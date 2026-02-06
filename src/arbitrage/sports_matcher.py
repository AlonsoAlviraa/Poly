#!/usr/bin/env python3
"""
Sports Market Matcher using Fuzzy Logic + LLM Hybrid.

This module matches sports prediction markets between platforms using:
1. Fuzzy Matching (thefuzz) - Fast first-pass filter
2. LLM (MiMo-V2-Flash) - Semantic verification for edge cases

Optimized for matching Polymarket match bets with Betfair events.
"""

import os
import asyncio
import json
import logging
import hashlib
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import time

from dotenv import load_dotenv
load_dotenv()

from src.data.dual_lane_resolver import DualLaneResolver
from src.arbitrage.market_mapper import OutcomeMapper
from src.utils.text_utils import clean_entity_name, get_clean_tokens

# Fuzzy matching - 1000x faster than LLM for simple cases
try:
    from thefuzz import fuzz
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False
    fuzz = None

logger = logging.getLogger(__name__)


@dataclass
class SportsMatch:
    """Result of a sports market match."""
    poly_question: str
    poly_id: str
    betfair_event_name: str
    betfair_event_id: str
    betfair_market_id: str
    
    confidence: float
    source: str  # 'llm', 'cache', 'keyword'
    reasoning: str
    
    matched_at: datetime
    mapping: Optional[Dict] = None # {side: 'BACK', runner: '...', market: '...'}
    
    def to_dict(self) -> Dict:
        return {
            'poly_question': self.poly_question,
            'poly_id': self.poly_id,
            'bf_event': self.betfair_event_name,
            'bf_event_id': self.betfair_event_id,
            'confidence': self.confidence,
            'source': self.source,
            'reasoning': self.reasoning,
            'mapping': self.mapping
        }


class SportsMatchingCache:
    """Simple in-memory cache for sports matches with TTL."""
    
    def __init__(self, ttl_hours: float = 24.0):
        self.ttl = ttl_hours * 3600
        self._cache: Dict[str, Dict] = {}
        self._timestamps: Dict[str, float] = {}
        
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0
        }
    
    def _make_key(self, poly_q: str, bf_event: str) -> str:
        """Create cache key from normalized text."""
        combined = f"{poly_q.lower().strip()}|{bf_event.lower().strip()}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def get(self, poly_question: str, bf_event_name: str) -> Optional[Dict]:
        """Get cached match result."""
        key = self._make_key(poly_question, bf_event_name)
        
        if key in self._cache:
            if time.time() - self._timestamps.get(key, 0) < self.ttl:
                self.stats['hits'] += 1
                return self._cache[key]
        
        self.stats['misses'] += 1
        return None
    
    def set(self, poly_question: str, bf_event_name: str, result: Dict):
        """Cache a match result."""
        key = self._make_key(poly_question, bf_event_name)
        self._cache[key] = result
        self._timestamps[key] = time.time()
        self.stats['sets'] += 1
    
    def get_stats(self) -> Dict:
        return {
            **self.stats,
            'entries': len(self._cache),
            'hit_rate': f"{self.stats['hits'] / max(self.stats['hits'] + self.stats['misses'], 1) * 100:.1f}%"
        }


