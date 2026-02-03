"""
AI Integration Module for Arbitrage Analysis.
Uses MiMo-V2-Flash via OpenRouter for semantic market matching and thesis generation.
Includes ChromaDB semantic cache for token efficiency.
"""

import os
import asyncio
import logging
import hashlib
import json
import time
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Load environment
from dotenv import load_dotenv
load_dotenv()


@dataclass
class AIThesis:
    """Result of AI market analysis."""
    is_arb: bool
    confidence: float
    reasoning: str
    suggested_action: str
    markets_analyzed: List[str]
    cached: bool = False
    tokens_used: int = 0


class SemanticCache:
    """
    Semantic cache using ChromaDB for efficient token usage.
    Caches AI responses for similar market queries.
    """
    
    def __init__(self, cache_dir: str = "./semantic_cache", ttl_hours: float = 1.0):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_hours * 3600
        self._collection = None
        self._use_chroma = False
        self._simple_cache: Dict[str, Dict] = {}  # Fallback
        
        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=cache_dir)
            self._collection = self._client.get_or_create_collection(
                "market_mappings",
                metadata={"hnsw:space": "cosine"}
            )
            self._use_chroma = True
            logger.info("[AI Cache] ChromaDB initialized")
        except ImportError:
            logger.warning("[AI Cache] ChromaDB not installed, using simple cache")
        except Exception as e:
            logger.warning(f"[AI Cache] ChromaDB error: {e}, using simple cache")
    
    def _hash_query(self, query: str) -> str:
        """Create stable hash for query."""
        return hashlib.md5(query.lower().strip().encode()).hexdigest()
    
    def get(self, market_description: str, similarity_threshold: float = 0.05) -> Optional[Dict]:
        """
        Check cache for similar market analysis.
        Returns cached result if found within TTL and similarity threshold.
        """
        query_hash = self._hash_query(market_description)
        
        # Simple cache fallback
        if not self._use_chroma:
            if query_hash in self._simple_cache:
                entry = self._simple_cache[query_hash]
                if time.time() - entry['timestamp'] < self.ttl_seconds:
                    logger.debug(f"[Cache HIT] Simple cache: {query_hash[:8]}")
                    return entry['data']
            return None
        
        # ChromaDB semantic search
        try:
            results = self._collection.query(
                query_texts=[market_description],
                n_results=1,
                include=['documents', 'metadatas', 'distances']
            )
            
            if results['distances'] and results['distances'][0]:
                distance = results['distances'][0][0]
                if distance < similarity_threshold:
                    metadata = results['metadatas'][0][0] if results['metadatas'][0] else {}
                    timestamp = metadata.get('timestamp', 0)
                    
                    if time.time() - timestamp < self.ttl_seconds:
                        logger.debug(f"[Cache HIT] Semantic: dist={distance:.4f}")
                        return json.loads(metadata.get('data', '{}'))
            
            return None
            
        except Exception as e:
            logger.warning(f"[Cache] Query error: {e}")
            return None
    
    def set(self, market_description: str, data: Dict):
        """Store analysis result in cache."""
        query_hash = self._hash_query(market_description)
        timestamp = time.time()
        
        # Simple cache
        if not self._use_chroma:
            self._simple_cache[query_hash] = {
                'data': data,
                'timestamp': timestamp
            }
            return
        
        # ChromaDB
        try:
            self._collection.add(
                documents=[market_description],
                metadatas=[{
                    'timestamp': timestamp,
                    'data': json.dumps(data),
                    'hash': query_hash
                }],
                ids=[query_hash]
            )
            logger.debug(f"[Cache SET] {query_hash[:8]}")
        except Exception as e:
            # Might already exist, try update
            try:
                self._collection.update(
                    ids=[query_hash],
                    documents=[market_description],
                    metadatas=[{
                        'timestamp': timestamp,
                        'data': json.dumps(data),
                        'hash': query_hash
                    }]
                )
            except:
                logger.warning(f"[Cache] Set error: {e}")
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        if self._use_chroma:
            try:
                count = self._collection.count()
                return {'type': 'chromadb', 'entries': count}
            except:
                pass
        return {'type': 'simple', 'entries': len(self._simple_cache)}


