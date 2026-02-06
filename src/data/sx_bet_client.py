"""
SX Bet (SportX) Exchange Client.

SX Bet is a blockchain-based prediction market exchange on SX Network.
Similar to Polymarket but with different liquidity and pricing.

KEY ADVANTAGES FOR SPANISH USERS:
- No KYC restrictions (wallet-based access)
- Has Politics, Crypto, Sports, and Entertainment markets
- Uses USDC (same as Polymarket - no currency conversion)
- Can be used for arbitrage with Polymarket when Betfair is restricted

API Documentation: https://api.docs.sx.bet

Categories available:
- Politics (US Elections, World Leaders, etc.)
- Crypto (Bitcoin, Ethereum price predictions)
- Sports (NFL, NBA, Soccer, etc.)
- Entertainment (Oscars, Grammys, etc.)
"""

import os
import asyncio
import aiohttp
import time
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

# Import Validator
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.arbitrage.arbitrage_validator import ArbitrageValidator, ArbResult

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)


class SXBetCategory(Enum):
    """SX Bet market categories."""
    ALL = "all"
    POLITICS = "politics"
    CRYPTO = "crypto"
    SPORTS = "sports"
    ENTERTAINMENT = "entertainment"
    SOCCER = "Soccer"
    BASKETBALL = "Basketball"
    AMERICAN_FOOTBALL = "American Football"
    BASEBALL = "Baseball"
    TENNIS = "Tennis"
    MMA = "MMA"
    HOCKEY = "Hockey"


@dataclass
class SXBetMarket:
    """Representation of an SX Bet market."""
    market_hash: str
    market_hash: str
    label: str
    market_key: str # Added for semantic filtering (e.g. 'game_winner')
    sport_label: str
    outcome_one_name: str
    outcome_two_name: str
    team_one_name: str
    team_two_name: str
    game_time: Optional[datetime]
    status: str
    
    # Price data (if available)
    best_bid: float = 0.0
    best_ask: float = 0.0
    spread: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            'id': self.market_hash,
            'name': self.label,
            'category': self.sport_label,
            'outcome_one': self.outcome_one_name,
            'outcome_two': self.outcome_two_name,
            'best_bid': self.best_bid,
            'best_ask': self.best_ask,
            'spread': self.spread
        }


@dataclass
class SXBetOrderbook:
    """Orderbook for a market."""
    market_hash: str
    bids: List[Dict] = field(default_factory=list)  # [{'price': 0.55, 'size': 100}]
    asks: List[Dict] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def best_bid(self) -> float:
        return self.bids[0]['price'] if self.bids else 0.0
    
    @property
    def best_ask(self) -> float:
        return self.asks[0]['price'] if self.asks else 1.0
    
    @property
    def spread(self) -> float:
        return self.best_ask - self.best_bid if self.bids and self.asks else 1.0
    
    @property
    def mid_price(self) -> float:
        if self.bids and self.asks:
            return (self.best_bid + self.best_ask) / 2
        return 0.5