class SportsMarketMatcher:
    """
    Matches sports prediction markets using Hybrid Logic (Entity Resolution + LLM).
    
    Features:
    - Hub & Spoke Entity Resolution (Normalized Names)
    - Pre-filtering with fuzzy matching
    - LLM verification for edge cases
    """
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 cache_ttl_hours: float = 24.0,
                 min_keyword_overlap: float = 0.3,
                 skip_prefilter: bool = False):
        """
        Args:
            api_key: OpenRouter API key
            cache_ttl_hours: Cache TTL
            min_keyword_overlap: Min keyword overlap
            skip_prefilter: Skip pre-filter (Full LLM mode)
        """
        self.api_key = api_key or os.getenv('API_LLM') or os.getenv('OPENROUTER_API_KEY')
        
        # Initialize Dual Lane Resolver (Fast Lane + Slow Lane)
        self.resolver = DualLaneResolver()
        self.mapper = OutcomeMapper()
        
        self.cache = SportsMatchingCache(ttl_hours=cache_ttl_hours)
        self.min_overlap = min_keyword_overlap
        self.skip_prefilter = skip_prefilter
        
        # LLM config
        self.model = "xiaomi/mimo-v2-flash"
        self.base_url = "https://openrouter.ai/api/v1"
        self._client = None
        
        self.stats = {
            'total_attempts': 0,
            'llm_calls': 0,
            'keyword_matches': 0,
            'canonical_matches': 0,  # New stat
            'cache_hits': 0,
            'tokens_used': 0,
            'cache': self.cache.get_stats()
        }
        
        self.fuzz = fuzz if FUZZY_AVAILABLE else None
        
        if self.api_key:
            if self.skip_prefilter:
                logger.info(f"[SportsMatcher] Initialized (Full LLM Mode)")
            else:
                logger.info(f"[SportsMatcher] Initialized (Hybrid Mode: Entities + fuzzy + LLM)")
        else:
            logger.warning("[SportsMatcher] No API key - using Entity/Keyword matching only")
    
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
    
    def _extract_entities(self, text: str) -> set:
        """
        Extract resolved canonical entities from text using DualLaneResolver (Fast Lane).
        Returns a set of Canonical names.
        """
        return self.resolver.fast_resolve(text)
    
    def _keyword_overlap(self, poly_q: str, bf_event: str) -> Tuple[float, set]:
        """Calculate keyword overlap between clean tokens."""
        poly_tokens = self._get_clean_tokens(poly_q)
        bf_tokens = self._get_clean_tokens(bf_event)
        
        if not poly_tokens or not bf_tokens:
            return (0.0, set())

        common = poly_tokens & bf_tokens
        total = len(poly_tokens | bf_tokens)
        
        return (len(common) / max(total, 1), common)
    
    def _get_clean_tokens(self, text: str) -> set:
        """
        Use centralized utility for aggressive tokenization & Normalization.
        """
        return get_clean_tokens(text)
    
    def _entity_guardrail(self, poly_question: str, bf_event_name: str) -> tuple:
        """
        ENTITY GUARDRAIL: Validates that a match shares actual entities.
        """
        # 1. Resolve entities from both sides (Canonical Check - "The Gold Standard")
        poly_entities = self._extract_entities(poly_question)
        bf_entities = self._extract_entities(bf_event_name)
        shared_canonical = poly_entities & bf_entities
        
        if shared_canonical:
            return (True, shared_canonical, f"Shared Canonical: {shared_canonical}")
            
        # 2. Relaxed Token Overlap (User's request)
        poly_tokens = self._get_clean_tokens(poly_question)
        bf_tokens = self._get_clean_tokens(bf_event_name)
        shared_tokens = poly_tokens & bf_tokens
        
        # PASS if: at least 1 strong shared token
        if len(shared_tokens) >= 1:
            return (True, shared_tokens, f"Shared Tokens: {shared_tokens}")
            
        # FAIL
        return (False, set(), f"No matches. PolyTokens={poly_tokens}, BFTokens={bf_tokens}")
    
    def _fuzzy_match(self, poly_question: str, bf_event_name: str) -> Tuple[int, str]:
        """
        Fast fuzzy matching using thefuzz library.
        
        Returns: (score: 0-100, method: str)
        """
        if not FUZZY_AVAILABLE:
            return (0, 'unavailable')
        
        # Normalize strings
        poly_clean = poly_question.lower().replace('?', '').replace('!', '').strip()
        bf_clean = bf_event_name.lower().strip()
        
        # token_sort_ratio handles word order differences
        # "Man City vs Liverpool" matches "Liverpool v Manchester City"
        score = fuzz.token_sort_ratio(poly_clean, bf_clean)
        
        return (score, 'fuzzy')
    
    def _pre_filter_candidates(self, 
                                poly_question: str, 
                                bf_events: List[Dict],
                                max_candidates: int = 10) -> List[Dict]:
        """
        Pre-filter Betfair events using HYBRID approach:
        1. Fuzzy matching (fast, handles variations)
        2. Keyword/entity overlap (catches known entities)
        """
        scored = []
        
        for bf in bf_events:
            bf_name = bf.get('name', '')
            
            # Method 1: Fuzzy matching (primary for match bets)
            fuzzy_score, _ = self._fuzzy_match(poly_question, bf_name)
            
            # Method 2: Keyword/entity overlap (secondary)
            overlap, common = self._keyword_overlap(poly_question, bf_name)
            
            # Combine scores (fuzzy is primary)
            combined_score = fuzzy_score / 100.0  # Normalize to 0-1
            if overlap > 0:
                combined_score = max(combined_score, overlap)  # Take best
            
            # Accept if: fuzzy >= 70 OR keyword overlap >= 0.3 OR shared entity
            if fuzzy_score >= 70 or overlap >= self.min_overlap or len(common) >= 1:
                scored.append({
                    **bf,
                    '_fuzzy_score': fuzzy_score,
                    '_overlap': overlap,
                    '_common': common,
                    '_combined': combined_score
                })
        
        # Sort by combined score (fuzzy + keyword)
        scored.sort(key=lambda x: x.get('_combined', 0), reverse=True)
        
        return scored[:max_candidates]
    
    async def match_single(self, 
                           poly: Dict, 
                           bf_events: List[Dict],
                           trace: Optional[Any] = None) -> Optional[SportsMatch]:
        """
        Match a single Polymarket question to Betfair events.
        """
        poly_question = poly.get('question', '')
        poly_id = poly.get('condition_id', poly.get('id', ''))
        poly_tags = poly.get('tags', [])
        
        self.stats['total_attempts'] += 1
        
        # 0. Sport Viability Filter (Early Exit)
        # Use entities to detect primary category
        entities = self._extract_entities(poly_question)
        category = "unknown"
        if entities:
            canonical = list(entities)[0]
            category = self.resolver.entity_to_category.get(canonical, "unknown")
            
        if trace:
            trace.category = category
            
        if not self.mapper.validate_sport_viability(category, poly_tags):
            logger.debug(f"[Matcher] Skipping non-viable market ({category}): {poly_question[:40]}...")
            if trace:
                trace.add_step("Whitelist", "FAIL", f"Category '{category}' or tags {poly_tags} not viable")
            return None
            
        if trace:
            trace.add_step("Whitelist", "PASS", f"Category '{category}' is viable")
        
        # Step 1: Get candidates
        if self.skip_prefilter:
            # SMART SAMPLING: First try keyword overlap, then add random samples
            # This ensures we check relevant events while still being thorough
            
            # Get keyword-matched candidates (relaxed threshold)
            keyword_candidates = self._pre_filter_candidates(
                poly_question, bf_events, max_candidates=10
            )
            
            # If we found keyword candidates, use them
            if keyword_candidates:
                candidates = keyword_candidates
                logger.debug(f"[Matcher] SMART: Found {len(candidates)} keyword candidates for: {poly_question[:40]}...")
            else:
                # No keyword matches - try harder with word overlap
                poly_words = self._extract_significant_words(poly_question)
                scored = []
                for bf in bf_events:
                    bf_words = self._extract_significant_words(bf.get('name', ''))
                    shared = poly_words & bf_words
                    if shared:
                        scored.append({**bf, '_overlap': len(shared) / max(len(poly_words), 1), '_common': shared})
                
                if scored:
                    scored.sort(key=lambda x: x['_overlap'], reverse=True)
                    candidates = scored[:15]
                    logger.debug(f"[Matcher] SMART: Found {len(candidates)} word-overlap candidates")
                else:
                    # Still nothing - skip this market (no point in random guessing)
                    logger.debug(f"[Matcher] SMART: No candidates for: {poly_question[:40]}...")
                    if trace:
                        trace.add_step("PreFilter", "FAIL", "No keyword or word-overlap candidates in Betfair")
                    return None
        else:
            candidates = self._pre_filter_candidates(poly_question, bf_events)
            
            if not candidates:
                logger.debug(f"[Matcher] No keyword candidates for: {poly_question[:40]}...")
                return None
        
        # Step 2: Check cache (only if using pre-filter)
        if not self.skip_prefilter:
            for cand in candidates:
                bf_name = cand.get('name', '')
                cached = self.cache.get(poly_question, bf_name)
                
                if cached and cached.get('match'):
                    self.stats['cache_hits'] += 1
                    return SportsMatch(
                        poly_question=poly_question,
                        poly_id=poly_id,
                        betfair_event_name=bf_name,
                        betfair_event_id=cand.get('id', ''),
                        betfair_market_id=cand.get('market_id', ''),
                        confidence=cached.get('confidence', 0.8),
                        source='cache',
                        reasoning=cached.get('reasoning', 'Cached match'),
                        matched_at=datetime.now(),
                        mapping=cached.get('mapping')
                    )
            
            # Step 3: Fast Fuzzy/Keyword Match (Skip LLM if confidence is very high)
            best_cand = candidates[0]
            fuzzy_score = best_cand.get('_fuzzy_score', 0)
            overlap = best_cand.get('_overlap', 0)
            common = best_cand.get('_common', set())
            
            # High confidence threshold for automatic matching
            is_strong_fuzzy = fuzzy_score >= 85
            is_strong_keyword = overlap >= 0.7 and len(common) >= 2
            
            if is_strong_fuzzy or is_strong_keyword:
                bf_name = best_cand.get('name', '')
                
                # STILL verify with Guardrail to be 100% sure
                passes, shared, reason = self._entity_guardrail(poly_question, bf_name)
                
                if passes:
                    self.stats['keyword_matches'] += 1
                    source = 'fuzzy' if is_strong_fuzzy else 'keyword'
                    
                    # Outcome Mapping for strong matches
                    mapping_result = self.mapper.map_outcome(
                        poly_question=poly_question,
                        poly_outcome="Yes",
                        canonical_entity=list(shared)[0] if shared else bf_name
                    )
                    
                    match = SportsMatch(
                        poly_question=poly_question,
                        poly_id=poly_id,
                        betfair_event_name=bf_name,
                        betfair_event_id=best_cand.get('id', ''),
                        betfair_market_id=best_cand.get('market_id', ''),
                        confidence=max(fuzzy_score / 100.0, 0.8),
                        source=source,
                        reasoning=f"Automatic {source} match | Shared: {shared}",
                        matched_at=datetime.now(),
                        mapping={
                            'side': mapping_result.side,
                            'runner': mapping_result.selection_name,
                            'market': mapping_result.market_type
                        } if mapping_result.success else None
                    )
                    
                    # Cache it
                    self.cache.set(poly_question, bf_name, {
                        'match': True,
                        'confidence': match.confidence,
                        'reasoning': match.reasoning,
                        'mapping': match.mapping
                    })
                    
                    return match
                else:
                    logger.debug(f"[Matcher] Fast match rejected by guardrail: {poly_question[:40]}... → {bf_name}")
                    # Don't return, let it fall through to LLM for second opinion if needed
                    # but maybe remove this candidate if it's clearly wrong?
                    # For now just continue to LLM.
        
        # Step 4: Use LLM (ALWAYS if skip_prefilter=True or for uncertain cases)
        if not self.api_key:
            return None
        
        await self._init_client()
        
        # Prepare candidates for LLM (use more candidates when skip_prefilter)
        max_llm_candidates = 15 if self.skip_prefilter else 5
        llm_candidates = [
            {"id": c.get("id", ""), "name": c.get("name", "")}
            for c in candidates[:max_llm_candidates]
        ]
        
        # More lenient prompt when skip_prefilter is True
        if self.skip_prefilter:
            prompt = f"""Find the best Betfair event match for this prediction market. Be FLEXIBLE with matching.

Polymarket Question: "{poly_question}"

Betfair Events:
{json.dumps(llm_candidates, indent=2)}

Instructions:
- Match if the events are about the SAME topic (team, tournament, person, award)
- Partial matches are OK (e.g., "Brazil World Cup" matches "Brazil")
- Time differences are OK (2026 prediction can match current tournament odds)
- Return the BEST match even if not 100% certain

Response format (JSON only):
{{"match":true/false,"bf_id":"<event id>","confidence":0.0-1.0,"reason":"<why this matches>"}}"""
        else:
            prompt = f"""Match this sports prediction market to a Betfair event. JSON only.

Polymarket: "{poly_question}"

Betfair events:
{json.dumps(llm_candidates, indent=2)}

Respond: {{"match":true/false,"bf_id":"<id or null>","confidence":0.0-1.0,"reason":"<15 words max>"}}
Only match if SAME event/outcome. Different outcomes = false."""

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Sports market matcher. Match prediction markets to events. Be strict - only match if clearly same event."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=100
            )
            
            content = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0
            
            self.stats['llm_calls'] += 1
            self.stats['tokens_used'] += tokens
            
            # Parse response
            result = self._parse_llm_response(content)
            
            if result.get('match') and result.get('bf_id'):
                bf_id = result['bf_id']
                matched_event = next(
                    (c for c in candidates if c.get('id') == bf_id),
                    None
                )
                
                if matched_event:
                    bf_name = matched_event.get('name', '')
                    
                    # === ENTITY GUARDRAIL ===
                    # Verify the match shares actual entities (team names)
                    passes, shared_entities, guard_reason = self._entity_guardrail(
                        poly_question, bf_name
                    )
                    
                    if not passes:
                        # REJECT: False positive - no shared entities
                        self.stats['guardrail_rejections'] = self.stats.get('guardrail_rejections', 0) + 1
                        logger.debug(f"[Guardrail] ❌ REJECTED: {poly_question[:40]}... → {bf_name}")
                        logger.debug(f"   Reason: {guard_reason}")
                        
                        if trace:
                            trace.add_step("Guardrail", "FAIL", f"Rejected: {guard_reason} for {bf_name}")
                        
                        # Cache as non-match
                        self.cache.set(poly_question, bf_name, {'match': False})
                        return None
                    # === END GUARDRAIL ===
                    
                    if trace:
                        trace.add_step("Guardrail", "PASS", f"Matched with {bf_name} via LLM/Hybrid")
                    
                    # 3. Outcome Mapping (Discovery)
                    # We assume mapping for "Yes" to find the primary side.
                    # The actual order execution will map specifically per outcome.
                    canonical_entity = list(shared_entities)[0] if shared_entities else bf_name
                    mapping_result = self.mapper.map_outcome(
                        poly_question=poly_question,
                        poly_outcome="Yes",
                        canonical_entity=canonical_entity
                    )
                    
                    # 4. Slow Lane Learning (Queue for LLM enrichment if not canonical)
                    if "Shared Tokens" in guard_reason:
                        # LLM confirmed a match but we didn't have canonicals? Learn it.
                        self.resolver.queue_for_learning(
                            poly_text=poly_question,
                            bf_text=bf_name,
                            fuzzy_score=int(result.get('confidence', 0.8) * 100)
                        )
                    
                    match = SportsMatch(
                        poly_question=poly_question,
                        poly_id=poly_id,
                        betfair_event_name=bf_name,
                        betfair_event_id=bf_id,
                        betfair_market_id=matched_event.get('market_id', ''),
                        confidence=result.get('confidence', 0.8),
                        source='llm',
                        reasoning=f"{result.get('reason', 'LLM match')} | Entities: {shared_entities}",
                        matched_at=datetime.now(),
                        mapping={
                            'side': mapping_result.side,
                            'runner': mapping_result.selection_name,
                            'market': mapping_result.market_type
                        } if mapping_result.success else None
                    )
                    
                    # Cache it
                    self.cache.set(poly_question, bf_name, {
                        'match': True,
                        'confidence': match.confidence,
                        'reasoning': match.reasoning,
                        'mapping': match.mapping
                    })
                    
                    return match
            
            # Cache negative result too
            for cand in candidates[:3]:
                self.cache.set(poly_question, cand.get('name', ''), {'match': False})
            
            return None
            
        except Exception as e:
            logger.error(f"[Matcher] LLM error: {e}")
            return None
    
    def _parse_llm_response(self, content: str) -> Dict:
        """Parse LLM JSON response."""
        import re
        
        # Try direct parse
        try:
            return json.loads(content.strip())
        except:
            pass
        
        # Extract JSON from text
        json_match = re.search(r'\{[^}]+\}', content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass
        
        return {'match': False}
    
    async def batch_match(self,
                          poly_markets: List[Dict],
                          bf_events: List[Dict],
                          max_concurrent: int = 10) -> List[SportsMatch]:
        """
        Batch match multiple Polymarket markets using PARALLEL processing.
        
        Args:
            poly_markets: List of Polymarket market dicts
            bf_events: List of Betfair event dicts
            max_concurrent: Max concurrent LLM calls (default 10 for speed)
        """
        matches = []
        total = len(poly_markets)
        
        # Semaphore for rate limiting
        sem = asyncio.Semaphore(max_concurrent)
        
        async def process_one(idx: int, poly: Dict) -> Optional[SportsMatch]:
            async with sem:
                trace = None
                if audit_logger:
                    poly_question = poly.get('question', '')
                    poly_id = poly.get('condition_id', poly.get('id', ''))
                    trace = audit_logger.get_event(poly_id, poly_question)
                    
                match = await self.match_single(
                    poly=poly,
                    bf_events=bf_events,
                    trace=trace
                )
                
                # Progress indicator every 10 markets
                if (idx + 1) % 10 == 0:
                    print(f"   ⏳ Progress: {idx + 1}/{total} markets processed...")
                
                return match
        
        # Process ALL markets in parallel with semaphore limit
        print(f"   🚀 Processing {total} markets ({max_concurrent} parallel)...")
        
        tasks = [process_one(i, poly) for i, poly in enumerate(poly_markets)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect successful matches
        for result in results:
            if isinstance(result, SportsMatch):
                matches.append(result)
                logger.info(f"✅ MATCH: {result.poly_question[:50]}... → {result.betfair_event_name}")
        
        print(f"   ✨ Done! Found {len(matches)} matches from {total} markets")
        
        return matches
    
    def get_stats(self) -> Dict:
        return {
            **self.stats,
            'cache': self.cache.get_stats()
        }


# ============== DEMO ==============

async def demo():
    """Demo the sports market matcher."""
    print("\n" + "=" * 70)
    print("SPORTS MARKET MATCHER DEMO (with LLM)")
    print("=" * 70)
    
    matcher = SportsMarketMatcher()
    
    if not matcher.api_key:
        print("\n⚠️ No API key found. Set API_LLM in .env for LLM matching.")
        print("   Using keyword matching only.\n")
    else:
        print(f"\n✅ API Key: {matcher.api_key[:15]}...\n")
    
    # Sample Polymarket sports questions
    poly_markets = [
        {'question': 'Will Brazil win the 2026 FIFA World Cup?', 'condition_id': 'poly_brazil_wc'},
        {'question': 'Will the Kansas City Chiefs win Super Bowl LX?', 'condition_id': 'poly_chiefs_sb'},
        {'question': 'Will Lionel Messi win the 2026 Ballon d\'Or?', 'condition_id': 'poly_messi_bdor'},
        {'question': 'Will the Lakers win the 2025-26 NBA Championship?', 'condition_id': 'poly_lakers_nba'},
        {'question': 'Will England win Euro 2028?', 'condition_id': 'poly_england_euro'},
    ]
    
    # Sample Betfair events
    bf_events = [
        {'id': 'bf_1', 'name': 'Brazil', 'market_id': '1.200001'},
        {'id': 'bf_2', 'name': 'Argentina', 'market_id': '1.200002'},
        {'id': 'bf_3', 'name': 'Germany', 'market_id': '1.200003'},
        {'id': 'bf_4', 'name': 'Kansas City Chiefs', 'market_id': '1.200004'},
        {'id': 'bf_5', 'name': 'Philadelphia Eagles', 'market_id': '1.200005'},
        {'id': 'bf_6', 'name': 'Messi to win Ballon d\'Or', 'market_id': '1.200006'},
        {'id': 'bf_7', 'name': 'Los Angeles Lakers', 'market_id': '1.200007'},
        {'id': 'bf_8', 'name': 'Boston Celtics', 'market_id': '1.200008'},
        {'id': 'bf_9', 'name': 'England', 'market_id': '1.200009'},
        {'id': 'bf_10', 'name': 'France', 'market_id': '1.200010'},
    ]
    
    print("Testing matches...\n")
    
    for poly in poly_markets:
        match = await matcher.match_single(
            poly_question=poly['question'],
            poly_id=poly['condition_id'],
            bf_events=bf_events
        )
        
        if match:
            print(f"✅ {match.poly_question[:50]}...")
            print(f"   → {match.betfair_event_name}")
            print(f"   Confidence: {match.confidence:.0%} | Source: {match.source}")
            print(f"   Reason: {match.reasoning}\n")
        else:
            print(f"❌ {poly['question'][:50]}...")
            print(f"   No match found\n")
    
    print("\n" + "-" * 40)
    print("Stats:", matcher.get_stats())
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(demo())