class MiMoClient:
    """
    Async client for MiMo-V2-Flash via OpenRouter.
    Optimized for HFT with minimal token usage.
    """
    
    # Default model - MiMo-V2-Flash via OpenRouter
    DEFAULT_MODEL = "xiaomi/mimo-v2-flash"
    FALLBACK_MODELS = [
        "openai/gpt-4o-mini",
        "google/gemini-flash-1.5",
        "anthropic/claude-3-haiku"
    ]
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 base_url: str = "https://openrouter.ai/api/v1",
                 model: Optional[str] = None):
        """
        Initialize MiMo client.
        
        Args:
            api_key: OpenRouter API key (or set API_LLM env)
            base_url: API endpoint
            model: Model to use (default: xiaomi/mimo-v2-flash)
        """
        # Check multiple env vars for the API key
        self.api_key = api_key or os.getenv('API_LLM') or os.getenv('OPENROUTER_API_KEY')
        self.base_url = base_url
        self.model = model or self.DEFAULT_MODEL
        self._client = None
        
        if not self.api_key:
            logger.warning("[MiMo] No API key found - AI features disabled")
        else:
            logger.info(f"[MiMo] Initialized with model: {self.model}")
    
    async def _init_client(self):
        """Lazy init of async OpenAI client."""
        if self._client is None:
            try:
                import openai
                self._client = openai.AsyncOpenAI(
                    base_url=self.base_url,
                    api_key=self.api_key
                )
            except ImportError:
                logger.error("[MiMo] openai package not installed")
                raise
    
    async def analyze_arbitrage(self, 
                                market_data: Dict,
                                context: str = "") -> AIThesis:
        """
        Analyze potential arbitrage opportunity.
        
        Args:
            market_data: Dict with market prices, spreads, etc.
            context: Additional context (optional)
            
        Returns:
            AIThesis with analysis result
        """
        if not self.api_key:
            return AIThesis(
                is_arb=False,
                confidence=0.0,
                reasoning="AI disabled - no API key",
                suggested_action="none",
                markets_analyzed=[],
                cached=False
            )
        
        await self._init_client()
        
        # Build compact prompt
        prompt = self._build_analysis_prompt(market_data, context)
        
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "HFT Analyst. Compare markets, find arb. Be concise. JSON only."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.1,  # High precision
                max_tokens=200,   # Strict token limit
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0
            
            # Parse response
            return self._parse_response(content, market_data, tokens)
            
        except Exception as e:
            logger.error(f"[MiMo] API error: {e}")
            return AIThesis(
                is_arb=False,
                confidence=0.0,
                reasoning=f"API error: {str(e)[:50]}",
                suggested_action="error",
                markets_analyzed=list(market_data.keys()) if isinstance(market_data, dict) else [],
                cached=False
            )
    
    def _build_analysis_prompt(self, market_data: Dict, context: str) -> str:
        """Build minimal token prompt."""
        # Compact JSON representation
        data_str = json.dumps(market_data, separators=(',', ':'))
        
        prompt = f"""Arb? {data_str}
        
Rules:
- Compare prices across platforms
- Calculate net EV after fees (0.5%)
- Respond JSON: {{"is_arb":bool,"confidence":0-1,"action":"buy_X_sell_Y"|"none","reason":"<20 words"}}
"""
        if context:
            prompt += f"\nContext: {context}"
        
        return prompt
    
    def _parse_response(self, content: str, market_data: Dict, tokens: int) -> AIThesis:
        """Parse AI response to AIThesis."""
        import re
        
        data = None
        
        # Strategy 1: Direct JSON parse
        try:
            data = json.loads(content.strip())
        except:
            pass
        
        # Strategy 2: Extract from markdown code block
        if data is None and "```" in content:
            try:
                json_block = content.split("```")[1]
                if json_block.startswith("json"):
                    json_block = json_block[4:]
                data = json.loads(json_block.strip())
            except:
                pass
        
        # Strategy 3: Find JSON object in text
        if data is None:
            json_match = re.search(r'\{[^}]+\}', content)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except:
                    pass
        
        if data:
            return AIThesis(
                is_arb=data.get('is_arb', False),
                confidence=float(data.get('confidence', 0.0)),
                reasoning=data.get('reason', data.get('reasoning', 'Analysis complete')),
                suggested_action=data.get('action', 'none'),
                markets_analyzed=list(market_data.keys()) if isinstance(market_data, dict) else [],
                cached=False,
                tokens_used=tokens
            )
        
        # Fallback parsing from natural language
        content_lower = content.lower()
        is_arb = 'arbitrage' in content_lower or 'profit' in content_lower or 'buy' in content_lower
        reasoning = content[:150] if content else "Could not parse response"
        
        return AIThesis(
            is_arb=is_arb,
            confidence=0.5 if is_arb else 0.3,
            reasoning=reasoning,
            suggested_action="review",
            markets_analyzed=list(market_data.keys()) if isinstance(market_data, dict) else [],
            cached=False,
            tokens_used=tokens
        )
    
    async def match_markets(self, 
                           market1: str, 
                           market2: str,
                           platform1: str = "Polymarket",
                           platform2: str = "Kalshi") -> Dict:
        """
        Use LLM to semantically match markets across platforms.
        
        Args:
            market1: First market description
            market2: Second market description
            platform1: First platform name
            platform2: Second platform name
            
        Returns:
            Dict with match score and reasoning
        """
        if not self.api_key:
            return {'match': False, 'score': 0.0, 'reason': 'AI disabled'}
        
        await self._init_client()
        
        prompt = f"""Match?
M1 ({platform1}): {market1}
M2 ({platform2}): {market2}

Same event? JSON: {{"match":bool,"score":0-1,"reason":"<10 words"}}"""

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Market matcher. Compare if same event across platforms."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=100,
                response_format={"type": "json_object"}
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"[MiMo] Match error: {e}")
            # Fallback: simple keyword matching
            keywords1 = set(market1.lower().split())
            keywords2 = set(market2.lower().split())
            overlap = len(keywords1 & keywords2) / max(len(keywords1 | keywords2), 1)
            return {
                'match': overlap > 0.5,
                'score': overlap,
                'reason': f'Keyword overlap: {overlap:.0%}'
            }


