"""
Cross-Platform Market Mapper.
Uses LLM with semantic cache to map markets between Polymarket and Betfair.

Optimizations:
1. Mathematical pre-filter (only map if EV_net > 0)
2. ChromaDB semantic cache to avoid repeat LLM calls
3. Minimal JSON-only prompts
4. Batch processing for efficiency
"""

import os
import json
import hashlib
import logging
import asyncio
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()

# Import event type configuration
try:
    from config.betfair_event_types import (
        POLYMARKET_COMPATIBLE_EVENT_TYPES,
        get_event_type_name,
    )
except ImportError:
    # Fallback if config not available
    POLYMARKET_COMPATIBLE_EVENT_TYPES = ["2378961", "10", "6231"]
    def get_event_type_name(eid): return eid


@dataclass
class MarketMapping:
    """Mapping between platforms."""
    polymarket_id: str
    polymarket_question: str
    betfair_event_id: str
    betfair_market_id: str
    betfair_event_name: str
    confidence: float
    mapped_at: datetime
    source: str  # 'cache' or 'llm'
    
    def to_dict(self) -> Dict:
        return {
            'poly_id': self.polymarket_id,
            'poly_question': self.polymarket_question,
            'bf_event_id': self.betfair_event_id,
            'bf_market_id': self.betfair_market_id,
            'bf_event': self.betfair_event_name,
            'confidence': self.confidence,
            'source': self.source
        }


@dataclass
class ArbOpportunity:
    """Cross-platform arbitrage opportunity."""
    mapping: MarketMapping
    poly_yes_price: float
    poly_no_price: float
    betfair_back_odds: float
    betfair_lay_odds: float
    ev_net: float
    is_profitable: bool
    direction: str  # 'buy_poly_back_bf' or 'buy_poly_lay_bf'
    detected_at: datetime
    betfair_delayed: bool = True  # 15-min delay flag
    
    def to_alert(self) -> str:
        """Format as alert message."""
        return (
            f"🎯 ARBITRAGE: {self.mapping.betfair_event_name}\n"
            f"  Poly YES: {self.poly_yes_price:.2%}\n"
            f"  Betfair: Back {self.betfair_back_odds:.2f} / Lay {self.betfair_lay_odds:.2f}\n"
            f"  EV Net: €{self.ev_net:.2f}\n"
            f"  Direction: {self.direction}\n"
            f"  ⚠️ Betfair prices 15min DELAYED" if self.betfair_delayed else ""
        )


