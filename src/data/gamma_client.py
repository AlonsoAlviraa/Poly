#!/usr/bin/env python3
"""
Gamma API Client for Polymarket Market Discovery.
Enhanced with advanced filtering, caching, and market scoring.
"""

import logging
import time
import json
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional
from dataclasses import dataclass

from src.utils.http_client import get_httpx_client
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

    def parse_polymarket_event_date(self, event_json: Dict) -> Optional[datetime]:
        """
        Unified Polymarket Date Parsing.
        Priority: gameStartTime > startDate > endDate.
        """
        # Look in root or first market
        first_m = event_json.get('markets', [{}])[0] if isinstance(event_json.get('markets'), list) else {}
        
        date_str = (
            event_json.get('gameStartTime') or 
            first_m.get('gameStartTime') or 
            event_json.get('startDate') or 
            event_json.get('endDate')
        )
        
        if not date_str:
            return None
            
        try:
            # Handle ISO or "2026-02-07 15:00:00+00" formats
            clean_str = date_str.replace(' ', 'T').replace('Z', '+00:00')
            return datetime.fromisoformat(clean_str)
        except Exception as e:
            logger.warning(f"Failed to parse date '{date_str}': {e}")
            return None
        
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
            with get_httpx_client(timeout=self.timeout, http2=True) as client:
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
    
    # BROADENING: Inclusion of specific sports tags for maximum coverage
    # BROADENING: Inclusion of specific sports tags for maximum coverage
    TARGET_TAGS = [
        "10345",  # NBA
        "100032", # Soccer (General)
        "10340",  # Premier League
        "10342",  # La Liga
        "10343",  # Serie A
        "10344",  # Bundesliga
        "10341",  # UCL
        "100008", # Tennis
        "10339",  # NFL
        "10271",  # NHL
        "10346",  # Baseball
        "10672",  # Cricket
        "10349",  # NCAA Basketball
        "10452",  # EuroLeague
        "100109", # Basketball General
        "100127", # Tennis ATP (NEW)
        "100128", # Tennis WTA (NEW)
        "100028", # WNBA (NEW)
        "100650", # ITF Tennis (NEW)
        "100639", # Game Bets (General Rescue)
    ]
    
    def get_match_events(self, 
                         series_id: Optional[str] = None,
                         limit: int = 200) -> List[Dict]:
        """
        🎯 Fetch ONLY match odds (No Futures) from Polymarket.
        """
        params = {
            "tag_id": self.TAG_GAME_BET,
            "active": "true",
            "closed": "false",
            "order": "startDate",
            "ascending": "true",
            "limit": limit
        }
        if series_id: params["series_id"] = series_id
        
        try:
            with get_httpx_client(timeout=self.timeout, http2=True) as client:
                resp = client.get(f"{self.BASE_URL}/events", params=params)
                resp.raise_for_status()
                return resp.json()
        except: return []

    async def get_all_match_markets(self, limit: int = 1000) -> List[Dict]:
        """
        🎯 OPEN THE TAP: Fetch all match markets across multiple categories with Parallelism.
        """
        limit_per_tag = limit
        logger.info(f"[Polymarket] 🌊 OPENING THE TAP - Broad Ingestion Pattern (Parallel)...")
        
        self.discard_stats = {
            "no_category": 0, "expired_date": 0, "no_tokens": 0, "total_raw": 0
        }
        
        all_markets = []
        unique_market_ids = set()
        
        seen_ids = set()
        loop = asyncio.get_event_loop()

        # 1. Scrape specific tags
        async def scrape_tag(tag):
            tag_markets = []
            offset = 0
            while offset < limit_per_tag:
                raw_page = await loop.run_in_executor(None, lambda: self.get_markets(
                    closed=False, limit=100, offset=offset, order="volume", tag_id=tag
                ))
                if not raw_page: break
                
                self.discard_stats["total_raw"] += len(raw_page)
                for m in raw_page:
                    processed = self._process_market(m)
                    if processed:
                        tag_markets.append(processed)
                
                if len(raw_page) < 100: break
                offset += 100
            return tag_markets

        # 2. Add a BROAD VOLUME SCRAPE (NEW)
        async def scrape_top_volume():
            top_markets = []
            offset = 0
            while offset < 2000: # Fetch top 2000 markets globally
                raw_page = await loop.run_in_executor(None, lambda: self.get_markets(
                    closed=False, limit=100, offset=offset, order="volume"
                ))
                if not raw_page: break
                self.discard_stats["total_raw"] += len(raw_page)
                for m in raw_page:
                    processed = self._process_market(m)
                    if processed: top_markets.append(processed)
                if len(raw_page) < 100: break
                offset += 100
            return top_markets

        # Concurrent Scraping
        tasks = [scrape_tag(tag) for tag in self.TARGET_TAGS]
        tasks.append(scrape_top_volume())
        
        results = await asyncio.gather(*tasks)
        
        for batch in results:
            for m in batch:
                m_id = str(m.get('id', ''))
                if m_id not in seen_ids:
                    all_markets.append(m)
                    seen_ids.add(m_id)
        
        logger.info(f"[Polymarket] ✅ INGESTION COMPLETE: {len(all_markets)} valid entries.")
        return all_markets

    def _infer_category_from_metadata(self, m: Dict) -> Optional[str]:
        """🎯 CATEGORY RESCUE: Infer sport/category from metadata."""
        tags = m.get('tags', []) or []
        tag_ids = [str(t.get('id')) if isinstance(t, dict) else str(t) for t in tags]
        
        tag_map = {
            '10345': 'Basketball', '10339': 'American Football', '10346': 'Baseball',
            '100032': 'Soccer', '10340': 'Soccer', '10341': 'Soccer', '10342': 'Soccer',
            '100008': 'Tennis', '10271': 'Ice Hockey', '10672': 'Cricket'
        }
        for tid, sport in tag_map.items():
            if tid in tag_ids: return sport

        slug = f"{m.get('slug', '')} {m.get('question', '')}".lower()
        
        # 🎾 TENNIS RESCUE (Aggressive but safe)
        tennis_keywords = ['tennis', 'atp', 'wta', 'australian-open', 'french-open', 'wimbledon', 'us-open', 'match odds', 'set betting', 'games handicap']
        tennis_players = [
            'nadal', 'alcaraz', 'djokovic', 'sinner', 'medvedev', 'zverev', 'tsitsipas', 
            'ruud', 'rublev', 'hurkacz', 'norrie', 'draper', 'fritz', 'tiafoe', ' Shelton',
            'sabalenka', 'swiatek', 'gauff', 'rybakina', 'pegula', 'jabeur', 'paolini'
        ]
        # 🏀 BASKETBALL RESCUE
        basket_keywords = ['nba', 'basketball', 'wnba', 'ncaa', 'euroleague', 'march madness', 'college basketball', 'league pass', 'points spread']
        basket_teams = [
            'lakers', 'warriors', 'celtics', 'knicks', '76ers', 'suns', 'bucks', 'clippers', 'nuggets',
            'baskonia', 'barcelona', 'madrid', 'monaco', 'olimpiacos', 'panathinaikos', 'virtus', 'zalgiris'
        ]
        tennis_blacklist = ['table tennis', 'ping pong', 'padel', 'esports', 'cyber', 'simulated', 'e-soccer', 'efootball']
        
        is_tennis = any(k in slug for k in tennis_keywords) or any(p in slug for p in tennis_players)
        is_fake_tennis = any(b in slug for b in tennis_blacklist)
        
        if is_tennis and not is_fake_tennis:
            return 'Tennis'

        rules = [
            (['soccer', 'premier-league', 'la-liga', 'football', 'bundesliga', 'serie-a'], 'Soccer'),
            (['nba', 'basketball', 'euroleague', 'wnba'], 'Basketball'),
            (['nhl', 'hockey'], 'Ice Hockey'),
            (['mlb', 'baseball'], 'Baseball'),
            (['nfl', 'american-football'], 'American Football'),
            (['ufc', 'boxing', 'mma'], 'Martial Arts'),
            (['f1', 'formula-1'], 'Motorsports'),
            (['politics', 'election', 'trump', 'kamala', 'harris'], 'Politics'),
            (['crypto', 'bitcoin', 'eth', 'solana'], 'Crypto'),
            (['oscar', 'grammy', 'movie', 'rot-tom'], 'Pop Culture')
        ]
        for keywords, sport in rules:
            if any(k in slug for k in keywords): return sport
        return 'Other' # Fallback for remaining Game Bets

    def _process_market(self, m: Dict, forced_category: Optional[str] = None) -> Optional[Dict]:
        """Internal helper to parse, filter and score a single market."""
        try:
            event_date = self.parse_polymarket_event_date(m)
            if not event_date: return None
            
            # UTC Safety: ensure comparison is with aware datetime
            now_utc = datetime.now(timezone.utc)
            if event_date.tzinfo is None:
                event_date = event_date.replace(tzinfo=timezone.utc)

            # RELAXED EXPIRATION: 6 hours grace for sports, 24 hours for others
            inferred_cat = self._infer_category_from_metadata(m) or ''
            is_sport = any(x in inferred_cat.lower() for x in ['soccer', 'basketball', 'tennis', 'hockey', 'baseball', 'football'])
            grace_period = 21600 if is_sport else 86400 # 6h vs 24h
            
            if event_date.timestamp() < (now_utc.timestamp() - grace_period):
                self.discard_stats["expired_date"] += 1
                return None
            
            m['_event_date_parsed'] = event_date
            m['startDate'] = event_date.isoformat()

            cat = (m.get('category', '') or '').lower()
            if forced_category: cat = forced_category.lower()
            
            # If still missing or overly generic, rescue
            if not cat or cat in ['game-bet', 'special', 'other']:
                inferred = self._infer_category_from_metadata(m)
                if inferred: cat = inferred.lower()

            final_cat = None
            if any(x in cat for x in ['soccer', 'football']): final_cat = 'Soccer'
            elif any(x in cat for x in ['nba', 'basketball']): final_cat = 'Basketball'
            elif any(x in cat for x in ['tennis']): final_cat = 'Tennis'
            elif any(x in cat for x in ['hockey']): final_cat = 'Ice Hockey'
            elif any(x in cat for x in ['baseball', 'mlb']): final_cat = 'Baseball'
            elif any(x in cat for x in ['american football']): final_cat = 'American Football'
            elif 'politics' in cat: final_cat = 'Politics'
            elif 'crypto' in cat: final_cat = 'Crypto'
            else: final_cat = cat.title() if cat else 'Other'
            
            m['category'] = final_cat

            # --- ROBUST PRICE EXTRACTION ---
            tokens = m.get('tokens')
            try:
                if not tokens and m.get('outcomes') and m.get('outcomePrices'):
                    outcomes = self._smart_parse(m['outcomes'])
                    prices = self._smart_parse(m['outcomePrices'])
                    clob_ids = self._smart_parse(m.get('clobTokenIds', []))
                    if outcomes and len(outcomes) >= 2:
                        tokens = []
                        for i in range(len(outcomes)):
                            try:
                                tokens.append({
                                    'outcome': outcomes[i],
                                    'price': float(prices[i]) if i < len(prices) else 0.0,
                                    'token_id': clob_ids[i] if i < len(clob_ids) else ''
                                })
                            except: continue
                
                if not tokens or len(tokens) < 2:
                    self.discard_stats["no_tokens"] += 1
                    return None
                    
                m['tokens'] = tokens
                m['_is_match'] = True
                return m
            except:
                self.discard_stats["no_tokens"] += 1
                return None
        except: return None

    def _smart_parse(self, val):
        import ast
        if not val: return []
        if isinstance(val, list): return val
        try: return json.loads(val)
        except:
            try: return ast.literal_eval(val)
            except: return [val]
    
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
            with get_httpx_client(timeout=self.timeout, http2=True) as client:
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
            with get_httpx_client(timeout=self.timeout, http2=True) as client:
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
            with get_httpx_client(timeout=self.timeout, http2=True) as client:
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

# Alias for backward compatibility
GammaClient = GammaAPIClient

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
    print("[2] Fetching OPEN events MATCH EVENTS (STRICT MODE)...")
    # Using get_match_events specifically since that's what we modified
    events = client.get_match_events(limit=5)

    print(f"    Retrieved: {len(events)} filtered events")
    
    for e in events[:5]:
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
