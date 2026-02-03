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
from datetime import datetime
from enum import Enum

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
    label: str
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
            
            try:
                async with session.get(f"{self.BASE_URL}/markets/active", timeout=15) as response:
                    self.stats['api_calls'] += 1
                    
                    if response.status != 200:
                        logger.error(f"SX Bet API error: {response.status}")
                        return []
                    
                    data = await response.json()
                    markets = data.get("data", {}).get("markets", [])
                    
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
            
            # Parse game time
            game_time = None
            if m.get('gameTime'):
                try:
                    game_time = datetime.fromisoformat(str(m.get('gameTime')).replace('Z', '+00:00'))
                except:
                    pass
            
            sx_market = SXBetMarket(
                market_hash=market_hash,
                label=label,
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
                                     sx_markets: List[SXBetMarket]) -> List[Dict]:
        """
        Find markets that exist on both platforms.
        Uses fuzzy text matching on market questions/labels.
        
        TODO: Integrate LLM matching from cross_platform_mapper.py
        """
        matches = []
        
        for poly in poly_markets:
            poly_question = poly.get('question', '').lower()
            poly_id = poly.get('condition_id', '')
            
            for sx in sx_markets:
                sx_label = sx.label.lower()
                
                # Simple keyword matching (can be improved with LLM)
                # Check for common terms
                poly_terms = set(poly_question.split())
                sx_terms = set(sx_label.split())
                
                common = poly_terms.intersection(sx_terms)
                
                # If more than 2 common significant words
                if len(common) >= 2:
                    # Filter out common words
                    common = {w for w in common if len(w) > 3}
                    
                    if len(common) >= 1:
                        matches.append({
                            'poly_id': poly_id,
                            'poly_question': poly.get('question', ''),
                            'poly_yes_price': float(poly.get('tokens', [{}])[0].get('price', 0.5)),
                            'sx_hash': sx.market_hash,
                            'sx_label': sx.label,
                            'sx_best_bid': sx.best_bid,
                            'sx_best_ask': sx.best_ask,
                            'common_terms': list(common)
                        })
        
        self.stats['matches_found'] += len(matches)
        return matches
    
    def calculate_arbitrage(self, 
                            poly_yes: float, 
                            sx_bid: float, 
                            sx_ask: float) -> Dict:
        """
        Calculate if arbitrage exists between platforms.
        
        Scenario 1: Buy YES on Poly, Sell YES on SX
            Profit if: Poly_YES < SX_BID
            
        Scenario 2: Buy NO on Poly (1-YES), Buy YES on SX
            Profit if: (1-Poly_YES) + SX_ASK < 1
            Simplified: Poly_YES > SX_ASK
        """
        arb = {
            'has_opportunity': False,
            'direction': None,
            'expected_profit_pct': 0.0
        }
        
        # Scenario 1: Poly YES cheaper than SX bid
        if poly_yes < sx_bid and sx_bid > 0:
            spread = sx_bid - poly_yes
            arb = {
                'has_opportunity': True,
                'direction': 'buy_poly_sell_sx',
                'expected_profit_pct': spread * 100,
                'poly_action': 'BUY YES',
                'sx_action': 'SELL YES (take bid)',
                'buy_price': poly_yes,
                'sell_price': sx_bid
            }
        
        # Scenario 2: SX YES cheaper than implied by Poly
        elif sx_ask < poly_yes and sx_ask > 0:
            spread = poly_yes - sx_ask
            arb = {
                'has_opportunity': True,
                'direction': 'buy_sx_sell_poly',
                'expected_profit_pct': spread * 100,
                'poly_action': 'BUY NO (sell YES)',
                'sx_action': 'BUY YES',
                'buy_price': sx_ask,
                'sell_price': poly_yes
            }
        
        return arb
    
    async def scan(self, 
                   poly_markets: List[Dict],
                   sx_category: SXBetCategory = SXBetCategory.ALL) -> List[Dict]:
        """
        Scan for arbitrage opportunities between platforms.
        
        Args:
            poly_markets: List of Polymarket markets (from GammaAPIClient)
            sx_category: SX Bet category to filter
            
        Returns:
            List of arbitrage opportunities
        """
        self.stats['scans'] += 1
        
        # Get SX markets with liquidity
        sx_markets_with_liquidity = await self.sx.get_markets_with_liquidity(
            category=sx_category,
            min_liquidity=50.0
        )
        
        sx_markets = [m for m, _ in sx_markets_with_liquidity]
        
        # Find matching markets
        matches = await self.find_matching_markets(poly_markets, sx_markets)
        
        opportunities = []
        
        for match in matches:
            arb = self.calculate_arbitrage(
                poly_yes=match['poly_yes_price'],
                sx_bid=match['sx_best_bid'],
                sx_ask=match['sx_best_ask']
            )
            
            if arb['has_opportunity'] and arb['expected_profit_pct'] >= self.min_spread * 100:
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