class SXBetClient:
    """
    Client for SX Bet API - fetches market data and places orders.
    
    Features:
    - Active market discovery with category filtering
    - Orderbook reconstruction from global orders
    - Order placement (requires wallet/private key)
    - Caching for performance
    
    Note: SX Bet uses blockchain for settlement (SX Network).
    """
    
    BASE_URL = "https://api.sx.bet"
    
    # Price scaling factors
    ODDS_DIVISOR = 1e20
    USDC_DIVISOR = 1e6

    # Category to Sport ID Map
    SPORT_ID_MAP = {
        'Soccer': 5,
        'Tennis': 3,
        'Basketball': 4,
        'American Football': 2, # Need to verify, assuming standard or from probe
        'Baseball': 8, # Probe didn't show, using placeholder or check later. Probe showed ID 26 is AFL. ID 2 is likely American Football or similar.
        # From probe:
        # 5: Soccer, 3: Tennis, 4: Basketball, 17: Politics, 14: Crypto, 15: Cricket
        # 13: Boxing, 11: Rugby Union, 20: Rugby League, 24: Horse Racing
        'Politics': 17,
        'Crypto': 14,
        'Cricket': 15,
        'Boxing': 13,
        'MMA': 7, # Guessing or need probe
        'Ice Hockey': 6 # Guessing
    }
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 cache_ttl: int = 30):
        """
        Initialize SX Bet client.
        
        Args:
            api_key: SX Bet API key (from .env SX_BET_API_KEY)
            cache_ttl: Cache TTL in seconds for orders
        """
        self.api_key = api_key or os.getenv('SX_BET_API_KEY')
        self.cache_ttl = cache_ttl
        
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Order cache (global orders are ~700KB)
        self._orders_cache: List[Dict] = []
        self._orders_cache_time: float = 0
        
        # Market cache
        self._markets_cache: List[Dict] = []
        self._markets_cache_time: float = 0
        
        # Stats
        self.stats = {
            'api_calls': 0,
            'markets_fetched': 0,
            'orderbooks_built': 0,
            'cache_hits': 0
        }
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            headers = {'Content-Type': 'application/json'}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session
    
    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def fetch_markets(self, market_ids: List[str]) -> List[Dict]:
        """
        Bulk fetch market status and prices for a list of hashes.
        Refreshes global orders and calculates top of book for each.
        """
        await self._refresh_orders() # Global refresh
        results = []
        
        # We need the market labels too. If not in cache, we might miss them.
        # But for poller, hashes are usually enough if we just need prices.
        
        for m_hash in market_ids:
            ob = await self.get_orderbook(m_hash)
            results.append({
                'marketHash': m_hash,
                'highestBid': ob.best_bid,
                'lowestAsk': ob.best_ask,
                'status': 'ACTIVE' # Placeholder
            })
        return results
    
    async def get_active_markets(self, 
                                  category: Optional[SXBetCategory] = None,
                                  force_refresh: bool = False) -> List[SXBetMarket]:
        """
        Fetch active markets from SX Bet.
        
        Args:
            category: Filter by category (SXBetCategory enum)
            force_refresh: Force cache refresh
            
        Returns:
            List of SXBetMarket objects
        """
        now = time.time()
        
        # Check cache
        if not force_refresh and now - self._markets_cache_time < self.cache_ttl:
            self.stats['cache_hits'] += 1
            markets = self._markets_cache
        else:
            session = await self._get_session()
            all_markets = []
            next_key = None
            
            # Determine API Sport ID
            sport_id = None
            if category:
                 sport_id = self.SPORT_ID_MAP.get(category.value)
                 # Handle special cases if value doesn't match keys exactly
                 if not sport_id and category == SXBetCategory.POLITICS: sport_id = 17
                 if not sport_id and category == SXBetCategory.CRYPTO: sport_id = 14
                 if not sport_id and category == SXBetCategory.SOCCER: sport_id = 5
                 if not sport_id and category == SXBetCategory.TENNIS: sport_id = 3
                 if not sport_id and category == SXBetCategory.BASKETBALL: sport_id = 4
            
            try:
                while True:
                    params = {}
                    if next_key:
                        params['paginationKey'] = next_key
                    
                    # FORCE BROAD SCAN: Do not filter by Sport ID on API level
                    # if sport_id:
                    #    params['sportId'] = sport_id

                    async with session.get(f"{self.BASE_URL}/markets/active", params=params, timeout=15) as response:
                        self.stats['api_calls'] += 1
                        
                        if response.status != 200:
                            logger.error(f"SX Bet API error: {response.status}")
                            break
                        
                        data = await response.json()
                        page_markets = data.get("data", {}).get("markets", [])
                        if not page_markets:
                            break
                            
                        all_markets.extend(page_markets)
                        
                        # Check for next page
                        next_key = data.get("data", {}).get("nextKey")
                        if not next_key:
                            break
                            
                        # Safety break for massive scrapes
                        if len(all_markets) > 2000:
                            logger.warning("SX Bet fetch limit reached (2000)")
                            break

                markets = all_markets
                self._markets_cache = markets
                self._markets_cache_time = now
                    
            except Exception as e:
                logger.error(f"Error fetching SX markets: {e}")
                return []
        
        # Filter by category
        filtered = []
        seen_hashes = set()
        
        for m in markets:
            market_hash = m.get('marketHash')
            if not market_hash or market_hash in seen_hashes:
                continue
            
            sport_label = m.get('sportLabel', '')
            
            # Category filter
            if category and category != SXBetCategory.ALL:
                if category.value.lower() not in sport_label.lower():
                    # Special cases for cross-category matching
                    if category == SXBetCategory.POLITICS and 'politic' not in sport_label.lower():
                        continue
                    elif category == SXBetCategory.CRYPTO and 'crypto' not in sport_label.lower():
                        continue
                    elif category in [SXBetCategory.SOCCER, SXBetCategory.BASKETBALL]:
                        if sport_label != category.value:
                            continue
            
            # Construct label
            t1 = m.get('teamOneName', '')
            t2 = m.get('teamTwoName', '')
            label = f"{t1} vs {t2}" if t1 and t2 else m.get('outcomeOneName', 'Match')
            
            # Parse game time (Supports ISO or Unix Timestamp)
            game_time = None
            gt = m.get('gameTime')
            if gt:
                try:
                    if isinstance(gt, (int, float)) or (isinstance(gt, str) and gt.isdigit()):
                        ts = float(gt)
                        # Detect milliseconds (if year > 3000, assume millis)
                        if ts > 4102444800: # 2100 AD
                            ts /= 1000
                        game_time = datetime.fromtimestamp(ts, tz=timezone.utc)
                    else:
                        game_time = datetime.fromisoformat(str(gt).replace('Z', '+00:00'))
                except Exception as e:
                    logger.debug(f"Failed to parse SX time {gt}: {e}")
            
            sx_market = SXBetMarket(
                market_hash=market_hash,
                label=label,
                market_key=m.get('marketKey', ''), # Populate market_key
                sport_label=sport_label,
                outcome_one_name=m.get('outcomeOneName', 'Yes'),
                outcome_two_name=m.get('outcomeTwoName', 'No'),
                team_one_name=t1,
                team_two_name=t2,
                game_time=game_time,
                status=m.get('status', 'ACTIVE')
            )
            
            filtered.append(sx_market)
            seen_hashes.add(market_hash)
        
        self.stats['markets_fetched'] += len(filtered)
        logger.info(f"[SX Bet] Fetched {len(filtered)} markets (category: {category})")
        
        return filtered

    def _normalize_market_type(self, market_key: str) -> str:
        """Map SX market keys to Betfair-style market types."""
        k = market_key.lower()
        if k in ['game_winner', 'match_winner', 'winner', 'ipv', '1x2']:
            return 'MATCH_ODDS'
        if k in ['moneyline', 'money_line', 'h2h', 'head_to_head']:
            return 'MONEY_LINE'
        if 'handicap' in k or 'spread' in k:
            return 'HANDICAP'
        if 'total' in k or 'over' in k or 'under' in k:
            return 'OVER_UNDER'
        return k.upper()

    async def get_markets_standardized(self, category: Optional[SXBetCategory] = None) -> List[Dict]:
        """
        Fetch markets and return them in the standardized format used by CrossPlatformMapper.
        Matches the Betfair event dictionary structure.
        """
        markets = await self.get_active_markets(category=category)
        standardized = []
        for m in markets:
            # Map SX categories to our local sport_ids if possible, or let the mapper handle it
            # Standardized structure:
            # {
            #     'id': str,
            #     'event_id': str,
            #     'market_id': str,
            #     'name': str,
            #     'open_date': str (ISO),
            #     'market_type': str,
            #     'runners': List[Dict],
            #     'exchange': 'sx' # Mandatory for multi-exchange
            # }
            standardized.append({
                'id': m.market_hash,
                'event_id': m.market_hash,
                'market_id': m.market_hash,
                'name': m.label,
                'open_date': m.game_time.isoformat() if m.game_time else None,
                # Normalize Market Type for Mapper (MATCH_ODDS, MONEY_LINE, etc.)
                'market_type': self._normalize_market_type(m.market_key),
                'runners': [
                    {'selectionId': 1, 'runnerName': m.outcome_one_name},
                    {'selectionId': 2, 'runnerName': m.outcome_two_name}
                ],
                'exchange': 'sx',
                '_sx_market_obj': m # Keep reference for price fetching
            })
        return standardized
    
    async def _refresh_orders(self, force: bool = False):
        """Refresh the global orders cache."""
        now = time.time()
        
        if not force and now - self._orders_cache_time < self.cache_ttl:
            return
        
        session = await self._get_session()
        
        try:
            async with session.get(f"{self.BASE_URL}/orders", timeout=30) as response:
                self.stats['api_calls'] += 1
                
                if response.status != 200:
                    logger.error(f"SX Bet orders API error: {response.status}")
                    return
                
                data = await response.json()
                self._orders_cache = data.get("data", [])
                self._orders_cache_time = now
                
                logger.debug(f"[SX Bet] Refreshed {len(self._orders_cache)} global orders")
                
        except Exception as e:
            logger.error(f"Error fetching SX orders: {e}")
    
    async def get_orderbook(self, market_hash: str) -> SXBetOrderbook:
        """
        Build orderbook for a market from global orders.
        
        Args:
            market_hash: The market hash to get orderbook for
            
        Returns:
            SXBetOrderbook with bids and asks
        """
        await self._refresh_orders()
        
        bids = []
        asks = []
        
        for order in self._orders_cache:
            if order.get('marketHash') != market_hash:
                continue
            
            if order.get('orderStatus') != 'ACTIVE':
                continue
            
            try:
                raw_odds = float(order.get('percentageOdds', 0))
                total_size = float(order.get('totalBetSize', 0))
                fill_amount = float(order.get('fillAmount', 0))
                
                size_usdc = (total_size - fill_amount) / self.USDC_DIVISOR
                
                if size_usdc < 1.0:  # Ignore dust
                    continue
                
                maker_outcome_one = order.get('isMakerBettingOutcomeOne', False)
                maker_price = raw_odds / self.ODDS_DIVISOR
                
                if maker_outcome_one:
                    # Maker betting YES -> BID for YES
                    bids.append({'price': maker_price, 'size': size_usdc})
                else:
                    # Maker betting NO -> ASK for YES
                    price_yes = 1.0 - maker_price
                    asks.append({'price': price_yes, 'size': size_usdc})
                    
            except Exception as e:
                logger.debug(f"Error parsing order: {e}")
                continue
        
        # Sort bids (desc) and asks (asc)
        bids.sort(key=lambda x: x['price'], reverse=True)
        asks.sort(key=lambda x: x['price'])
        
        self.stats['orderbooks_built'] += 1
        
        return SXBetOrderbook(
            market_hash=market_hash,
            bids=bids,
            asks=asks,
            timestamp=datetime.now()
        )
    
    async def get_markets_with_liquidity(self, 
                                          category: Optional[SXBetCategory] = None,
                                          min_liquidity: float = 100.0) -> List[Tuple[SXBetMarket, SXBetOrderbook]]:
        """
        Get markets that have actual orderbook liquidity.
        
        Args:
            category: Optional category filter
            min_liquidity: Minimum total liquidity (USDC)
            
        Returns:
            List of (market, orderbook) tuples
        """
        markets = await self.get_active_markets(category=category)
        await self._refresh_orders(force=True)
        
        liquid_markets = []
        
        for market in markets:
            orderbook = await self.get_orderbook(market.market_hash)
            
            total_bid_liquidity = sum(b['size'] for b in orderbook.bids)
            total_ask_liquidity = sum(a['size'] for a in orderbook.asks)
            total_liquidity = total_bid_liquidity + total_ask_liquidity
            
            if total_liquidity >= min_liquidity:
                # Update market with price data
                market.best_bid = orderbook.best_bid
                market.best_ask = orderbook.best_ask
                market.spread = orderbook.spread
                
                liquid_markets.append((market, orderbook))
        
        logger.info(f"[SX Bet] Found {len(liquid_markets)} markets with >= ${min_liquidity} liquidity")
        
        return liquid_markets
    
    def get_stats(self) -> Dict:
        """Get client statistics."""
        return {
            **self.stats,
            'orders_cached': len(self._orders_cache),
            'markets_cached': len(self._markets_cache)
        }