class AIArbitrageAnalyzer:
    """
    High-level AI analyzer for arbitrage with caching.
    Filters mathematically first, then uses AI only when needed.
    """
    
    def __init__(self, 
                 min_edge_for_ai: float = 0.5,
                 cache_ttl_hours: float = 1.0):
        """
        Args:
            min_edge_for_ai: Minimum edge % to trigger AI analysis
            cache_ttl_hours: How long to cache AI responses
        """
        self.min_edge = min_edge_for_ai
        self.cache = SemanticCache(ttl_hours=cache_ttl_hours)
        self.mimo = MiMoClient()
        
        self._stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'ai_calls': 0,
            'tokens_used': 0
        }
    
    async def analyze(self, 
                      market_data: Dict,
                      edge_pct: float) -> AIThesis:
        """
        Analyze arbitrage opportunity with AI (if needed).
        
        Flow:
        1. Check if edge meets threshold
        2. Check semantic cache
        3. Call AI only if necessary
        4. Cache result
        """
        self._stats['total_requests'] += 1
        
        # Filter 1: Mathematical threshold
        if edge_pct < self.min_edge:
            return AIThesis(
                is_arb=False,
                confidence=0.0,
                reasoning=f"Edge {edge_pct:.2f}% below threshold {self.min_edge}%",
                suggested_action="skip",
                markets_analyzed=[],
                cached=False
            )
        
        # Create cache key from market data
        cache_key = json.dumps(market_data, sort_keys=True)
        
        # Filter 2: Semantic cache
        cached = self.cache.get(cache_key)
        if cached:
            self._stats['cache_hits'] += 1
            return AIThesis(
                is_arb=cached.get('is_arb', False),
                confidence=cached.get('confidence', 0.0),
                reasoning=cached.get('reasoning', ''),
                suggested_action=cached.get('action', 'none'),
                markets_analyzed=cached.get('markets', []),
                cached=True
            )
        
        # Call AI
        self._stats['ai_calls'] += 1
        thesis = await self.mimo.analyze_arbitrage(market_data)
        self._stats['tokens_used'] += thesis.tokens_used
        
        # Cache result
        self.cache.set(cache_key, {
            'is_arb': thesis.is_arb,
            'confidence': thesis.confidence,
            'reasoning': thesis.reasoning,
            'action': thesis.suggested_action,
            'markets': thesis.markets_analyzed
        })
        
        return thesis
    
    def get_stats(self) -> Dict:
        """Get analyzer statistics."""
        hit_rate = 0
        if self._stats['total_requests'] > 0:
            hit_rate = self._stats['cache_hits'] / self._stats['total_requests'] * 100
        
        return {
            **self._stats,
            'cache_hit_rate': hit_rate,
            'cache_stats': self.cache.get_stats()
        }


