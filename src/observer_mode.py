"""
Active Observer Mode Implementation.
Phases:
1. Shadow Run (Logging to CSV, 15m verification)
2. MiMo Thesis Validation (Telegram human feedback streak)
3. Latency Stress-Test (Detection to EV calculation check)
"""

import asyncio
import csv
import os
import time
import logging
import json
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any

# Telegram Imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram import Bot
import telegram.error # Robustness

import hashlib

# Project imports
from src.arbitrage.entity_resolver_logic import get_resolver
from src.data.betfair_client import BetfairClient, BetfairSimulator
from src.data.gamma_client import GammaAPIClient
from src.data.sx_bet_client import SXBetClient, PolySXArbitrageScanner, SXBetCategory # New Integration
from src.arbitrage.cross_platform_mapper import CrossPlatformMapper, ArbOpportunity, MarketMapping
from src.arbitrage.arbitrage_validator import ArbitrageValidator
from src.utils.latency_monitor import monitor
from src.utils.sx_normalizer import SXNormalizer

logger = logging.getLogger("ObserverBot")

class ObserverMode:
    CSV_FILE = "opportunities_found.csv"
    STREAK_TARGET = 50
    STATE_FILE = ".mimo_streak.json"
    MIMO_COST_PER_TOKEN = 0.00001 # Estimated cost in USD

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.mimo_streak = self._load_streak()
        self.trust_ai = self.mimo_streak >= self.STREAK_TARGET
        self.validation_callbacks = {} # mapping_id -> Future
        
        self.poly = GammaAPIClient()
        self.bf = BetfairClient(use_delay=True) if os.getenv('BETFAIR_USERNAME') else BetfairSimulator(use_delay=True)
        # SIMULATION MODE: Threshold -100 to catch everything
        self.mapper = CrossPlatformMapper(min_ev_threshold=-100.0) 
        
        # SX Bet Integration
        self.sx_client = SXBetClient()
        self.sx_scanner = PolySXArbitrageScanner(sx_client=self.sx_client)
        
        # Zero Friction State
        self.last_bf_checksums: Dict[str, str] = {}
        self.mimo_temp = 0.0
        self.token_costs_usd = 0.0
        
        self.pending_verifications = [] # (opp, initial_price, timestamp)
        
        # Ensure CSV exists with enhanced technical headers
        if not os.path.exists(self.CSV_FILE):
            with open(self.CSV_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'event', 'poly_price', 'bf_odds', 'ev_net', 
                    'sentiment', 'result_15min', 'latency_ms', 'gas_pc', 
                    'drift', 'tokens_cost', 'volatility_tag'
                ])

    def _load_streak(self) -> int:
        if os.path.exists(self.STATE_FILE):
            try:
                with open(self.STATE_FILE, 'r') as f:
                    return json.load(f).get('streak', 0)
            except: pass
        return 0

    def _save_streak(self):
        with open(self.STATE_FILE, 'w') as f:
            json.dump({'streak': self.mimo_streak}, f)

    def _get_bf_checksum(self, prices) -> str:
        """Create a hash of the top 3 Betfair prices to avoid redundant AI calls."""
        top_data = [(p.back_price, p.lay_price) for p in prices[:3]]
        return hashlib.md5(str(top_data).encode()).hexdigest()

    async def get_sentiment(self, text: str) -> float:
        """Mock/Previous implementation of sentiment analysis."""
        # Simple sentiment placeholder - can be improved via MiMo if needed
        return 0.5

    async def validate_mapping_telegram(self, mapping: MarketMapping) -> bool:
        """Fase 2: Request human validation via Telegram."""
        if self.trust_ai:
            return True

        if not self.token or not self.chat_id:
            logger.warning("Telegram not configured, skipping validation.")
            return True

        mapping_id = hashlib.md5(f"{mapping.polymarket_id}{mapping.betfair_event_id}".encode()).hexdigest()[:8]
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Correct", callback_data=f"val_ok_{mapping_id}"),
                InlineKeyboardButton("❌ Wrong", callback_data=f"val_no_{mapping_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            f"🧠 <b>MIMO Mapping Validation</b>\n\n"
            f"Poly: {mapping.polymarket_question}\n"
            f"Betfair: {mapping.betfair_event_name}\n\n"
            f"Streak: {self.mimo_streak}/{self.STREAK_TARGET}\n"
            f"Confidence: {mapping.confidence:.0%}"
        )
        
        bot = Bot(token=self.token)
        try:
            sent_msg = await bot.send_message(
                chat_id=self.chat_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
            # Create a future to wait for the callback
            loop = asyncio.get_running_loop()
            fut = loop.create_future()
            self.validation_callbacks[mapping_id] = fut
            
            logger.info(f"Waiting for human validation for {mapping_id}...")
            
            try:
                # Wait for 5 minutes max
                result = await asyncio.wait_for(fut, timeout=300)
                return result
            except asyncio.TimeoutError:
                logger.warning(f"Validation timeout for {mapping_id}")
                return False
            finally:
                if mapping_id in self.validation_callbacks:
                    del self.validation_callbacks[mapping_id]
        except Exception as e:
            logger.error(f"Error sending Telegram validation: {e}")
            return True # Fallback to true if telegram fails

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        try:
            await query.answer()
        except Exception as e:
            logger.warning(f"Failed to answer callback: {e}")
        
        data = query.data
        if not data.startswith("val_"):
            return

        is_ok = data.startswith("val_ok_")
        mapping_id = data.split("_")[-1]
        
        if mapping_id in self.validation_callbacks:
            if not self.validation_callbacks[mapping_id].done():
                self.validation_callbacks[mapping_id].set_result(is_ok)
            
            if is_ok:
                self.mimo_streak += 1
                status = "✅ Validated"
            else:
                self.mimo_streak = 0
                status = "❌ Rejected"
            
            if self.mimo_streak >= self.STREAK_TARGET and not self.trust_ai:
                self.trust_ai = True
                await query.message.reply_text("🔓 <b>AI TRUSTED</b>: MiMo has reached 50 hits. Full automation active.")
            
            self._save_streak()
            
            try:
                await query.edit_message_text(
                    text=query.message.text + f"\n\n<b>Result: {status}</b>\nStreak: {self.mimo_streak}",
                    parse_mode='HTML'
                )
            except: pass

    async def shadow_run_logic(self, opp: ArbOpportunity, latency_ms: float, tokens_estimate: int = 200):
        """Fase 1: Log to CSV and prepare 15m verification with Manifesto metrics."""
        sentiment = await self.get_sentiment(opp.mapping.polymarket_question)
        
        costs = tokens_estimate * self.MIMO_COST_PER_TOKEN
        self.token_costs_usd += costs
        
        gas_est = 0.01 # Mock gas
        # Correctly use ROI as the metric for "ev_net" in this context
        gas_pc = (gas_est / opp.ev_net * 100) if opp.ev_net > 0 else 0
        
        with open(self.CSV_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                opp.mapping.betfair_event_name,
                opp.poly_yes_price,
                opp.betfair_lay_odds, # Log usage of LAY odds
                f"{opp.ev_net:.2f}%", # ROI
                sentiment,
                "PENDING",
                f"{latency_ms:.2f}",
                f"{gas_pc:.2f}%",
                "0.00", # Drift placeholder
                f"{costs:.5f}",
                "NORMAL"
            ])
        
        self.pending_verifications.append({
            'market_id': opp.mapping.betfair_market_id,
            'initial_odds': opp.betfair_lay_odds,
            'timestamp': datetime.now(),
            'event_name': opp.mapping.betfair_event_name,
            'ev_start': opp.ev_net
        })

    async def report_loop(self):
        """Report statistics to Telegram every 5 minutes."""
        if not self.token or not self.chat_id: return
        
        bot = Bot(token=self.token)
        while True:
            await asyncio.sleep(300) # 5 minutes
            try:
                stats = self.mapper.stats
                msg = (
                    f"📊 <b>STATUS REPORT</b>\n"
                    f"Mappings (Total): {stats.get('successful_mappings', 0)}\n"
                    f"AI Hits: {stats.get('ai_hits', 0)}\n"
                    f"Cache Hits: {stats.get('cache_hits', 0)}\n"
                    f"Vector Hits: {stats.get('vector_hits', 0)}\n"
                    f"Streak: {self.mimo_streak}"
                )
                await bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML')
            except Exception as e:
                logger.error(f"Report loop error: {e}")

    async def verify_loop(self):
        """Fase 1 verification with Strict Manifesto Logic (Volatility & Drift)."""
        while True:
            now = datetime.now()
            verifiable = [v for v in self.pending_verifications if now - v['timestamp'] >= timedelta(minutes=15)]
            
            for v in verifiable:
                prices = await self.bf.get_prices([v['market_id']])
                if prices:
                    # We check LAY price stability (Liquidity Risk)
                    lay_price = min((p.lay_price for p in prices if p.lay_price > 0), default=0)
                    
                    # High Volatility Risk Check
                    price_diff = 0
                    if v['initial_odds'] > 0 and lay_price > 0:
                        price_diff = abs(lay_price - v['initial_odds']) / v['initial_odds']
                    
                    if price_diff > 0.3: # 30% swing in 15 mins
                        result = "HIGH_VOLATILITY_RISK"
                    else:
                        # Simple mark: Just logged data available
                        result = "DATA_LOGGED"
                        
                    logger.info(f"🏛️ Manifesto Verification | {v['event_name']}: {result} | Drift: {price_diff:.1%}")
                    
                    with open(self.CSV_FILE, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            datetime.now().isoformat(), 
                            f"VERIFY_{v['event_name']}", 
                            "", 
                            lay_price, 
                            "", 
                            "", 
                            result, 
                            "", 
                            "", 
                            f"{price_diff:.4f}", # Semantic Drift
                            "",
                            result
                        ])
                
                self.pending_verifications.remove(v)
            
            await asyncio.sleep(60)

    async def run_cycle(self):
        """Refactored Cycle: Unified Exchange Scanning (Poly + BF + SX)."""
        cycle_start = time.time()
        logger.info("📡 Scanning markets (Unified Mode)...")
        
        try:
            # 1. Fetch Polymarket
            gamma_start = time.time()
            poly_markets = await self.poly.get_all_match_markets(limit=200)
            monitor.record('gamma_fetch', (time.time() - gamma_start) * 1000)
            
            # 2. Fetch Exchanges (Parallel)
            # Start/KeepAlive BF Session
            if not self.bf.is_authenticated:
                await self.bf.login()

            # --- FETCH BETFAIR MARKETS (Per Sport to ensure Market IDs) ---
            bf_events = []
            target_ids = ['1', '2', '7511', '7522', '2378961', '10']
            if "betfair.es" in self.bf.base_url: target_ids = ['1', '2', '7522', '7511', '4', '7']
            
            # Helper to fetch BF
            async def fetch_bf_sport(tid):
                payload = {
                    "filter": {
                        "eventTypeIds": [tid],
                        "marketStartTime": {"from": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}
                    },
                    "maxResults": 200, # Cap per sport for speed
                    "marketProjection": ["EVENT", "MARKET_START_TIME", "COMPETITION", "RUNNER_DESCRIPTION"]
                }
                
                # TENNIS FIX (From Audit)
                if tid == '2':
                    if "marketTypeCodes" in payload["filter"]: del payload["filter"]["marketTypeCodes"]
                    payload["marketProjection"] = ["EVENT", "MARKET_START_TIME", "COMPETITION"]
                    if "marketStartTime" in payload["filter"]: del payload["filter"]["marketStartTime"]
                elif tid == '1': # Soccer
                     payload["filter"]["marketTypeCodes"] = ["MATCH_ODDS"]
                elif tid == '7522': # Basketball
                     payload["filter"]["marketTypeCodes"] = ["MONEY_LINE", "MATCH_ODDS"]

                res = await self.bf._api_request('listMarketCatalogue', payload)
                if not res: return []
                
                parsed = []
                for m in res:
                    ev = m.get('event', {})
                    parsed.append({
                        'id': ev.get('id'),
                        'event_id': ev.get('id'),
                        'market_id': m.get('marketId'), # CRITICAL: We now have the Market ID
                        'name': ev.get('name'),
                        'competition': m.get('competition', {}).get('name', ''),
                        'open_date': m.get('marketStartTime'),
                        'market_type': m.get('description', {}).get('marketType', 'MATCH_ODDS'),
                        'runners': m.get('runners', []),
                        'exchange': 'bf',
                        '_sport': 'tennis' if tid=='2' else ('soccer' if tid=='1' else 'other')
                    })
                return parsed

            # --- FETCH SX MARKETS ---
            async def fetch_sx():
                return await self.sx_client.get_markets_standardized()

            # Execute Fetches
            tasks = [fetch_bf_sport(tid) for tid in target_ids]
            tasks.append(fetch_sx())
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for res in results:
                if isinstance(res, list):
                    bf_events.extend(res)
            
            logger.info(f"Exchange Surface: {len(bf_events)} markets (BF + SX)")
            
            if not bf_events:
                 logger.warning("No exchange events found.")
                 return

            # Pre-group by date
            bf_buckets = defaultdict(list)
            for event in bf_events:
                start_str = event.get('open_date')
                dt_key = 'NO_DATE'
                if start_str:
                    try:
                        dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                        event['_start_date_parsed'] = dt
                        dt_key = dt.date()
                    except: pass
                bf_buckets[dt_key].append(event)

            # 3. Mapping Loop
            for poly_market in poly_markets:
                q = poly_market.get('question', '')
                tokens = poly_market.get('tokens', [])
                if not tokens: continue
                
                try: yes_price = float(tokens[0].get('price', 0.5))
                except: continue

                # Determine Sport Category
                category = poly_market.get('category', '').lower()
                slug = poly_market.get('slug', '').lower()
                sport_id = 'soccer' # default
                if 'tennis' in category or 'atp' in slug: sport_id = 'tennis'
                elif 'basket' in category or 'nba' in slug: sport_id = 'basketball'
                
                # MAP IT (Using the robust MegaAudit/Mapper Logic)
                # OPTIMIZATION: Sport Blocking (Phase 3)
                # Filter 'bf_events' (or buckets) to only include relevant sport?
                # The 'bf_buckets' are currently by DATE. We should ideally sub-filter results of date blocking by sport inside mapper,
                # OR pass a filtered list here.
                # Since 'bf_buckets' contains mixed sports, we can filter relevant events AFTER date blocking in mapper, 
                # OR we can assume 'mapper' creates candidates from buckets.
                
                # For now, let's keep passing all buckets but ensure the mapper respects 'sport_category' strictly
                # in candidates generation (it mostly does via _sport_cross_check).
                # To truly "Block", we should have organized bf_events by sport.
                # But 'bf_events' variable here is just a list. 
                # Let's filter 'bf_events' passed (legacy arg) AND trust buckets.
                
                # Filter bf_events list for non-bucketed logic (if any)
                relevant_events = [e for e in bf_events if e.get('_sport', 'other') == sport_id or e.get('_sport') == 'other']
                
                mapping = await self.mapper.map_market(
                    poly_market=poly_market,
                    betfair_events=relevant_events, # Optimization
                    sport_category=sport_id,
                    polymarket_slug=slug,
                    bf_buckets=bf_buckets
                )
                
                if mapping:
                    # 4. Price Validation & Math
                    best_lay = 0.0
                    fee = 0.0
                    
                    try:
                        if mapping.exchange == 'sx':
                            # SX Logic
                            try:
                                ob = await self.sx_client.get_orderbook(mapping.betfair_market_id)
                                best_bid = ob.best_bid
                                if best_bid > 0:
                                    best_lay = 1.0 / best_bid
                                    fee = 0.02
                            except Exception as e:
                                logger.error(f"SX Price Error: {e}")
                                
                        else:
                            # Betfair Logic
                            try:
                                prices = await self.bf.get_prices([mapping.betfair_market_id])
                                if prices and mapping.bf_selection_id:
                                    p = next((x for x in prices if str(x.selection_id) == str(mapping.bf_selection_id)), None)
                                    if p:
                                        best_lay = p.lay_price
                                        fee = self.bf.COMMISSION_RATE
                            except Exception as e:
                                logger.warning(f"BF Price Error (skipping): {e}")

                        # Calculate EV
                        if best_lay > 1.01:

                         res = ArbitrageValidator.calculate_roi(yes_price, best_lay, fee)
                         
                         if res.is_opportunity and res.roi_percent > 0:
                            opp = ArbOpportunity(
                                mapping=mapping,
                                poly_yes_price=yes_price,
                                poly_no_price=1-yes_price,
                                betfair_back_odds=0.0,
                                betfair_lay_odds=best_lay,
                                ev_net=res.roi_percent,
                                is_profitable=True,
                                direction=f"buy_poly_sell_{mapping.exchange}",
                                detected_at=datetime.now(),
                                betfair_delayed=self.bf.use_delay
                            )
                            logger.info(f"🚀 MATCH ({mapping.exchange.upper()}): {mapping.betfair_event_name} | ROI: {res.roi_percent:.2f}%")
                            await self.shadow_run_logic(opp, 0)
                    
                    except Exception as e:
                        logger.error(f"Price/Math Error for {mapping.betfair_event_name}: {e}")

        except Exception as e:
            logger.error(f"Cycle Unified Error: {e}", exc_info=True)

    async def _log_sx_opportunity(self, opp: Dict, type_tag: str):
        """Log SX Opportunity to CSV and Telegram."""
        # opp dict from scanner has: region, team vs team, profit %, etc.
        # standardize keys
        event_name = opp.get('sx_label', 'Unknown')
        profit = opp.get('expected_profit_pct', 0)
        
        # Log to CSV
        with open(self.CSV_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                f"[{type_tag}] {event_name}",
                opp.get('poly_yes_price', 0),
                opp.get('sx_best_ask', 0),
                f"{profit:.2f}%",
                0.5, # Sentiment
                "PENDING",
                0, # Latency
                0, # Gas
                0, # Drift
                0, # Cost
                "SX_ARB"
            ])
            
        # Telegram
        if self.token and self.chat_id:
            bot = Bot(token=self.token)
            msg = (
                f"🚀 <b>SX ARBITRAGE FOUND [{type_tag}]</b>\n"
                f"Event: {event_name}\n"
                f"Profit: {profit:.2f}%\n"
                f"Direction: {opp.get('direction', 'Unknown')}\n"
                f"Buy: {opp.get('buy_price', 0):.3f}\n"
                f"Sell: {opp.get('sell_price', 0):.3f}"
            )
            try:
                await bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML')
            except: pass

    async def process_sx_arbitrage(self, poly_markets: List[Dict], bf_events: List[Dict]):
        """
        Scanning Routine for SX Bet Arbitrage.
        Covers:
        1. Poly <-> SX
        2. SX <-> Betfair
        3. Triangle (Poly <-> SX <-> BF)
        """
        try:
            # --- 1. Poly <-> SX ---
            # scanner.scan fetches SX markets internally (cached)
            sx_opps = await self.sx_scanner.scan(poly_markets)
            for opp in sx_opps:
                await self._log_sx_opportunity(opp, "Poly-SX")
                
            # --- 2. SX <-> Betfair & Triangle ---
            # Fetch SX markets explicitly (hits cache) to check against BF
            sx_markets = await self.sx_client.get_active_markets()
            
            # Simple Name Matching for SX <-> BF (Optimized loop)
            # Create dict of BF events by normalized name for O(1) lookup? 
            # Names are fuzzy. Use simple normalization.
            
            bf_lookup = {}
            for ev in bf_events:
                # Normalize: lowercase, remove " v ", " vs "
                name = ev.get('name', '').lower().replace(' v ', ' ').replace(' vs ', ' ')
                bf_lookup[name] = ev
            
            for sx_m in sx_markets:
                # Normalize SX label
                sx_name = sx_m.label.lower().replace(' v ', ' ').replace(' vs ', ' ')
                
                # Direct lookup first (Fast)
                bf_match = bf_lookup.get(sx_name)
                
                # If no direct match, try Normalized Splitting (SXNormalizer)
                if not bf_match:
                     # e.g. "Carabobo FC vs Huachipato" -> ["Carabobo FC", "Huachipato"]
                     normalized = SXNormalizer.expand_candidates({'name': sx_m.label}) 
                     # Normalized returns dicts with 'name'.
                     
                     for cand in normalized:
                         if cand.get('_is_virtual'):
                             c_name = cand['name'].lower()
                             # Try lookup with virtual name
                             bf_match = bf_lookup.get(c_name)
                             if bf_match: break
                             
                             # Try fuzzy against BF keys
                             # (Use token overlap loop below but with c_name?)
                
                # If still no match, try token overlap (Simple Fuzzy)
                if not bf_match:
                    sx_tokens = set(sx_name.split())
                    best_overlap = 0
                    for bf_n, ev in bf_lookup.items():
                        bf_tokens = set(bf_n.split())
                        overlap = len(sx_tokens.intersection(bf_tokens))
                        if overlap > best_overlap and overlap >= 2: # At least 2 words (names)
                             # Jaccard
                             jaccard = overlap / len(sx_tokens.union(bf_tokens))
                             if jaccard > 0.6:
                                 bf_match = ev
                                 best_overlap = overlap
                
                if bf_match:
                    # Found SX <-> BF Match! Add to list for batch processing
                    bf_event_id = bf_match.get('event', {}).get('id') or bf_match.get('id')
                    if bf_event_id:
                        matched_pairs.append((sx_m, bf_event_id, bf_match.get('name', '')))
            
            if not matched_pairs: return

            # Batch Fetch Market Catalogues to get "Match Odds"
            event_ids = list(set(p[1] for p in matched_pairs))
            chunk_size = 5 # Small chunks to respect API limits/latency
            
            for i in range(0, len(event_ids), chunk_size):
                chunk = event_ids[i:i+chunk_size]
                
                # 1. Get Market IDs (Match Odds)
                bf_markets = await self.bf.list_markets(event_ids=chunk, market_types=['MATCH_ODDS'])
                if not bf_markets: continue
                
                # Map Event ID -> Market ID
                event_to_market_map = {m.event_id: m.market_id for m in bf_markets if m.status == 'OPEN'}
                
                # 2. Get Prices
                market_ids = list(event_to_market_map.values())
                if not market_ids: continue
                
                prices = await self.bf.get_prices(market_ids)
                price_map = {p.market_id: p for p in prices}
                
                # 3. Compare with SX
                for sx_m, ev_id, bf_name in matched_pairs:
                    if ev_id not in chunk: continue
                    
                    market_id = event_to_market_map.get(ev_id)
                    if not market_id: continue
                    
                    bf_price = price_map.get(market_id)
                    if not bf_price: continue
                    
                    # --- CHECK ARB: SX vs BF ---
                    # Scenario A: Buy SX (Ask) -> Lay BF (Sell)
                    # Cost: SX Ask. Return: 1 (if win). 
                    # Hedging: Lay BF. (We sell reliability).
                    # Actually standard arb: Back SX (Ask) + Back BF (Back)? No.
                    # Back SX (Ask) + Lay BF (Lay Price).
                    # If SX Ask < 1/Lay_Odds (Inv Lay Price) -> Arb?
                    # Profitable if: (1/SX_Ask) > Lay_Odds? No.
                    # Simple: If we buy at 2.0 (50%) and Lay at 1.8 (55%), we profit.
                    # So: SX_Decimal_Ask > BF_Lay_Odds ? (Wait, Lay odds are what we PAY to lay?)
                    # If we Back at 2.0 (SX) and Lay at 1.9 (BF):
                    # Bet $10 on SX @ 2.0 -> Win $20. (Cost $10)
                    # Lay $10 on BF @ 1.9 -> Risk $9 to win $10.
                    # If Win: SX +$10, BF -$9 = +$1.
                    # If Lose: SX -$10, BF +$10 = $0.
                    # So yes: Back Odds (SX Implied) > Lay Odds (BF).
                    # SX Ask is prob. Implied Odds = 1/SX_Ask.
                    
                    sx_implied_back = 1.0 / sx_m.best_ask if sx_m.best_ask > 0 else 0
                    
                    if sx_implied_back > bf_price.lay_price and bf_price.lay_price > 1.01:
                        # Found Arb!
                        roi = (sx_implied_back - bf_price.lay_price) / bf_price.lay_price * 100
                        if roi > 0:
                            opp = {
                                'sx_label': sx_m.label,
                                'direction': 'Back SX / Lay BF',
                                'expected_profit_pct': roi,
                                'poly_yes_price': 0, # N/A
                                'sx_best_ask': sx_m.best_ask,
                                'buy_price': sx_m.best_ask,
                                'sell_price': bf_price.lay_price # Lay odds
                            }
                            await self._log_sx_opportunity(opp, "SX-BF")
                            logger.info(f"💰 SX-BF ARB: {sx_m.label} | ROI: {roi:.2f}%")

                    # Scenario B: Back BF (Back) + Lay SX (Sell/Bid)
                    # SX Bid is what people buy from us. We sell at Bid? No, we sell at Bid.
                    # BF Back > 1/SX_Bid ?
                    
                    sx_implied_lay = 1.0 / sx_m.best_bid if sx_m.best_bid > 0 else 999.0
                    if bf_price.back_price > sx_implied_lay:
                         roi = (bf_price.back_price - sx_implied_lay) / sx_implied_lay * 100
                         if roi > 0:
                            opp = {
                                'sx_label': sx_m.label,
                                'direction': 'Back BF / Sell SX',
                                'expected_profit_pct': roi,
                                'poly_yes_price': 0,
                                'sx_best_ask': 0,
                                'buy_price': bf_price.back_price,
                                'sell_price': sx_m.best_bid
                            }
                            await self._log_sx_opportunity(opp, "SX-BF")
                            logger.info(f"💰 SX-BF ARB (Reverse): {sx_m.label} | ROI: {roi:.2f}%")

                    # --- TRIANGLE CHECK (Poly-SX-BF) ---
                    # Check if this SX market was also matched with Poly
                    # We need to map SX hash back to Poly opps.
                    # Optimization: Do this on the fly or pre-map?
                    # Pre-map from step 1.
                    
                    # Assuming we stored step 1 results in a dict for faster lookup
                    # We didn't. Let's rely on iteration or refactor step 1.
                    # Refactoring step 1 to return dict would be cleaner but let's just loop for now (list is small)
                    
                    poly_match = next((o for o in sx_opps if o.get('sx_hash') == sx_m.market_hash), None)
                    if poly_match:
                        # We have Poly, SX, and BF prices for the same event!
                        # Compare Poly Yes/No vs BF Back/Lay
                        # We already have Poly <-> SX arb.
                        # We already have SX <-> BF arb.
                        # Do we have Poly <-> BF arb via SX name matching?
                        # The Main Mapper handles Poly <-> BF via different logic (Static/AI).
                        # This Triangle check confirms if our name matching found something the Main Mapper missed?
                        # OR if there is a circular arb?
                        # Let's just log it as a TRIANGLE match for visibility.
                         logger.info(f"📐 TRIANGLE MATCH: {sx_m.label} available on Poly, SX, and BF!")
                        
                         # Optional: Check Poly vs BF directly using these specific prices
                         # Poly Yes vs BF Lay
                         p_yes = poly_match.get('poly_yes_price')
                         if p_yes and bf_price.lay_price > 0:
                             roi_tri = ArbitrageValidator.calculate_roi(p_yes, bf_price.lay_price, 0.0).roi_percent
                             if roi_tri > 0:
                                 opp = {
                                     'sx_label': sx_m.label + " (Triangle)",
                                     'direction': 'Poly -> BF (Verified via SX)',
                                     'expected_profit_pct': roi_tri,
                                     'poly_yes_price': p_yes,
                                     'sx_best_ask': 0, # N/A
                                     'buy_price': p_yes,
                                     'sell_price': bf_price.lay_price
                                 }
                                 await self._log_sx_opportunity(opp, "TRIANGLE")

                
        except Exception as e:
            logger.error(f"SX Scan Error: {e}")

        except Exception as e:
            logger.error(f"SX Scan Error: {e}")

    async def start(self):
        logger.info("Starting Observer Mode...")
        
        # Start Telegram App (Robust)
        if self.token:
            try:
                app = Application.builder().token(self.token).build()
                app.add_handler(CallbackQueryHandler(self.handle_callback))
                
                # Robust Error Handler
                async def tg_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
                    if isinstance(context.error, telegram.error.Conflict):
                        logger.warning("⚠️ TELEGRAM CONFLICT: Instance terminated by another request. Disabling Telegram.")
                        # We cannot stop easily but we can swallow the error
                    else:
                        logger.error(f"Telegram Error: {context.error}")

                app.add_error_handler(tg_error_handler)
                
                await app.initialize()
                await app.start()
                # Start polling with clean state
                await app.updater.start_polling(drop_pending_updates=True)
                
            except telegram.error.Conflict:
                 logger.warning("⚠️ TELEGRAM CONFLICT: Running in HEADLESS mode (No Telegram).")
                 self.token = None # Disable TG for this session
            except Exception as e:
                logger.warning(f"⚠️ Telegram startup failed: {e}. Running in HEADLESS mode.")
                self.token = None 

        
        # Start verification loop
        asyncio.create_task(self.verify_loop())
        # Start reporting loop
        asyncio.create_task(self.report_loop())
        
        while True:
            await self.run_cycle()
            if os.getenv('SINGLE_CYCLE') == 'true':
                logger.info("SINGLE_CYCLE=true detected. Exiting loop.")
                break
            await asyncio.sleep(15)

if __name__ == "__main__":
    observer = ObserverMode()
    asyncio.run(observer.start())