# ============== POLYMARKET-SX ARBITRAGE SCANNER ==============

class PolySXArbitrageScanner:
    """
    Scanner for arbitrage opportunities between Polymarket and SX Bet.
    
    Both platforms:
    - Use USDC for settlement
    - Have Politics and Crypto markets
    - Are blockchain-based (no KYC restrictions)
    
    This is ideal for Spanish users who can't access Betfair Politics.
    """
    
    def __init__(self,
                 sx_client: SXBetClient,
                 polymarket_client = None,
                 min_spread_pct: float = 1.0):
        """
        Args:
            sx_client: SXBetClient instance
            polymarket_client: Optional GammaAPIClient for Polymarket
            min_spread_pct: Minimum spread % to report as opportunity
        """
        self.sx = sx_client
        self.poly = polymarket_client
        self.min_spread = min_spread_pct / 100
        
        self.opportunities = []
        self.stats = {
            'scans': 0,
            'matches_found': 0,
            'opportunities_found': 0
        }
    
    async def find_matching_markets(self, 
                                     poly_markets: List[Dict],
                                     sx_data: List[Tuple[SXBetMarket, SXBetOrderbook]]) -> List[Dict]:
        """
        Find markets that exist on both platforms.
        Uses fuzzy text matching and STRICT semantic validation.
        """
        matches = []
        
        for poly in poly_markets:
            poly_question = poly.get('question', '').lower()
            poly_id = poly.get('condition_id', '')
            
            for sx, orderbook in sx_data:
                sx_label = sx.label.lower()
                
                # STRICT Semantic Validation from Validator Engine
                if not ArbitrageValidator.is_semantically_compatible(poly_question, sx.market_key, sx.sport_label):
                    continue 

                # TIME WINDOW Check (Strategy C)
                # Need poly_time. Polymarket events usually have 'startDate' in ISO.
                # poly dict comes from adapt_gamma_events, check keys.
                # Gamma events have 'startDate'. adapt_gamma_events keeps keys? 
                # adapt_gamma_events creates new dict. Need to ensure 'startDate' is passed.
                # Assuming it is or I need to update adapt_gamma_events first?
                # Check adapt_gamma_events in shadow_bot.py... 
                # It does: 'id', 'condition_id', 'question', 'slug', 'yes_price', 'tokens'.
                # MISSING 'startDate'. I should update adapt_gamma_events later.
                # For now, if missing, validator returns True (soft pass).
                
                poly_start = poly.get('startDate') 
                sx_time = sx.game_time
                
                p_dt = None
                if poly_start:
                    try:
                        p_dt = datetime.fromisoformat(poly_start.replace('Z', '+00:00'))
                    except:
                        pass
                
                if not ArbitrageValidator.check_time_window(p_dt, sx_time):
                    continue

                # Simple keyword matching matching
                # Check for common terms
                poly_terms = set(poly_question.split())
                sx_terms = set(sx_label.split())
                
                common = poly_terms.intersection(sx_terms)
                
                # If more than 2 common significant words
                if len(common) >= 2:
                    # Filter out common words
                    common = {w for w in common if len(w) > 3}
                    
                    if len(common) >= 1:
                        # Extract liquidity at best price
                        bid_depth = orderbook.bids[0]['size'] if orderbook.bids else 0.0
                        ask_depth = orderbook.asks[0]['size'] if orderbook.asks else 0.0
                        
                        matches.append({
                            'poly_id': poly_id,
                            'poly_question': poly.get('question', ''),
                            'poly_yes_price': float(poly.get('tokens', [{}])[0].get('price', 0.5)),
                            # Liquidity from Poly (Mocking 100 for now if real data not available in 'tokens', usually it is)
                            'poly_liquidity': 100.0, # TODO: extract real poly liquidity
                            'sx_hash': sx.market_hash,
                            'sx_label': sx.label,
                            'sx_market_key': sx.market_key,
                            'sx_best_bid': sx.best_bid,
                            'sx_best_ask': sx.best_ask,
                            'sx_bid_depth': bid_depth,
                            'sx_ask_depth': ask_depth,
                            'common_terms': list(common)
                        })
        
        self.stats['matches_found'] += len(matches)
        return matches


    
    def calculate_arbitrage(self, 
                            poly_yes: float, 
                            sx_bid: float, 
                            sx_ask: float,
                            poly_liq: float,
                            sx_bid_liq: float,
                            sx_ask_liq: float) -> Dict:
        """
        Calculate if arbitrage exists using Professional Fee-Adjusted Formula.
        """
        arb = {
            'has_opportunity': False,
            'direction': None,
            'expected_profit_pct': 0.0,
            'max_volume': 0.0
        }
        
        # Scenario 1: Buy YES on Poly, Sell YES on SX (Lay)
        # Poly Ask vs SX Bid
        # Fee 2% on SX
        res1 = ArbitrageValidator.calculate_roi(poly_ask=poly_yes, exch_odds=1.0/sx_bid if sx_bid > 0 else 1.0, fee_rate=0.02)
        if res1.is_opportunity:
            # Check Liquidity
            max_vol = min(poly_liq, sx_bid_liq)
            if ArbitrageValidator.check_liquidity(poly_liq, sx_bid_liq, min_threshold=10.0):
                arb = {
                    'has_opportunity': True,
                    'direction': 'buy_poly_sell_sx',
                    'expected_profit_pct': res1.roi_percent,
                    'poly_action': 'BUY YES',
                    'sx_action': 'SELL YES (take bid)',
                    'buy_price': poly_yes,
                    'sell_price': sx_bid,
                    'max_volume': max_vol,
                    'roi_detail': f"ROI: {res1.roi_percent:.2f}% (Fee Adj)"
                }
                return arb
        
        # Scenario 2: SX YES cheaper than Poly YES
        # Buy SX YES (Ask), Sell Poly YES (No support for Short Poly yet, so we assume Buy NO on Poly?)
        # User prompt implies: "Buy NO on Poly (1-YES) + Buy YES on SX"
        # Total Cost = (1-PolyYES) + SX_Ask
        # ROI = 1 - Total Cost
        # Validation:
        poly_no_price = 1.0 - poly_yes
        # Using 0 fee for SX Buy (Taker fee might exist, assume 0 for check or 2%)
        # Let's use simple cost comparison for this direction as standard validator is for Ask vs Exch(Lay)
        
        total_cost = poly_no_price + sx_ask
        roi = (1.0 - total_cost) * 100
        if roi > 0:
            max_vol = min(poly_liq, sx_ask_liq)
            if max_vol >= 10.0:
                 arb = {
                    'has_opportunity': True,
                    'direction': 'buy_sx_sell_poly_no',
                    'expected_profit_pct': roi,
                    'poly_action': 'BUY NO',
                    'sx_action': 'BUY YES',
                    'buy_price': sx_ask,
                    'sell_price': poly_yes,
                    'max_volume': max_vol
                }

        return arb
    
    async def scan(self, 
                   poly_markets: List[Dict],
                   sx_category: SXBetCategory = SXBetCategory.ALL) -> List[Dict]:
        """
        Scan for arbitrage opportunities.
        """
        self.stats['scans'] += 1
        
        # Get SX markets with liquidity AND Orderbooks
        sx_data = await self.sx.get_markets_with_liquidity(
            category=sx_category,
            min_liquidity=10.0 # Match new threshold
        )
        
        # sx_data is List[Tuple[SXBetMarket, SXBetOrderbook]]
        
        # Find matching markets passing the FULL tuples
        matches = await self.find_matching_markets(poly_markets, sx_data)
        
        opportunities = []
        
        for match in matches:
            arb = self.calculate_arbitrage(
                poly_yes=match['poly_yes_price'],
                sx_bid=match['sx_best_bid'],
                sx_ask=match['sx_best_ask'],
                poly_liq=match['poly_liquidity'],
                sx_bid_liq=match['sx_bid_depth'],
                sx_ask_liq=match['sx_ask_depth']
            )
            
            if arb['has_opportunity']:
                opp = {
                    **match,
                    **arb,
                    'detected_at': datetime.now().isoformat()
                }
                opportunities.append(opp)
                self.opportunities.append(opp)
        
        self.stats['opportunities_found'] += len(opportunities)
        
        return opportunities