class SemanticMappingCache:
    """
    Semantic cache for market mappings using ChromaDB.
    Avoids repeat LLM calls for similar market questions.
    """
    
    def __init__(self, 
                 cache_dir: str = "./mapping_cache",
                 ttl_hours: float = 24.0,
                 similarity_threshold: float = 0.92):
        """
        Args:
            cache_dir: Directory for ChromaDB persistence
            ttl_hours: Cache TTL (mappings valid for 24h typically)
            similarity_threshold: Cosine similarity threshold for hits
        """
        self.cache_dir = cache_dir
        self.ttl_hours = ttl_hours
        self.threshold = similarity_threshold
        
        # In-memory exact match cache
        self._exact_cache: Dict[str, Dict] = {}
        
        # ChromaDB and embeddings
        self._chroma_client = None
        self._collection = None
        self._embedder = None
        self._use_semantic = False
        
        # Stats
        self.stats = {
            'exact_hits': 0,
            'semantic_hits': 0,
            'misses': 0,
            'total_queries': 0
        }
        
        self._init_cache()
    
    def _init_cache(self):
        """Initialize caching backends."""
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Try ChromaDB
        try:
            import chromadb
            self._chroma_client = chromadb.PersistentClient(path=self.cache_dir)
            self._collection = self._chroma_client.get_or_create_collection(
                name="market_mappings",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("[MappingCache] ChromaDB initialized")
        except ImportError:
            logger.warning("[MappingCache] ChromaDB not installed")
        except Exception as e:
            logger.warning(f"[MappingCache] ChromaDB error: {e}")
        
        # Try SentenceTransformers
        try:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer('all-MiniLM-L6-v2')
            self._use_semantic = self._chroma_client is not None
            logger.info("[MappingCache] Semantic search enabled")
        except ImportError:
            logger.warning("[MappingCache] sentence-transformers not installed")
    
    def _hash_query(self, poly_q: str, bf_event: str) -> str:
        """Create stable hash for exact matching."""
        combined = f"{poly_q.lower().strip()}|||{bf_event.lower().strip()}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def get(self, poly_question: str, betfair_event: str) -> Optional[Dict]:
        """
        Check cache for existing mapping.
        
        Returns:
            Cached mapping or None
        """
        self.stats['total_queries'] += 1
        query_hash = self._hash_query(poly_question, betfair_event)
        
        # Try exact match first
        if query_hash in self._exact_cache:
            entry = self._exact_cache[query_hash]
            if time.time() - entry.get('timestamp', 0) < self.ttl_hours * 3600:
                self.stats['exact_hits'] += 1
                return entry.get('mapping')
        
        # Try semantic match
        if self._use_semantic:
            try:
                combined_query = f"{poly_question} ||| {betfair_event}"
                embedding = self._embedder.encode(combined_query).tolist()
                
                results = self._collection.query(
                    query_embeddings=[embedding],
                    n_results=1,
                    include=['metadatas', 'distances']
                )
                
                if results['distances'] and results['distances'][0]:
                    distance = results['distances'][0][0]
                    similarity = 1 - distance
                    
                    if similarity >= self.threshold:
                        metadata = results['metadatas'][0][0]
                        timestamp = metadata.get('timestamp', 0)
                        
                        if time.time() - timestamp < self.ttl_hours * 3600:
                            self.stats['semantic_hits'] += 1
                            return json.loads(metadata.get('mapping', '{}'))
            except Exception as e:
                logger.debug(f"[MappingCache] Semantic search error: {e}")
        
        self.stats['misses'] += 1
        return None
    
    def set(self, 
            poly_question: str, 
            betfair_event: str, 
            mapping: Dict):
        """Store mapping in cache."""
        query_hash = self._hash_query(poly_question, betfair_event)
        timestamp = time.time()
        
        # Store in exact cache
        self._exact_cache[query_hash] = {
            'mapping': mapping,
            'timestamp': timestamp
        }
        
        # Store in semantic cache
        if self._use_semantic:
            try:
                combined_query = f"{poly_question} ||| {betfair_event}"
                embedding = self._embedder.encode(combined_query).tolist()
                
                # Upsert
                try:
                    self._collection.update(
                        ids=[query_hash],
                        embeddings=[embedding],
                        documents=[combined_query],
                        metadatas=[{
                            'timestamp': timestamp,
                            'mapping': json.dumps(mapping),
                            'poly_q': poly_question[:100],
                            'bf_event': betfair_event[:100]
                        }]
                    )
                except:
                    self._collection.add(
                        ids=[query_hash],
                        embeddings=[embedding],
                        documents=[combined_query],
                        metadatas=[{
                            'timestamp': timestamp,
                            'mapping': json.dumps(mapping),
                            'poly_q': poly_question[:100],
                            'bf_event': betfair_event[:100]
                        }]
                    )
            except Exception as e:
                logger.debug(f"[MappingCache] Storage error: {e}")
    
    def get_hit_rate(self) -> float:
        """Get cache hit rate percentage."""
        total = self.stats['total_queries']
        if total == 0:
            return 0.0
        hits = self.stats['exact_hits'] + self.stats['semantic_hits']
        return hits / total * 100
    
    def get_stats(self) -> Dict:
        return {
            **self.stats,
            'hit_rate': f"{self.get_hit_rate():.1f}%",
            'semantic_enabled': self._use_semantic
        }


class CrossPlatformMapper:
    """
    Maps markets between Polymarket and Betfair.
    Uses MiMo-V2-Flash with semantic caching for efficiency.
    """
    
    def __init__(self,
                 min_ev_threshold: float = 0.0,
                 cache_ttl_hours: float = 24.0,
                 api_key: Optional[str] = None):
        """
        Args:
            min_ev_threshold: Minimum EV to even attempt mapping (0 = disabled)
            cache_ttl_hours: How long mappings are cached
            api_key: LLM API key (or API_LLM env)
        """
        self.min_ev = min_ev_threshold
        self.cache = SemanticMappingCache(ttl_hours=cache_ttl_hours)
        
        # LLM client
        self.api_key = api_key or os.getenv('API_LLM') or os.getenv('OPENROUTER_API_KEY')
        self.model = "xiaomi/mimo-v2-flash"
        self.base_url = "https://openrouter.ai/api/v1"
        self._client = None
        
        # Stats
        self.stats = {
            'mapping_attempts': 0,
            'successful_mappings': 0,
            'cache_savings': 0,
            'llm_calls': 0,
            'tokens_used': 0
        }
    
    async def _init_client(self):
        """Initialize async OpenAI client."""
        if self._client is None and self.api_key:
            try:
                import openai
                self._client = openai.AsyncOpenAI(
                    base_url=self.base_url,
                    api_key=self.api_key
                )
            except ImportError:
                logger.error("openai package not installed")
    
    async def map_market(self,
                         poly_question: str,
                         poly_id: str,
                         betfair_events: List[Dict],
                         poly_yes_price: float = 0.0,
                         betfair_odds: float = 0.0,
                         gas_cost: float = 0.10) -> Optional[MarketMapping]:
        """
        Find matching Betfair event for Polymarket question.
        
        Process:
        1. Check EV threshold (skip if not profitable)
        2. Check semantic cache (skip LLM if cached)
        3. Call LLM for mapping (if needed)
        4. Cache result
        
        Args:
            poly_question: Polymarket market question
            poly_id: Polymarket market ID
            betfair_events: List of Betfair events to match against
            poly_yes_price: Current Polymarket YES price (for EV check)
            betfair_odds: Best Betfair odds (for EV check)
            gas_cost: Estimated gas in USD
        """
        self.stats['mapping_attempts'] += 1
        
        # Step 1: EV Pre-filter
        if self.min_ev > 0 and poly_yes_price > 0 and betfair_odds > 0:
            ev_net = self._calculate_ev(poly_yes_price, betfair_odds, gas_cost)
            if ev_net < self.min_ev:
                logger.debug(f"[Mapper] Skipped - EV {ev_net:.4f} below threshold")
                return None
        
        # Step 2: Check cache for each potential match
        for bf_event in betfair_events:
            bf_name = bf_event.get('name', '')
            
            cached = self.cache.get(poly_question, bf_name)
            if cached:
                self.stats['cache_savings'] += 1
                self.stats['successful_mappings'] += 1
                
                return MarketMapping(
                    polymarket_id=poly_id,
                    polymarket_question=poly_question,
                    betfair_event_id=cached.get('bf_event_id', bf_event.get('id', '')),
                    betfair_market_id=cached.get('bf_market_id', ''),
                    betfair_event_name=bf_name,
                    confidence=cached.get('confidence', 0.9),
                    mapped_at=datetime.now(),
                    source='cache'
                )
        
        # Step 3: LLM mapping (only if no cache hit)
        if not self.api_key:
            logger.warning("[Mapper] No API key - cannot call LLM")
            return None
        
        await self._init_client()
        
        # Prepare candidate list for LLM
        candidates = [
            {"id": e.get("id", ""), "name": e.get("name", "")}
            for e in betfair_events[:10]  # Limit to top 10
        ]
        
        # Minimal prompt (JSON only)
        prompt = f"""Match Polymarket to Betfair. JSON only.
Poly: "{poly_question}"
BF events: {json.dumps(candidates, separators=(',', ':'))}
Format: {{"match":true/false,"bf_id":"ID","confidence":0.0-1.0}}"""

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Market matcher. JSON only, no explanation."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=80
            )
            
            content = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0
            
            self.stats['llm_calls'] += 1
            self.stats['tokens_used'] += tokens
            
            # Parse response
            result = self._parse_response(content)
            
            if result.get('match') and result.get('bf_id'):
                bf_id = result['bf_id']
                confidence = result.get('confidence', 0.8)
                
                # Find matched event
                matched_event = next(
                    (e for e in betfair_events if e.get('id') == bf_id),
                    None
                )
                
                if matched_event:
                    mapping_data = {
                        'bf_event_id': bf_id,
                        'bf_market_id': matched_event.get('market_id', ''),
                        'confidence': confidence,
                        'match': True
                    }
                    
                    # Cache the mapping
                    self.cache.set(poly_question, matched_event.get('name', ''), mapping_data)
                    
                    self.stats['successful_mappings'] += 1
                    
                    return MarketMapping(
                        polymarket_id=poly_id,
                        polymarket_question=poly_question,
                        betfair_event_id=bf_id,
                        betfair_market_id=matched_event.get('market_id', ''),
                        betfair_event_name=matched_event.get('name', ''),
                        confidence=confidence,
                        mapped_at=datetime.now(),
                        source='llm'
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"[Mapper] LLM error: {e}")
            return None
    
    def _parse_response(self, content: str) -> Dict:
        """Parse LLM JSON response."""
        import re
        
        # Try direct parse
        try:
            return json.loads(content.strip())
        except:
            pass
        
        # Try extracting JSON from text
        json_match = re.search(r'\{[^}]+\}', content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass
        
        return {'match': False}
    
    def _calculate_ev(self, 
                      poly_prob: float, 
                      bf_odds: float,
                      gas: float,
                      commission: float = 0.02) -> float:
        """
        Calculate net EV.
        Formula: EV_net = (Poly - BF_implied) - Gas - Commission
        """
        bf_implied = 1 / bf_odds if bf_odds > 0 else 0
        ev_gross = poly_prob - bf_implied
        ev_net = ev_gross - gas - commission
        return ev_net
    
    async def batch_map(self,
                        poly_markets: List[Dict],
                        betfair_events: List[Dict]) -> List[MarketMapping]:
        """
        Batch map multiple Polymarket markets to Betfair events.
        Uses semantic cache for efficiency.
        """
        mappings = []
        
        for poly in poly_markets:
            mapping = await self.map_market(
                poly_question=poly.get('question', ''),
                poly_id=poly.get('id', ''),
                betfair_events=betfair_events,
                poly_yes_price=poly.get('yes_price', 0),
                betfair_odds=poly.get('best_bf_odds', 0)
            )
            
            if mapping:
                mappings.append(mapping)
        
        return mappings
    
    def get_stats(self) -> Dict:
        """Get mapper statistics."""
        savings_pct = 0
        if self.stats['mapping_attempts'] > 0:
            savings_pct = self.stats['cache_savings'] / self.stats['mapping_attempts'] * 100
        
        return {
            **self.stats,
            'cache_savings_pct': f"{savings_pct:.1f}%",
            'cache': self.cache.get_stats()
        }


class ShadowArbitrageScan:
    """
    Shadow mode arbitrage scanner.
    Reads real prices but doesn't execute - for testing/validation.
    
    Logs theoretical profit opportunities with 15-min Betfair delay awareness.
    """
    
    def __init__(self,
                 mapper: CrossPlatformMapper,
                 betfair_client,  # BetfairClient or BetfairSimulator
                 polymarket_client = None,
                 min_ev_threshold: float = 0.01,  # €0.01 minimum
                 betfair_commission: float = 0.02):
        """
        Args:
            mapper: CrossPlatformMapper for ID linking
            betfair_client: Betfair API client
            polymarket_client: Polymarket API client (optional)
            min_ev_threshold: Minimum EV to report (in EUR)
            betfair_commission: Betfair commission rate
        """
        self.mapper = mapper
        self.betfair = betfair_client
        self.polymarket = polymarket_client
        self.min_ev = min_ev_threshold
        self.bf_commission = betfair_commission
        
        # Detected opportunities
        self.opportunities: List[ArbOpportunity] = []
        
        # Stats
        self.stats = {
            'scans': 0,
            'opportunities_found': 0,
            'total_theoretical_profit': 0.0
        }
    
    async def scan_market(self,
                          poly_market: Dict,
                          bf_events: List[Dict]) -> Optional[ArbOpportunity]:
        """
        Scan a single Polymarket market against Betfair events.
        
        Args:
            poly_market: Polymarket market data
            bf_events: List of Betfair events
            
        Returns:
            ArbOpportunity if profitable, None otherwise
        """
        self.stats['scans'] += 1
        
        # Step 1: Map the market
        mapping = await self.mapper.map_market(
            poly_question=poly_market.get('question', ''),
            poly_id=poly_market.get('id', ''),
            betfair_events=bf_events,
            poly_yes_price=poly_market.get('yes_price', 0.5)
        )
        
        if not mapping:
            return None
        
        # Step 2: Get Betfair prices (15-min delayed for free tier)
        bf_prices = await self.betfair.get_prices([mapping.betfair_market_id])
        
        if not bf_prices:
            return None
        
        # Get best prices
        best_back = max((p.back_price for p in bf_prices), default=0)
        best_lay = min((p.lay_price for p in bf_prices if p.lay_price > 0), default=0)
        
        poly_yes = poly_market.get('yes_price', 0.5)
        poly_no = poly_market.get('no_price', 0.5)
        
        # Step 3: Calculate EV
        # Strategy: Buy YES on Poly, Back on Betfair
        ev_net, profitable = self.betfair.calculate_ev_net(
            poly_prob=poly_yes,
            betfair_odds=best_back,
            stake=10.0,
            gas_cost=0.10
        )
        
        if profitable and ev_net >= self.min_ev:
            opp = ArbOpportunity(
                mapping=mapping,
                poly_yes_price=poly_yes,
                poly_no_price=poly_no,
                betfair_back_odds=best_back,
                betfair_lay_odds=best_lay,
                ev_net=ev_net,
                is_profitable=True,
                direction='buy_poly_back_bf',
                detected_at=datetime.now(),
                betfair_delayed=self.betfair.use_delay
            )
            
            self.opportunities.append(opp)
            self.stats['opportunities_found'] += 1
            self.stats['total_theoretical_profit'] += ev_net
            
            # Log the opportunity
            logger.info(f"[SHADOW] Oportunidad detectada: Beneficio teórico {ev_net:.2f}€")
            
            return opp
        
        return None
    
    async def run_scan_cycle(self,
                              poly_markets: List[Dict],
                              bf_events: List[Dict]) -> List[ArbOpportunity]:
        """
        Run a full scan cycle across all markets.
        """
        found = []
        
        for poly in poly_markets:
            opp = await self.scan_market(poly, bf_events)
            if opp:
                found.append(opp)
        
        return found
    
    def get_report(self) -> str:
        """Generate scan report."""
        report = [
            "=" * 60,
            "SHADOW MODE ARBITRAGE REPORT",
            "=" * 60,
            f"Total Scans: {self.stats['scans']}",
            f"Opportunities Found: {self.stats['opportunities_found']}",
            f"Total Theoretical Profit: €{self.stats['total_theoretical_profit']:.2f}",
            "",
            "Recent Opportunities:"
        ]
        
        for opp in self.opportunities[-5:]:
            report.append(f"  - {opp.mapping.betfair_event_name}: €{opp.ev_net:.2f}")
        
        if self.betfair.use_delay:
            report.append("")
            report.append("⚠️ NOTE: Betfair prices are 15 minutes DELAYED")
            report.append("   Real-time data requires paid subscription")
        
        report.append("=" * 60)
        return "\n".join(report)
    
    def get_stats(self) -> Dict:
        return {
            **self.stats,
            'mapper': self.mapper.get_stats(),
            'betfair': self.betfair.get_stats()
        }


# ============== DEMO ==============

async def demo():
    """Demo the cross-platform mapper and shadow scanner."""
    print("\n" + "=" * 70)
    print("CROSS-PLATFORM MARKET MAPPER + SHADOW SCANNER DEMO")
    print("=" * 70)
    
    api_key = os.getenv('API_LLM')
    if not api_key:
        print("\n⚠️ API_LLM not set - will use cache only")
    else:
        print(f"\n✅ API Key: {api_key[:15]}...")
    
    # Initialize components
    mapper = CrossPlatformMapper(
        min_ev_threshold=0.0,  # Check all for demo
        cache_ttl_hours=24.0
    )
    
    # Use simulated Betfair client
    from src.data.betfair_client import BetfairSimulator
    betfair = BetfairSimulator(use_delay=True)
    await betfair.login()
    
    # Simulated Polymarket markets (Political/Financial - matching Betfair categories)
    poly_markets = [
        {
            'id': '0xpol001',
            'question': 'Will Donald Trump win the 2028 US Presidential Election?',
            'yes_price': 0.35,
            'no_price': 0.67
        },
        {
            'id': '0xpol002',
            'question': 'Will Bitcoin exceed $150,000 by end of 2026?',
            'yes_price': 0.28,
            'no_price': 0.74
        },
        {
            'id': '0xpol003',
            'question': 'Will there be a Federal Reserve rate cut in March 2026?',
            'yes_price': 0.62,
            'no_price': 0.40
        }
    ]
    
    # Get Betfair events (Politics, Specials, Financial - NOT Soccer)
    print(f"\n[1] Fetching Betfair Events...")
    print(f"    Event Types: {[get_event_type_name(et) for et in POLYMARKET_COMPATIBLE_EVENT_TYPES]}")
    
    bf_events = await betfair.list_events(event_type_ids=POLYMARKET_COMPATIBLE_EVENT_TYPES)
    print(f"    Events found: {len(bf_events)}")
    
    if len(bf_events) == 0:
        print("    ⚠️ No Politics/Specials events found. Using simulated events for demo.")
        # Provide simulated political events for demo
        bf_events = [
            {'id': 'bf_trump2028', 'name': 'Trump to win 2028 Presidential Election', 'market_id': '1.200000001'},
            {'id': 'bf_btc150k', 'name': 'Bitcoin to be over $150,000', 'market_id': '1.200000002'},
            {'id': 'bf_fedrate', 'name': 'Fed to cut rates March 2026', 'market_id': '1.200000003'},
        ]
    
    for e in bf_events[:5]:
        print(f"    {e.get('id', 'N/A')}: {e.get('name', 'Unknown')}")
    
    # Test mapping
    print(f"\n[2] Market Mapping...")
    for poly in poly_markets:
        print(f"\n  Polymarket: {poly['question']}")
        
        mapping = await mapper.map_market(
            poly_question=poly['question'],
            poly_id=poly['id'],
            betfair_events=bf_events,
            poly_yes_price=poly['yes_price']
        )
        
        if mapping:
            print(f"  ✅ Matched: {mapping.betfair_event_name}")
            print(f"     Confidence: {mapping.confidence:.0%}")
            print(f"     Source: {mapping.source}")
        else:
            print(f"  ❌ No match found")
    
    # Shadow scan
    print(f"\n[3] Shadow Arbitrage Scan...")
    scanner = ShadowArbitrageScan(
        mapper=mapper,
        betfair_client=betfair,
        min_ev_threshold=0.01
    )
    
    opps = await scanner.run_scan_cycle(poly_markets, bf_events)
    print(f"    Found {len(opps)} opportunities")
    
    for opp in opps:
        print(f"\n    {opp.to_alert()}")
    
    # Stats
    print(f"\n[4] Statistics...")
    print(f"    Mapper: {mapper.get_stats()}")
    print(f"\n{scanner.get_report()}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(demo())
