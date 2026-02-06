
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Dict, List, Any

from src.data.gamma_client import GammaAPIClient
from src.data.betfair_client import BetfairClient
from src.data.sx_bet_client import SXBetClient, SXBetCategory
from src.arbitrage.cross_platform_mapper import CrossPlatformMapper, MarketMapping
from src.arbitrage.arbitrage_validator import ArbitrageValidator

# Silence noisy loggers
logging.getLogger("src.arbitrage.cross_platform_mapper").setLevel(logging.WARNING)
logging.getLogger("src.data.betfair_client").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)


class MegaAudit:
    def __init__(self):
        self.gamma = GammaAPIClient()
        self.bf = BetfairClient()
        self.sx = SXBetClient()
        self.mapper = CrossPlatformMapper(min_ev_threshold=-100.0)
        
        # Stats
        self.stats = {
            "total_poly_markets": 0,
            "total_bf_events": 0,
            "matches_found": 0,
            "poly_by_sport": defaultdict(int),
            "by_sport": defaultdict(int),
            "fetched_by_sport": defaultdict(int),
            "scorecards": defaultdict(lambda: defaultdict(lambda: {"fetched": 0, "matched": 0}))
        }

    def _record_fetch(self, exchange: str, market_type: str):
        self.stats["scorecards"][exchange][market_type]["fetched"] += 1

    def _infer_region_tag(self, text: str) -> str:
        t = text.lower()
        if any(x in t for x in ['premier league', 'england', 'efl', 'fa cup']):
            return 'england'
        if any(x in t for x in ['la liga', 'laliga', 'spain', 'copa del rey']):
            return 'spain'
        if any(x in t for x in ['serie a', 'italy', 'coppa italia']):
            return 'italy'
        if any(x in t for x in ['bundesliga', 'germany', 'dfb']):
            return 'germany'
        if any(x in t for x in ['ligue 1', 'ligue1', 'france']):
            return 'france'
        if any(x in t for x in ['nba', 'wnba', 'mlb', 'nfl', 'nhl', 'usa']):
            return 'usa'
        return ''

    def _get_sport_id(self, name_or_slug: str) -> str:
        """Centralized sport classification logic."""
        s = name_or_slug.lower()
        # Broaden Basketball detection
        if any(x in s for x in ['basketball', 'nba', ' ncaa', 'basket', 'lakers', 'warriors', 'knicks', 'suns', 'euroleague', '76ers', 'celtics', 'wnba', 'bulls', 'cavaliers', 'rockets', 'hornets', 'clippers', 'nuggets', 'pacers', 'grizzlies', 'timberwolves', 'pelicans', 'magic', 'raptors', 'jazz']):
            return 'basketball'
        if any(x in s for x in ['tennis', 'atp', 'wta', 'open', 'nadal', 'djokovic', 'alcaraz', 'norrie', 'draper', 'itf', 'challenger']):
            return 'tennis'
        if any(x in s for x in ['mlb', 'baseball', 'yankees', 'dodgers', 'world series', 'red sox', 'mets']):
            return 'baseball'
        if any(x in s for x in ['politics', 'election', 'trump', 'vance', 'presidential', 'senate', 'vp', 'harris', 'biden']):
            return 'politics'
        return 'soccer'

    async def run(self):
        print("-" * 60)
        print("STARTING MEGA AUDIT: LOGIC & MATH TRACE")
        print("-" * 60 + "\n")

        # 1. Data Fetching
        print(">> [1/4] Fetching Polymarket markets (BROAD INGESTION)...")
        poly_markets = await self.gamma.get_all_match_markets(limit=500)
        self.stats["total_poly_markets"] = len(poly_markets)
        print(f"   Fetched {len(poly_markets)} Polymarket entities.")
        
        # Display Ingestion Telemetry
        if hasattr(self.gamma, 'discard_stats'):
            ds = self.gamma.discard_stats
            print(f"   INGESTION TELEMETRY:")
            print(f"     - Raw Fetched: {ds.get('total_raw',0)}")
            print(f"     - Discarded (No Category): {ds.get('no_category',0)}")
            print(f"     - Discarded (Expired): {ds.get('expired_date',0)}")
            print(f"     - Discarded (No Tokens): {ds.get('no_tokens',0)}")

        print("\n>> [2/4] Fetching Betfair events...")
        if not await self.bf.login():
            print("!! CRITICAL: Betfair Login Failed.")
            return

        # 2. Data Fetching (Per-Sport for unfair advantage)
        target_ids = ['1', '2', '7522', '10', '11', '4', '7']
        if "betfair.es" in self.bf.base_url: target_ids = ['1', '2', '7522', '11', '4', '7']
        
        market_types = ["MATCH_ODDS", "OVER_UNDER_15", "OVER_UNDER_25", "OVER_UNDER_35", "HANDICAP", "ASIAN_HANDICAP", "MONEY_LINE"]
        bf_events = []

        print(f">> [2/4] Fetching Betfair events per sport (Exhaustive Baskets/Tennis)...")
        market_types_soccer = ["MATCH_ODDS"] # Tighter set to avoid .es errors
        market_types_general = None # Broad for others
        bf_events = []

        print(f">> [2/4] Fetching Betfair events per sport (Targeted 150+ Baskets)...")
        for tid in target_ids:
            sport_name = 'unknown'
            current_mtypes = market_types_general
            if tid == '1': 
                sport_name = 'soccer'
                current_mtypes = market_types_soccer
            elif tid == '2': sport_name = 'tennis'
            elif tid == '7522': 
                sport_name = 'basketball'
                current_mtypes = ["MONEY_LINE", "MATCH_ODDS", "HANDICAP"]
            elif tid == '4': sport_name = 'financials'
            elif tid == '7': sport_name = 'horse_racing'
            elif tid == '10': sport_name = 'specials'
            elif tid == '11': sport_name = 'cricket'
            
            payload = {
                "filter": {
                    "eventTypeIds": [tid],
                    "marketStartTime": {
                        "from": (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat().replace('+00:00', 'Z')
                    }
                },
                "maxResults": 1000,
                "marketProjection": ["EVENT", "MARKET_START_TIME", "COMPETITION", "RUNNER_DESCRIPTION"]
            }
            if tid in ['2', '7522']:
                # For non-soccer, we want the description to see market types
                payload["marketProjection"].append("MARKET_DESCRIPTION")
                payload["maxResults"] = 1000 # Maximize basketball/tennis discovery
            
            # BROADENING: For basketball, don't restrict marketTypeCodes too much
            # TENNIS FIX: Strict Probe (No filters) for Tennis to verify API inventory
            if tid == '2':
                # Remove marketProjection and marketTypeCodes for Tennis Probe
                # We just want to see IF events exist
                if "marketTypeCodes" in payload["filter"]:
                   del payload["filter"]["marketTypeCodes"]
                # Keep marketProjection simple to avoid 400 errors or filtering
                payload["marketProjection"] = ["EVENT", "MARKET_START_TIME", "COMPETITION"]
                # Remove time filter for deep probe
                if "marketStartTime" in payload["filter"]:
                    del payload["filter"]["marketStartTime"]
            elif current_mtypes and tid != '7522':
                payload["filter"]["marketTypeCodes"] = current_mtypes
            
            raw_markets = await self.bf._api_request('listMarketCatalogue', payload)
            if not raw_markets:
                print(f"   [{tid}] No markets found for {sport_name}.")
                continue
            
            sport_count = 0
            for m in raw_markets:
                market_id = m.get('marketId')
                event = m.get('event', {})
                event_id = event.get('id')
                name = event.get('name')
                start_time = m.get('marketStartTime')
                
                # Standardized dict for mapper
                standardized = {
                    'id': event_id,
                    'event_id': event_id,
                    'market_id': market_id,
                    'name': name,
                    'competition': m.get('competition', {}).get('name', ''),
                    'open_date': start_time,
                    'market_type': m.get('description', {}).get('marketType', 'MATCH_ODDS'),
                    'runners': m.get('runners', []),
                    'exchange': 'bf',
                    '_sport': sport_name,
                    '_region_tag': self._infer_region_tag(f"{name} {m.get('competition', {}).get('name', '')}"),
                    '_start_date_parsed': None
                }
                bf_events.append(standardized)
                self._record_fetch('bf', standardized['market_type'])
                
                # Telemetry (Forced by tid)
                sport = sport_name
                self.stats["fetched_by_sport"][sport] += 1
                sport_count += 1
            
            print(f"   [{tid}] Fetched {sport_count} markets for {sport_name}.")

        self.stats["total_bf_events"] = len(bf_events)
        print(f"   TOTAL: Fetched {len(bf_events)} Betfair markets across all sports.")

        print("\n>> [2.5/4] Fetching SX Bet markets...")
        sx_events = await self.sx.get_markets_standardized()
        self.stats["total_sx_events"] = len(sx_events)
        print(f"   Fetched {len(sx_events)} SX Bet entities.")

        # 🔍 SX DEBUG: Print 5 random events to understand naming convention
        if sx_events:
            print("\n   🔍 SX BET RAW DATA SAMPLE (First 5):")
            for i, ev_sx in enumerate(sx_events[:5]):
                print(f"      [{i}] {ev_sx.get('name', 'N/A')} | Cat: {ev_sx.get('category')} | Type: {ev_sx.get('market_type')} | Date: {ev_sx.get('open_date')}")
        print("\n")


        for ev in sx_events:
            # Prefer 'category' if exchange provided it (standardized.append above)
            cat = ev.get('category', '').lower()
            if 'basketball' in cat: sport = 'basketball'
            elif 'soccer' in cat: sport = 'soccer'
            elif 'tennis' in cat: sport = 'tennis'
            elif 'baseball' in cat: sport = 'baseball'
            elif 'politics' in cat: sport = 'politics'
            else:
                sport = self._get_sport_id(f"{ev.get('name', '')} {ev.get('market_type', '')}")
            
            ev['_sport'] = sport # Store for later stats
            self.stats["fetched_by_sport"][sport] += 1
            self._record_fetch('sx', ev.get('market_type', 'UNKNOWN'))
            ev['_region_tag'] = self._infer_region_tag(f"{ev.get('name', '')} {ev.get('category', '')}")
        
        # Merge all exchange events
        all_exchange_events = bf_events + sx_events
        print(f"   TOTAL EXCHANGE SURfACE: {len(all_exchange_events)} markets.")

        # 2. Parallel Mapping & Logic Trace
        # Pre-group by date
        exchange_buckets = defaultdict(list)
        for event in all_exchange_events:
            start_str = event.get('open_date')
            dt_key = 'NO_DATE'
            hour_bucket = 'NO_TIME'
            if start_str:
                try:
                    clean_str = start_str.replace('Z', '+00:00')
                    dt = datetime.fromisoformat(clean_str)
                    event['_start_date_parsed'] = dt
                    dt_key = dt.date()
                    hour_bucket = dt.hour // 6
                except:
                    pass
            region = event.get('_region_tag', '') or 'global'
            exchange_buckets[(dt_key, hour_bucket, region)].append(event)
        
        # DEBUG: Date Parsing Stats
        sx_with_date = sum(1 for e in sx_events if e.get('_start_date_parsed'))
        print(f"   [Date Debug] SX Events with valid dates: {sx_with_date}/{len(sx_events)}")


        # 2. Parallel Mapping & Logic Trace
        print("\n>> [3/4] Performing Mappings & Logic Tracing (PARALLEL)...")
        print("-" * 60)
        
        semaphore = asyncio.Semaphore(15) # Parallelism cap
        mappings: List[MarketMapping] = []
        opportunities: List[Dict] = []

        async def process_single_market(pm):
            async with semaphore:
                # Telemetry
                sport = self._get_sport_id(f"{pm.get('category', '')} {pm.get('question', '')} {pm.get('slug', '')}")
                self.stats["poly_by_sport"][sport] += 1
                pm['_region_tag'] = self._infer_region_tag(f"{pm.get('slug', '')} {pm.get('question', '')} {pm.get('category', '')}")
                pm['_market_fingerprint'] = self.mapper._market_fingerprint_from_text(
                    pm.get('question', ''), market_type=pm.get('market_type')
                )
                
                # OPTIMIZATION: Sport Blocking (Relaxed based on user request)
                # Filter 'all_exchange_events' to only include relevant sport OR unknown
                # But allowing more flexibility for "General" matches
                relevant_events = [
                    e for e in all_exchange_events 
                    # if e.get('_sport', 'other') == sport or e.get('_sport') == 'other' or e.get('_sport') == 'unknown'
                    # User asked to NOT limit. We pass ALL events.
                    # Warning: This increases CPU usage but finds everything.
                ]

                m = await self.mapper.map_market(
                    poly_market=pm,
                    betfair_events=relevant_events, # Optimized List
                    sport_category=sport,
                    polymarket_slug=pm.get('slug', '').lower(),
                    bf_buckets=exchange_buckets
                )

                if m:
                    # Correct mapping of matches found by sport
                    # Use exchange event's sport if available
                    found_sport = getattr(m, '_sport', sport) # fallback to pm sport
                    self.stats["matches_found"] += 1
                    self.stats["by_sport"][found_sport] += 1
                    mappings.append(m)
                    self.stats["scorecards"][m.exchange][m.market_type or "UNKNOWN"]["matched"] += 1
                    
                    # Output formatting should be careful for parallel logs, but we'll try to keep them together
                    output = [
                        f"MATCH FOUND!",
                        f"   - POLY: {pm['question']}",
                        f"   - BF:   {m.betfair_event_name}",
                        f"   - CONF: {m.confidence:.2%}",
                        f"   - SPORT: {found_sport.upper()}"
                    ]
                    
                    # --- MATH TRACE ---
                    tokens = pm.get('tokens', [])
                    if tokens:
                        poly_price = float(tokens[0].get('price', 0.5))
                        
                        # Price Fetching Logic (Exchange-Aware)
                        best_lay = 0
                        fee_rate = 0
                        exch_tag = getattr(m, 'exchange', 'bf')
                        
                        if exch_tag == 'sx':
                            # SX Bet Price Logic
                            ob = await self.sx.get_orderbook(m.betfair_market_id)
                            # Implied Odds for SX = 1 / Price
                            # To hedge a buy on Poly (Yes), we need to SELL on SX (Take Bid)
                            # If selection is outcome two, use the complementary price.
                            selected_price = None
                            if ob:
                                if m.bf_selection_id:
                                    if str(m.bf_selection_id) == "1":
                                        selected_price = ob.best_bid
                                    elif str(m.bf_selection_id) == "2" and ob.best_ask > 0:
                                        selected_price = 1.0 - ob.best_ask
                                else:
                                    selected_price = ob.best_bid

                            if selected_price and selected_price > 0:
                                best_lay = 1.0 / selected_price
                                fee_rate = 0.02 # SX Commissions vary, 2% is safe
                        else:
                            # Betfair Price Logic
                            bf_prices = await self.bf.get_prices([m.betfair_market_id])
                            target_price = None
                            if bf_prices and m.bf_selection_id:
                                target_price = next((p for p in bf_prices if str(p.selection_id) == str(m.bf_selection_id)), None)
                            
                            if target_price and target_price.lay_price > 1.01:
                                best_lay = target_price.lay_price
                                fee_rate = self.bf.COMMISSION_RATE

                        if best_lay > 1.01:
                            # --- MATH TRACE ---
                            # ROI Calc from Validator perspective
                            price_lay_hedge = (best_lay - 1) / (best_lay - fee_rate)
                            total_cost = poly_price + price_lay_hedge
                            roi = (1.0 / total_cost - 1.0) * 100
                            
                            # --- AI SECOND OPINION & PRICE GUARDRAIL ---
                            ai_confirmed = True
                            ai_note = ""
                            is_price_consistent = True
                            
                            # 1. Price Consistency Check (Strategy 3)
                            # Implied probs: Poly (approx poly_price), Exch (1/best_lay approx)
                            # Best Lay is Decimal Odds. Implied Prob = 1/BestLay
                            implied_prob_exch = 1.0 / best_lay
                            if not ArbitrageValidator.check_price_consistency(poly_price, implied_prob_exch, max_diff=0.25):
                                is_price_consistent = False
                                ai_note += " [SUSPICIOUS: PRICE DIVERGENCE]"
                            
                            if roi > 5.0 and is_price_consistent:
                                is_match_ai, conf = await self.mapper.ai_mapper.check_similarity(pm['question'], m.betfair_event_name, sport)
                                if not is_match_ai or conf < 0.90:
                                    ai_confirmed = False
                                    ai_note += f" [SUSPICIOUS: AI Conf={conf:.2f}]"
                                else:
                                    ai_note += f" [AI VERIFIED: {conf:.2f}]"

                            output.extend([
                                f"   MATH TRACE ({exch_tag.upper()} Selection: {m.bf_runner_name}):",
                                f"     1. Poly Price (Yes): {poly_price:.3f}",
                                f"     2. {exch_tag.upper()} Implied Lay:   {best_lay:.2f}",
                                f"     3. Fee Rate:           {fee_rate*100:.1f}%",
                                f"     4. Price to Hedge:     {price_lay_hedge:.3f}",
                                f"     5. Total Cost:         {total_cost:.4f}",
                                f"     6. ROI (Arb):          {roi:.2f}%{ai_note}"
                            ])
                            if roi > 0 and ai_confirmed and is_price_consistent:
                                output.append(f"     [PROFITABLE OPPORTUNITY]")
                                opportunities.append({
                                    'poly': pm['question'],
                                    'exchange': m.betfair_event_name,
                                    'roi': roi,
                                    'sport': sport
                                })
                            elif roi > 0:
                                reasons = []
                                if not is_price_consistent: reasons.append("PRICE DIVERGENCE")
                                if not ai_confirmed: reasons.append("AI REJECTED")
                                output.append(f"     [OPPORTUNITY REJECTED: {', '.join(reasons)}]")
                        else:
                            output.append(f"   MATH: No liquid prices found on {exch_tag.upper()} for runner {m.bf_runner_name}.")
                    else:
                        output.append(f"   MATH: No tokens found for Polymarket.")
                    
                    print("\n".join(output))
                    print("-" * 60)

        tasks = [process_single_market(pm) for pm in poly_markets]
        await asyncio.gather(*tasks)

        # 3. Final Statistical Summary
        print("\n>> [4/4] FINAL STATISTICAL SUMMARY")
        print("="*60)
        print(f"   Total Polymarket Entries: {len(poly_markets)}")
        print(f"   Total Betfair Events:     {len(bf_events)}")
        print(f"   Total Matches Found:      {self.stats['matches_found']}")
        if len(poly_markets) > 0:
            print(f"   Global Success Rate:      {self.stats['matches_found']/len(poly_markets):.1%}")

        print("\n   MATCHES BY SPORT:")
        for s in ['soccer', 'basketball', 'tennis', 'baseball', 'politics']:
            matched = self.stats['by_sport'][s]
            fetched = self.stats['fetched_by_sport'][s]
            poly = self.stats['poly_by_sport'][s]
            if fetched > 0 or matched > 0 or poly > 0:
                print(f"   - {s.upper():<12}: {matched} matched / {fetched} fetched (PM: {poly})")
        print("="*60)
        print(f"   Total Polymarket Entries: {self.stats['total_poly_markets']}")
        print(f"   Total Betfair Events:     {self.stats.get('total_bf_events', 0)}")
        print(f"   Total SX Bet Events:      {self.stats.get('total_sx_events', 0)}")
        print(f"   Total Matches Found:      {self.stats['matches_found']}")
        
        # Break down matches by exchange
        exch_counts = defaultdict(int)
        for m in mappings:
            exch_counts[m.exchange] += 1
        
        print(f"\n   MATCHES BY EXCHANGE:")
        for exch, count in exch_counts.items():
            print(f"   - {exch.upper():<12}: {count}")

        print("\n   MATCHES BY SPORT (CONSOLIDATED):")
        for sport, count in sorted(self.stats["by_sport"].items(), key=lambda x: x[1], reverse=True):
            fetched = self.stats["fetched_by_sport"].get(sport, 0)
            print(f"   - {sport.upper().ljust(12)}: {count} matched / {fetched} fetched")

        print("\n   SCORECARDS BY SOURCE & MARKET TYPE:")
        for exchange, market_stats in self.stats["scorecards"].items():
            print(f"   {exchange.upper()}:")
            for market_type, stats in sorted(market_stats.items(), key=lambda x: x[0]):
                if stats["fetched"] or stats["matched"]:
                    print(f"     - {market_type:<20}: {stats['matched']} matched / {stats['fetched']} fetched")
        if opportunities:
            print("\n   💰💰💰 PROFITABLE OPPORTUNITIES (ROI > 0%) 💰💰💰")
            print("   " + "="*57)
            print(f"   {'POLYMARKET':<30} | {'EXCHANGE':<20} | {'ROI':<6}")
            print("   " + "-"*57)
            for opp in sorted(opportunities, key=lambda x: x['roi'], reverse=True):
                 # Truncate names
                 p_name = (opp['poly'][:28] + '..') if len(opp['poly']) > 28 else opp['poly']
                 e_name = (opp['exchange'][:18] + '..') if len(opp['exchange']) > 18 else opp['exchange']
                 print(f"   {p_name:<30} | {e_name:<20} | {opp['roi']:.2f}%")
            print("   " + "="*57 + "\n")
        else:
             print("\n   💰 No immediate profitable opportunities found (Market Efficient).")

        print("="*60 + "\n")

        # --- 5. GRAPH ENGINE: ORPHAN RESOLUTION ---
        try:
            from src.data.mining.graph_resolution_engine import GraphResolutionEngine
            
            # 1. Identify unmatched Poly events
            # mappings contains successful mappings
            matched_ids = {m.polymarket_id for m in mappings}
            unmatched_poly = [p for p in poly_markets if str(p.get('id','')) not in matched_ids and str(p.get('condition_id','')) not in matched_ids]
            
            # 2. Identify unmatched Exchange events (optional, for negative mining)
            # For now, pass ALL exchange events as candidates for graph
            
            if unmatched_poly:
                print(f"\n>> [5/5] ACTIVATING GRAPH RESOLUTION ENGINE ({len(unmatched_poly)} orphans)...")
                engine = GraphResolutionEngine()
                engine.resolve(unmatched_poly, all_exchange_events)
            else:
                print("\n>> [5/5] GRAPH ENGINE STANDBY: No orphans found (100% Match Rate!)")
                
        except Exception as e:
            print(f"!! GRAPH ENGINE ERROR: {e}")
            import traceback
            traceback.print_exc()
        
        print("="*60 + "\n")

async def run_mega_audit():
    audit = MegaAudit()
    try:
        await audit.run()
    finally:
        # CRITICAL: Persist any new knowledge gained during the audit (Vectors/AI)
        if hasattr(audit, 'mapper') and hasattr(audit.mapper, 'resolver'):
            print(">> [PERSISTENCE] Saving learned mappings to disk...")
            audit.mapper.resolver.save_mappings()
            
        await audit.gamma.close() if hasattr(audit.gamma, 'close') else None
        await audit.bf.logout()
        await audit.sx.close()

if __name__ == "__main__":
    asyncio.run(run_mega_audit())