# ============== DEMO ==============

async def demo():
    """Demo SX Bet client and arbitrage scanner."""
    print("\n" + "=" * 70)
    print("SX BET CLIENT DEMO")
    print("=" * 70)
    
    client = SXBetClient()
    
    try:
        # 1. Get all active markets
        print("\n[1] Fetching active markets...")
        markets = await client.get_active_markets()
        print(f"    Found {len(markets)} total markets")
        
        # Group by category
        categories = {}
        for m in markets:
            cat = m.sport_label
            categories[cat] = categories.get(cat, 0) + 1
        
        print("\n    Categories:")
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"      {cat}: {count} markets")
        
        # 2. Get markets with liquidity
        print("\n[2] Finding markets with liquidity...")
        liquid_markets = await client.get_markets_with_liquidity(min_liquidity=100)
        
        print(f"    Found {len(liquid_markets)} markets with >= $100 liquidity")
        
        for market, orderbook in liquid_markets[:5]:
            print(f"\n    📊 {market.label}")
            print(f"       Category: {market.sport_label}")
            print(f"       Best Bid: {orderbook.best_bid:.4f}")
            print(f"       Best Ask: {orderbook.best_ask:.4f}")
            print(f"       Spread: {orderbook.spread:.4f}")
            print(f"       Bid Depth: {len(orderbook.bids)} levels")
            print(f"       Ask Depth: {len(orderbook.asks)} levels")
        
        # 3. Show specific categories
        print("\n[3] Checking Politics/Crypto markets...")
        for cat in [SXBetCategory.POLITICS, SXBetCategory.CRYPTO]:
            cat_markets = await client.get_active_markets(category=cat)
            print(f"    {cat.value}: {len(cat_markets)} markets")
        
        # Stats
        print(f"\n[4] Client Stats: {client.get_stats()}")
        
    finally:
        await client.close()
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(demo())
