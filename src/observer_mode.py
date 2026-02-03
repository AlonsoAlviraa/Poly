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
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram import Bot
import hashlib

# Project imports
from src.data.betfair_client import BetfairClient, BetfairSimulator
from src.data.gamma_client import GammaAPIClient
from src.arbitrage.cross_platform_mapper import CrossPlatformMapper, ArbOpportunity, MarketMapping
from src.utils.latency_monitor import monitor

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
        await query.answer()
        
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
            
            await query.edit_message_text(
                text=query.message.text + f"\n\n<b>Result: {status}</b>\nStreak: {self.mimo_streak}",
                parse_mode='HTML'
            )

    async def shadow_run_logic(self, opp: ArbOpportunity, latency_ms: float, tokens_estimate: int = 200):
        """Fase 1: Log to CSV and prepare 15m verification with Manifesto metrics."""
        sentiment = await self.get_sentiment(opp.mapping.polymarket_question)
        
        costs = tokens_estimate * self.MIMO_COST_PER_TOKEN
        self.token_costs_usd += costs
        
        gas_est = 0.01 # Mock gas
        gas_pc = (gas_est / opp.ev_net * 100) if opp.ev_net > 0 else 0
        
        with open(self.CSV_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                opp.mapping.betfair_event_name,
                opp.poly_yes_price,
                opp.betfair_back_odds,
                opp.ev_net,
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
            'initial_odds': opp.betfair_back_odds,
            'timestamp': datetime.now(),
            'event_name': opp.mapping.betfair_event_name,
            'ev_start': opp.ev_net
        })

    async def verify_loop(self):
        """Fase 1 verification with Strict Manifesto Logic (Volatility & Drift)."""
        while True:
            now = datetime.now()
            verifiable = [v for v in self.pending_verifications if now - v['timestamp'] >= timedelta(minutes=15)]
            
            for v in verifiable:
                prices = await self.bf.get_prices([v['market_id']])
                if prices:
                    best_back = max((p.back_price for p in prices), default=0)
                    
                    # High Volatility Risk Check
                    price_diff = abs(best_back - v['initial_odds']) / v['initial_odds'] if v['initial_odds'] > 0 else 0
                    if price_diff > 0.3: # 30% swing in 15 mins
                        result = "HIGH_VOLATILITY_RISK"
                    else:
                        result = "PROFIT" if best_back >= v['initial_odds'] else "LOSS"
                        
                    logger.info(f"🏛️ Manifesto Verification | {v['event_name']}: {result}")
                    
                    with open(self.CSV_FILE, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            datetime.now().isoformat(), 
                            f"VERIFY_{v['event_name']}", 
                            "", 
                            best_back, 
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
        """Main loop cycle with Zero Friction and Auto-Adjust Latency."""
        cycle_start = time.time()
        
        logger.info("📡 Scanning markets (Manifesto Mode)...")
        
        try:
            # 1. Ingestion
            ingestion_start = time.time()
            poly_markets = self.poly.get_markets(closed=False, limit=20, order="volume")
            await self.bf.login()
            # Politics: 2378961, Special Bets: 10, Current Affairs: 3988
            bf_events = await self.bf.list_events(event_type_ids=['2378961', '10', '3988']) 
            monitor.record('ingestion', (time.time() - ingestion_start) * 1000)
            
            for m in poly_markets:
                q = m.get('question', '')
                cid = m.get('condition_id', '')
                tokens = m.get('tokens', [])
                if not tokens: continue
                yes_price = float(tokens[0].get('price', 0.5))
                
                # Mapping (Phase 2)
                mapping_start = time.time()
                mapping = await self.mapper.map_market( q, cid, bf_events, yes_price )
                mapping_latency = (time.time() - mapping_start) * 1000
                monitor.record('mapping', mapping_latency)
                
                # Manifesto: Latency Auto-Adjust
                if mapping_latency > 500:
                    logger.warning("📉 Latency > 500ms in Mapping. Auto-adjusting parameters...")
                    self.mimo_temp = 0.0 # Force deterministic/faster output
                    bot = Bot(self.token) if self.token else None
                    if bot and self.chat_id:
                        await bot.send_message(self.chat_id, f"⚠️ <b>AUTO-ADJUST</b>: Latency {mapping_latency:.0f}ms. Reducing temp.")
                    
                if mapping:
                    # 2. Zero Friction: Check for price change before complex AI/Sentiment
                    bf_prices = await self.bf.get_prices([mapping.betfair_market_id])
                    if not bf_prices: continue
                    
                    checksum = self._get_bf_checksum(bf_prices)
                    if self.last_bf_checksums.get(mapping.betfair_market_id) == checksum:
                        logger.debug(f"Ahorro de tokens: Sin cambios en {mapping.betfair_event_name}")
                        continue
                    
                    self.last_bf_checksums[mapping.betfair_market_id] = checksum
                    
                    # 3. Projection (Math)
                    proj_start = time.time()
                    best_back = max((p.back_price for p in bf_prices), default=0)
                    ev_net, is_profitable = self.bf.calculate_ev_net(yes_price, best_back)
                    monitor.record('projection', (time.time() - proj_start) * 1000)
                    
                    # Overall Latency
                    overall_latency = (time.time() - cycle_start) * 1000
                    monitor.record('overall_scan', overall_latency)
                    
                    if overall_latency > 500:
                        bot = Bot(self.token) if self.token else None
                        msg = f"🛰️ <b>LATENCY ALERT</b>: {overall_latency:.2f}ms > 500ms"
                        if bot and self.chat_id:
                            await bot.send_message(self.chat_id, msg, parse_mode='HTML')
                        logger.warning(msg)

                    if ev_net > 0:
                        opp = ArbOpportunity(
                            mapping=mapping,
                            poly_yes_price=yes_price,
                            poly_no_price=1 - yes_price,
                            betfair_back_odds=best_back,
                            betfair_lay_odds=best_back + 0.02,
                            ev_net=ev_net,
                            is_profitable=True,
                            direction='buy_poly_back_bf',
                            detected_at=datetime.now()
                        )
                        
                        validated = await self.validate_mapping_telegram(mapping)
                        if validated:
                            await self.shadow_run_logic(opp, overall_latency)
                            logger.info(f"🚀 Opportunity logged: {mapping.betfair_event_name}")
        
        except Exception as e:
            logger.error(f"Cycle error: {e}")

    async def start(self):
        logger.info("Starting Observer Mode...")
        
        # Start Telegram App
        if self.token:
            app = Application.builder().token(self.token).build()
            app.add_handler(CallbackQueryHandler(self.handle_callback))
            await app.initialize()
            await app.start()
            # Start polling in background
            asyncio.create_task(app.updater.start_polling())
        
        # Start verification loop
        asyncio.create_task(self.verify_loop())
        
        while True:
            await self.run_cycle()
            await asyncio.sleep(15)

import hashlib

if __name__ == "__main__":
    observer = ObserverMode()
    asyncio.run(observer.start())
