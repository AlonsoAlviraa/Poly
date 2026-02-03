#!/usr/bin/env python3
"""
Gamma API Client for Polymarket Market Discovery.
Enhanced with advanced filtering, caching, and market scoring.
"""

import httpx
import logging
import time
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MarketFilters:
    """Filter criteria for market discovery."""
    min_volume_24h: float = 1000.0      # Minimum 24h volume ($)
    min_liquidity: float = 500.0         # Minimum total liquidity ($)
    max_spread_pct: float = 10.0         # Maximum bid-ask spread (%)
    min_activity_score: float = 0.0      # Minimum activity score
    exclude_resolved: bool = True        # Exclude resolved markets
    categories: Optional[List[str]] = None  # Filter by categories


class GammaAPIClient:
    """
    Client for Polymarket Gamma API.
    Used for market discovery, metadata, and event information.
    Enhanced with caching and advanced filtering.
    """
    
    BASE_URL = "https://gamma-api.polymarket.com"
    
    def __init__(self, timeout: float = 10.0, cache_ttl: int = 60):
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Dict] = {}
        self._last_fetch: Dict[str, float] = {}
        
    def _get_cached(self, key: str) -> Optional[Dict]:
        """Get cached response if still valid."""
        if key in self._cache:
            if time.time() - self._last_fetch.get(key, 0) < self.cache_ttl:
                return self._cache[key]
        return None
    
    def _set_cache(self, key: str, data: Dict):
        """Cache a response."""
        self._cache[key] = data
        self._last_fetch[key] = time.time()
        
    def get_markets(self, 
                    closed: Optional[bool] = False,
                    limit: int = 100,
                    offset: int = 0,
                    order: str = "volume",
                    ascending: bool = False,
                    tag_id: Optional[str] = None) -> List[Dict]:
        """
        Fetch markets from Gamma API with filtering.
        """
        cache_key = f"markets_{closed}_{limit}_{offset}_{order}_{ascending}_{tag_id}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        params = {
            "limit": limit,
            "offset": offset,
            "order": order,
            "ascending": str(ascending).lower()
        }
        
        if closed is not None:
            params["closed"] = str(closed).lower()
        
        if tag_id:
            params["tag_id"] = tag_id
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{self.BASE_URL}/markets", params=params)
                resp.raise_for_status()
                result = resp.json()
                self._set_cache(cache_key, result)
                return result
        except Exception as e:
            logger.error(f"Gamma API error: {e}")
            return []
    
    # ============================================================
    # MATCH EVENTS - THE PRO FILTER
    # ============================================================
    # Tag IDs discovered from Polymarket API research:
    # - 100639: "Game Bet" (individual match odds - THE KEY!)
    # - Series IDs: NBA=10345, EPL=10340, NFL=10339, UCL=10341
    
    TAG_GAME_BET = "100639"  # Magic filter for match bets only
    
    SERIES_IDS = {
        'nba': '10345',
        'premier_league': '10340', 
        'nfl': '10339',
        'champions_league': '10341',
        'la_liga': '10342',
        'serie_a': '10343',
        'bundesliga': '10344',
    }
    
    def get_match_events(self, 
                         series_id: Optional[str] = None,
                         limit: int = 200) -> List[Dict]:
        """
        🎯 Fetch ONLY match odds (No Futures) from Polymarket.
        
        This is the PRO filter that eliminates "Will X win 2026 World Cup?"
        and gives us only "Team A vs Team B" individual match bets.
        
        Args:
            series_id: Optional filter by league (use SERIES_IDS values)
            limit: Max events to fetch
            
        Returns:
            List of match events (not markets) with their question, outcomes, etc.
        """
        cache_key = f"match_events_{series_id}_{limit}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        # Use /events endpoint with tag filter
        params = {
            "tag_id": self.TAG_GAME_BET,  # THE CRITICAL FILTER
            "active": "true",
            "closed": "false",
            "order": "startDate",  # Closest matches first
            "ascending": "true",
            "limit": limit
        }
        
        if series_id:
            params["series_id"] = series_id
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{self.BASE_URL}/events", params=params)
                resp.raise_for_status()
                events = resp.json()
                
                logger.info(f"[Polymarket] 🎯 Found {len(events)} MATCH EVENTS (Game Bets only)")
                
                self._set_cache(cache_key, events)
                return events
        except Exception as e:
            logger.error(f"Gamma API events error: {e}")
            return []
    
    def get_all_match_markets(self, limit: int = 300) -> List[Dict]:
        """
        🎯 Fetch all Game Bet markets directly with pricing data.
        """
        logger.info(f"[Polymarket] Fetching Game Bets with tag_id={self.TAG_GAME_BET}...")
        
        # Fetch markets with the match tag
        raw_markets = self.get_markets(
            closed=False, 
            limit=limit, 
            order="volume", 
            tag_id=self.TAG_GAME_BET
        )
        
        logger.info(f"[Polymarket] Raw markets from API: {len(raw_markets)}")
        
        markets = []
        for m in raw_markets:
            # Handle outcomes/prices format
            outcomes = m.get('outcomes', [])
            prices = m.get('outcomePrices', [])
            
            # More robust parsing for outcomes/prices
            def smart_parse(val):
                import ast
                if not val: return []
                if isinstance(val, list):
                    if len(val) == 1 and isinstance(val[0], str):
                        return smart_parse(val[0])
                    # If it's already a list and not just one string inside, it's likely already parsed
                    return val
                
                if isinstance(val, str):
                    val = val.strip()
                    if not (val.startswith('[') or val.startswith('{')):
                        return [val] # Single value
                    try:
                        return json.loads(val)
                    except:
                        try:
                            return ast.literal_eval(val)
                        except:
                            return [val]
                return val

            outcomes = smart_parse(m.get('outcomes', []))
            prices = smart_parse(m.get('outcomePrices', []))
            
            # Map to standard 'tokens' format for compatibility
            if outcomes and prices and len(outcomes) >= 2:
                tokens = []
                for i in range(len(outcomes)):
                    price = prices[i] if i < len(prices) else 0
                    try:
                        tokens.append({
                            'outcome': outcomes[i],
                            'price': float(price)
                        })
                    except:
                        logger.error(f"Error converting price '{price}' (type {type(price)}) to float for market {m.get('id')}. Outcomes: {outcomes}, Prices: {prices}")
                        # Skip this market
                        tokens = []
                        break
                if tokens:
                    m['tokens'] = tokens
                    m['_is_match'] = True
                    markets.append(m)
            elif m.get('tokens'):
                # Already has tokens format
                m['_is_match'] = True
                markets.append(m)
        
        logger.info(f"[Polymarket] Found {len(markets)} Game Bet markets with processed tokens")
        return markets
    
    def get_filtered_markets(self, 
                             filters: MarketFilters,
                             limit: int = 100) -> List[Dict]:
        """
        Get markets with advanced filtering applied.
        
        Args:
            filters: MarketFilters with criteria
            limit: Maximum number of markets to return
            
        Returns:
            Filtered list of markets sorted by score
        """
        # Fetch more than needed to account for filtering
        raw_markets = self.get_markets(closed=False, limit=limit * 3, order="volume")
        
        filtered = []
        
        for m in raw_markets:
            # Volume filter
            volume = float(m.get("volume", 0) or 0)
            if volume < filters.min_volume_24h:
                continue
                
            # Liquidity filter
            liquidity = float(m.get("liquidity", 0) or 0)
            if liquidity < filters.min_liquidity:
                continue
                
            # Spread filter (calculate if possible)
            spread_pct = self._calculate_spread(m)
            if spread_pct is not None and spread_pct > filters.max_spread_pct:
                continue
            
            # Exclude resolved
            if filters.exclude_resolved:
                if m.get("closed") or m.get("resolved"):
                    continue
            
            # Category filter
            if filters.categories:
                market_cat = m.get("category", "")
                if market_cat not in filters.categories:
                    continue
            
            # Calculate score
            score = self._calculate_market_score(m)
            m['_score'] = score
            m['_spread_pct'] = spread_pct
            
            filtered.append(m)
        
        # Sort by score
        filtered.sort(key=lambda x: x.get('_score', 0), reverse=True)
        
        return filtered[:limit]
    
    def _calculate_spread(self, market: Dict) -> Optional[float]:
        """Calculate bid-ask spread percentage from market data."""
        tokens = market.get("tokens", [])
        if not tokens or len(tokens) < 2:
            return None
            
        try:
            # For binary market, spread = 1 - (yes_price + no_price)
            yes_price = float(tokens[0].get("price", 0) or 0)
            no_price = float(tokens[1].get("price", 0) or 0)
            
            if yes_price > 0 and no_price > 0:
                total = yes_price + no_price
                # Spread is deviation from 1.0
                spread = abs(1.0 - total) * 100
                return spread
        except:
            pass
        return None
    
    def _calculate_market_score(self, market: Dict) -> float:
        """
        Calculate a composite score for market quality.
        Higher score = better market for trading.
        
        Factors:
        - Volume (40%)
        - Liquidity (30%)
        - Tight spread (20%)
        - Recent activity (10%)
        """
        volume = float(market.get("volume", 0) or 0)
        liquidity = float(market.get("liquidity", 0) or 0)
        spread = market.get('_spread_pct') or 5.0  # Default 5%
        
        # Normalize scores
        volume_score = min(volume / 100000, 1.0) * 40  # Cap at 100k
        liquidity_score = min(liquidity / 50000, 1.0) * 30  # Cap at 50k
        spread_score = max(0, (10 - spread) / 10) * 20  # 0% spread = 20 points
        
        # Activity bonus (if recently updated)
        activity_score = 10  # Placeholder
        
        return volume_score + liquidity_score + spread_score + activity_score
    
    def get_top_markets(self, 
                        count: int = 20, 
                        min_volume: float = 5000,
                        max_spread: float = 5.0) -> List[Dict]:
        """
        Convenience method to get top trading markets.
        
        Args:
            count: Number of markets to return
            min_volume: Minimum 24h volume
            max_spread: Maximum spread percentage
            
        Returns:
            Top markets sorted by score
        """
        filters = MarketFilters(
            min_volume_24h=min_volume,
            min_liquidity=1000.0,
            max_spread_pct=max_spread
        )
        return self.get_filtered_markets(filters, limit=count)
    
    def get_events(self,
                   closed: Optional[bool] = False,
                   limit: int = 50,
                   offset: int = 0) -> List[Dict]:
        """
        Fetch events (groups of markets) from Gamma API.
        """
        cache_key = f"events_{closed}_{limit}_{offset}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        params = {
            "limit": limit,
            "offset": offset
        }
        
        if closed is not None:
            params["closed"] = str(closed).lower()
            
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{self.BASE_URL}/events", params=params)
                resp.raise_for_status()
                result = resp.json()
                self._set_cache(cache_key, result)
                return result
        except Exception as e:
            logger.error(f"Gamma API events error: {e}")
            return []
    
    def get_market_by_id(self, condition_id: str) -> Optional[Dict]:
        """
        Fetch a specific market by its condition ID.
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{self.BASE_URL}/markets/{condition_id}")
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Gamma API market fetch error: {e}")
            return None
    
    def search_markets(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search markets by keyword.
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(
                    f"{self.BASE_URL}/search",
                    params={"query": query, "limit": limit}
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Gamma API search error: {e}")
            return []
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            'cached_items': len(self._cache),
            'cache_ttl': self.cache_ttl
        }


def test_gamma_api():
    """Test the Gamma API connection and market discovery."""
    print("=" * 70)
    print("GAMMA API TEST - ACTIVE MARKET DISCOVERY")
    print("=" * 70)
    
    client = GammaAPIClient()
    
    # Test 1: Get open markets sorted by volume
    print("\n[1] Fetching OPEN markets (closed=false, order=volume)...")
    markets = client.get_markets(closed=False, limit=20, order="volume")
    
    print(f"    Retrieved: {len(markets)} markets")
    
    if markets:
        print("\n    TOP 5 ACTIVE MARKETS BY VOLUME:")
        print("    " + "-" * 60)
        
        for i, m in enumerate(markets[:5]):
            q = m.get("question", "N/A")[:55]
            volume = float(m.get("volume", 0) or 0)
            liquidity = float(m.get("liquidity", 0) or 0)
            condition_id = m.get("condition_id", "N/A")[:20]
            tokens = m.get("tokens", [])
            
            print(f"\n    [{i+1}] {q}...")
            print(f"        Volume: ${volume:,.2f} | Liquidity: ${liquidity:,.2f}")
            print(f"        Condition ID: {condition_id}...")
            print(f"        Tokens: {len(tokens)}")
            
            if tokens:
                for j, t in enumerate(tokens[:2]):
                    token_id = t.get("token_id", "N/A")
                    outcome = t.get("outcome", "N/A")
                    price = t.get("price", 0)
                    print(f"          [{j}] {outcome}: ${price:.4f} | ID: {token_id[:30]}...")
    
    # Test 2: Events
    print("\n" + "=" * 70)
    print("[2] Fetching OPEN events...")
    events = client.get_events(closed=False, limit=5)
    print(f"    Retrieved: {len(events)} events")
    
    for e in events[:3]:
        title = e.get("title", "N/A")[:50]
        print(f"    - {title}...")
    
    print("\n" + "=" * 70)
    if markets and len(markets) > 0:
        print("RESULT: SUCCESS - Gamma API returns active markets!")
        print("        Use these token_ids with CLOB API for orderbooks.")
    else:
        print("RESULT: NO ACTIVE MARKETS FOUND - Check API status.")
    print("=" * 70)
    
    return markets


if __name__ == "__main__":
    test_gamma_api()
