import asyncio
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from thefuzz import fuzz
from src.exchanges.sx_bet_client import SXBetClient
from src.collectors.polymarket import PolymarketClient
from src.utils.normalization import normalize_text
from src.utils.cache_manager import CacheManager
import math

class ArbitrageDetector:
    """
    Detects arbitrage opportunities between Polymarket and SX Bet.
    Matches events and calculates profit potential using Market Depth.
    """
    
    def __init__(self, min_profit_percent: float = 3.0):
        self.min_profit_percent = min_profit_percent
        self.polymarket_client = PolymarketClient()
        self.sx_bet_client = SXBetClient()
        # Use output directory for persistence across container restarts
        self.cache = CacheManager(db_path="output/signals.db")
        self.min_liquidity = 200.0 # Minimum liquidity in USD required to validate signal
        self.gas_cost_estimate = 1.0 # Estimated Gas cost in USD (fixed for now)

    async def fetch_all_markets(self) -> Tuple[List[Dict], List[Dict]]:
        """Fetch markets from both platforms concurrently"""
        poly_task = self.polymarket_client.search_events_async()
        sx_task = self.sx_bet_client.get_active_markets()
        
        poly_markets, sx_markets = await asyncio.gather(poly_task, sx_task)
        
        print(f"Fetched {len(poly_markets)} Polymarket + {len(sx_markets)} SX Bet markets")
        
        # Debug: Show sample titles
        if poly_markets:
            print(f"  Sample Poly: {poly_markets[0].get('title', 'N/A')[:50]}")
        if sx_markets:
            print(f"  Sample SX: {sx_markets[0].get('label', 'N/A')[:50]}")
        
        return poly_markets, sx_markets
    
    def match_events(self, poly_markets: List[Dict], sx_markets: List[Dict]) -> List[Tuple[Dict, Dict]]:
        """
        Match events between platforms using fuzzy matching.
        """
        matches = []
        near_misses = []  # For debugging
        
        # Pre-normalize SX labels
        sx_prepared = []
        for sx in sx_markets:
            label = sx.get("label", "")
            if not label: continue
            sx_prepared.append({
                "norm": normalize_text(label),
                "original": sx
            })

        for poly_event in poly_markets:
            poly_title = normalize_text(poly_event.get("title", ""))
            if not poly_title: continue
            
            best_score = 0
            best_sx = None
            
            for sx_item in sx_prepared:
                score = fuzz.token_sort_ratio(poly_title, sx_item["norm"])
                
                if score > best_score:
                    best_score = score
                    best_sx = sx_item["original"]
            
            # Lower threshold to 70% to capture more potential matches
            if best_score > 70 and best_sx:
                matches.append((poly_event, best_sx))
            elif best_score > 50 and best_sx:
                near_misses.append((poly_event.get("title", "")[:30], best_score))
        
        # Show top near-misses for debugging
        if near_misses and not matches:
            near_misses.sort(key=lambda x: -x[1])
            print(f"  Top near-misses (50-70%): {near_misses[:3]}")
        
        return matches

    def _get_vwap(self, orders: List[Dict], needed_usd: float) -> Optional[float]:
        """
        Calculate Volume Weighted Average Price for a specific size.
        orders: list of {'price': float, 'size': float}
        """
        if not orders:
            return None
            
        filled_qty = 0.0
        total_cost = 0.0
        remaining_needed = needed_usd
        
        for order in orders:
            p = order['price']
            s = order['size']
            
            take = min(remaining_needed, s)
            filled_qty += take
            total_cost += (take * p)
            remaining_needed -= take
            
            if remaining_needed <= 0.0001:
                break
        
        if filled_qty < (needed_usd * 0.99): # Allow small epsilon
            return None # Not enough depth
            
        return total_cost / filled_qty

    async def calculate_arbitrage(self, poly_event: Dict, sx_event: Dict) -> Optional[Dict]:
        """
        Calculate arbitrage opportunity for matched events using Order Book Depth.
        """
        # 1. Identify Token IDs for Polymarket
        poly_markets = poly_event.get("markets", [])
        if not poly_markets: return None
        poly_market = poly_markets[0]
        
        raw_token_ids = poly_market.get("clobTokenIds", [])
        if isinstance(raw_token_ids, str):
            import json
            try: raw_token_ids = json.loads(raw_token_ids)
            except: pass
            
        if not raw_token_ids or len(raw_token_ids) != 2: return None
        
        # Helper to convert to decimal string
        def to_decimal(val):
            s = str(val)
            if s.startswith("0x"):
                return str(int(s, 16))
            return s
        
        # 2. Map Outcomes Robustly
        outcomes = poly_market.get("outcomes", [])
        if isinstance(outcomes, str):
            import json
            try: outcomes = json.loads(outcomes)
            except: pass
            
        yes_idx, no_idx = 0, 1
        
        # Strategy: Cross-reference SX outcome names with Poly outcomes
        sx_out1 = normalize_text(sx_event.get("outcomeOneName", ""))
        sx_out2 = normalize_text(sx_event.get("outcomeTwoName", ""))
        
        if len(outcomes) == 2:
            poly_out1 = normalize_text(outcomes[0])
            poly_out2 = normalize_text(outcomes[1])
            
            # If Poly uses Team Names instead of Yes/No
            if poly_out1 in [sx_out1, sx_out2] or poly_out2 in [sx_out1, sx_out2]:
                # We assume outcomes[0] is our primary target for 'yes_side'
                # unless it specifically matches the opponent.
                if poly_out1 == sx_out2: # Target is outcome 2
                     yes_idx, no_idx = 0, 1 # Still index 0 is our 'Yes' (Team A)
            
            # Standard Yes/No handling
            elif "no" in poly_out1 and "yes" in poly_out2:
                yes_idx, no_idx = 1, 0
                
        yes_token_id = to_decimal(raw_token_ids[yes_idx])
        no_token_id = to_decimal(raw_token_ids[no_idx])

        # 2. Fetch Depths concurrently
        sx_market_id = sx_event.get("marketHash")
        
        # Fetch Poly depths for YES and NO
        t1, t2, sx_book = await asyncio.gather(
            self.polymarket_client.get_orderbook_depth_async(yes_token_id),
            self.polymarket_client.get_orderbook_depth_async(no_token_id),
            self.sx_bet_client.get_orderbook(sx_market_id)
        )
        
        poly_yes_book = t1 # {'bids': [], 'asks': []}
        poly_no_book = t2
        
        # 3. Calculate Prices for Required Size
        size = self.min_liquidity
        
        # POLY Prices
        # To Buy YES: We hit Asks
        poly_buy_yes = self._get_vwap(poly_yes_book['asks'], size)
        # To Sell YES: We hit Bids
        poly_sell_yes = self._get_vwap(poly_yes_book['bids'], size)
        
        # SX Prices
        # To Buy YES: We hit Asks
        sx_buy_yes = self._get_vwap(sx_book['asks'], size)
        # To Sell YES: We hit Bids
        sx_sell_yes = self._get_vwap(sx_book['bids'], size)
        
        # Synthetic Prices (Buy NO == Sell YES)
        # If I Buy NO (hit Asks), I am effectively Selling YES at (1 - Price_NO).
        # Cost to Buy NO = P_no. Implied Sell YES Revenue = 1 - P_no.
        
        poly_buy_no = self._get_vwap(poly_no_book['asks'], size)
        if poly_buy_no:
            poly_sell_yes_synthetic = 1.0 - poly_buy_no
        else:
            poly_sell_yes_synthetic = None

        # 4. Evaluate Strategies
        strategies = []
        
        # Strat A: Buy Poly YES, Sell SX YES
        if poly_buy_yes and sx_sell_yes:
            profit_raw = sx_sell_yes - poly_buy_yes
            fees = 0.02 # Approx fees
            roi = (profit_raw - fees) / poly_buy_yes
            strategies.append({
                "name": "Buy Poly YES -> Sell SX YES",
                "buy_price": poly_buy_yes,
                "sell_price": sx_sell_yes,
                "roi": roi * 100,
                "poly_action": "buy_yes",
                "sx_action": "sell_yes",
                "poly_side": "buy_yes",
                "sx_side": "sell_yes",
                "poly_price": poly_buy_yes,
                "sx_price": sx_sell_yes
            })
            
        # Strat B: Buy SX YES, Sell Poly YES
        if sx_buy_yes and poly_sell_yes:
            profit_raw = poly_sell_yes - sx_buy_yes
            fees = 0.02 
            roi = (profit_raw - fees) / sx_buy_yes
            strategies.append({
                "name": "Buy SX YES -> Sell Poly YES",
                "buy_price": sx_buy_yes,
                "sell_price": poly_sell_yes,
                "roi": roi * 100,
                "poly_action": "sell_yes",
                "sx_action": "buy_yes",
                "poly_side": "sell_yes",
                "sx_side": "buy_yes",
                "poly_price": poly_sell_yes,
                "sx_price": sx_buy_yes
            })
            
        # Strat C: Hedge / Synthetic (Buy Poly YES, Buy SX NO)
        # Note: Buying SX NO is handled by SX Client: "Buy NO" orders are "Asks" for YES?
        # No, SX Client `get_orderbook` standardizes everything to YES.
        # "Asks" in SX Client = Liquidity offering to SELL YES (so we can BUY YES).
        # "Bids" in SX Client = Liquidity offering to BUY YES (so we can SELL YES).
        
        # If we want to "Buy SX NO", we look for "Maker Betting YES".
        # Maker Betting YES = Maker Buys YES = Maker offers to SELL NO.
        # This is complexity hidden by SX Client? 
        # Actually SX Client converts everything to "Price of YES".
        # If I want to Buy NO on SX, I am taking a position that pays 1 if NO.
        # In current abstraction, this is equivalent to Selling YES.
        # So "Sell SX YES" (hit Bids) is effectively "Buy SX NO".
        # Because SX Bids = Maker Betting YES (Maker Long YES). 
        # If I hit that Bid, I am Shorting YES (Long NO).
        # So Strat C is implicitly covered by Strat A.
        
        # 5. Filter and Select Best
        if not strategies:
            return None
            
        best = max(strategies, key=lambda x: x['roi'])
        
        if best['roi'] >= self.min_profit_percent:
            return {
                "poly_event": poly_event,
                "sx_event": sx_event,
                "strategy": best,
                "profit_percent": best['roi'],
                "poly_token": yes_token_id,
                "poly_price": best['poly_price'],
                "sx_price": best['sx_price']
            }
            
        return None
    
    async def scan_for_opportunities(self) -> List[Dict]:
        """
        Main scan function with Deduplication.
        """
        print(f"\n🔍 Scanning markets (Require ${self.min_liquidity} depth, >{self.min_profit_percent}% ROI)...")
        start_time = datetime.now()
        
        poly_markets, sx_markets = await self.fetch_all_markets()
        matches = self.match_events(poly_markets, sx_markets)
        print(f"Found {len(matches)} matched events")
        
        opportunities = []
        for poly_event, sx_event in matches:
            try:
                opp = await self.calculate_arbitrage(poly_event, sx_event)
                if opp:
                    # Check Cache
                    strat = opp['strategy']
                    event_id = poly_event.get("id") or poly_event.get("slug")
                    
                    should_send = self.cache.should_send_alert(
                        event_id=str(event_id),
                        strategy_name=strat['name'],
                        poly_market_id=opp['poly_token'],
                        sx_market_id=sx_event.get("marketHash"),
                        current_profit=opp['profit_percent']
                    )
                    
                    if should_send:
                        opportunities.append(opp)
                        print(f"💰 Valid Opportunity: {opp['profit_percent']:.2f}% on {poly_event.get('title')[:40]}")
                    else:
                        print(f"💤 Duplicate/Spam skipped: {poly_event.get('title')[:30]} ({opp['profit_percent']:.2f}%)")
                        
            except Exception as e:
                print(f"Error calculating match: {e}")
                continue
        
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n✅ Scan complete in {elapsed:.1f}s. Found {len(opportunities)} new opportunities.")
        
        # Cleanup cache
        self.cache.cleanup()
        
        return opportunities

    async def close(self):
        await self.sx_bet_client.close()