# ============== DEMO / TESTING ==============

async def demo():
    """Demo the AI integration."""
    print("=" * 70)
    print("AI ARBITRAGE ANALYZER - DEMO")
    print("=" * 70)
    
    # Check API key - support both env var names
    api_key = os.getenv('API_LLM') or os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        print("\n[!] API_LLM not set in .env")
        print("    Add this line to your .env file:")
        print("    API_LLM=sk-or-v1-your_key_here")
        print("\n    Get a key at: https://openrouter.ai/keys")
        return
    
    print(f"\n[+] API Key found: {api_key[:12]}...")
    
    # Initialize
    analyzer = AIArbitrageAnalyzer(min_edge_for_ai=0.3)
    mimo = MiMoClient()
    
    # Test 1: Market matching
    print("\n[Test 1] Market Matching")
    print("-" * 40)
    
    result = await mimo.match_markets(
        market1="Will Trump win the 2024 presidential election?",
        market2="Donald Trump to win 2024 US Presidential Election",
        platform1="Polymarket",
        platform2="Kalshi"
    )
    print(f"  Match: {result.get('match')}")
    print(f"  Score: {result.get('score', 0):.2%}")
    print(f"  Reason: {result.get('reason', 'N/A')}")
    
    # Test 2: Arbitrage analysis
    print("\n[Test 2] Arbitrage Analysis")
    print("-" * 40)
    
    market_data = {
        "Polymarket": {
            "question": "Will BTC hit $100k by March 2026?",
            "yes_price": 0.65,
            "no_price": 0.38
        },
        "Kalshi": {
            "question": "Bitcoin above $100,000 on March 1, 2026",
            "yes_price": 0.58,
            "no_price": 0.45
        }
    }
    
    thesis = await analyzer.analyze(market_data, edge_pct=3.5)
    
    print(f"  Is Arb: {thesis.is_arb}")
    print(f"  Confidence: {thesis.confidence:.0%}")
    print(f"  Action: {thesis.suggested_action}")
    print(f"  Reasoning: {thesis.reasoning}")
    print(f"  Tokens: {thesis.tokens_used}")
    print(f"  Cached: {thesis.cached}")
    
    # Test 3: Cache test
    print("\n[Test 3] Cache Test")
    print("-" * 40)
    
    thesis2 = await analyzer.analyze(market_data, edge_pct=3.5)
    print(f"  Second call cached: {thesis2.cached}")
    
    # Stats
    print("\n[Stats]")
    print("-" * 40)
    stats = analyzer.get_stats()
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  Cache hits: {stats['cache_hits']}")
    print(f"  AI calls: {stats['ai_calls']}")
    print(f"  Tokens used: {stats['tokens_used']}")
    print(f"  Cache hit rate: {stats['cache_hit_rate']:.0f}%")
    
    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(demo())
