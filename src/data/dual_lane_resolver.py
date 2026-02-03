#!/usr/bin/env python3
"""
Dual Lane Entity Resolution System.

Fast Lane: Real-time scanning using local JSON only. Maximum speed.
Slow Lane: Async learner that analyzes misses with LLM and enriches the mapping database.

Architecture:
[Polymarket: "Pisa SC"] --No Match--> [Pending Queue] --> [LLM Analyzes] --> [New Alias] --> [Update JSON]
"""

import json
import os
import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class PendingMatch:
    """A match candidate that needs LLM analysis."""
    poly_text: str
    bf_text: str
    fuzzy_score: int
    timestamp: datetime = field(default_factory=datetime.now)
    attempts: int = 0


class DualLaneResolver:
    """
    Implements Fast Lane / Slow Lane entity resolution.
    
    Fast Lane: Instant lookup from local mappings.json (O(1))
    Slow Lane: Queue of misses for LLM enrichment (async background)
    """
    
    def __init__(self, mappings_path: str = None, max_pending: int = 100):
        if mappings_path is None:
            mappings_path = os.path.join(os.path.dirname(__file__), 'mappings.json')
        
        self.mappings_path = mappings_path
        self.max_pending = max_pending
        
        # Fast Lane Data Structures
        self.canonical_map: Dict[str, str] = {}  # alias.lower() -> Canonical
        self.entity_to_category: Dict[str, str] = {} # canonical -> category
        self.canonicals: Set[str] = set()
        self.categories: Dict[str, Dict] = {}
        
        # Slow Lane Data Structures
        self.pending_queue: deque = deque(maxlen=max_pending)
        self.learned_this_session: Dict[str, str] = {}  # New aliases discovered
        
        # Blacklist for ambiguous terms
        self.CONFUSING_TERMS = {
            "united", "city", "real", "fc", "cf", "sc", "club", "atletico",
            "inter", "ac", "sporting", "racing", "cd", "sv", "vs", "v",
            "esports", "gaming", "team"
        }
        
        self._load_mappings()
        logger.info(f"[DualLane] Loaded {len(self.canonicals)} canonicals, {len(self.canonical_map)} aliases")
    
    def _load_mappings(self):
        """Load and flatten mappings from JSON."""
        if not os.path.exists(self.mappings_path):
            logger.warning(f"[DualLane] Mappings not found: {self.mappings_path}")
            return
        
        try:
            with open(self.mappings_path, 'r', encoding='utf-8') as f:
                self.categories = json.load(f)
            
            self.canonical_map.clear()
            self.canonicals.clear()
            self.entity_to_category.clear()
            
            for category, entities in self.categories.items():
                if not isinstance(entities, dict):
                    continue
                
                for canonical, aliases in entities.items():
                    self.canonicals.add(canonical)
                    self.entity_to_category[canonical] = category
                    self.canonical_map[canonical.lower()] = canonical
                    
                    for alias in aliases:
                        if alias:
                            self.canonical_map[alias.lower()] = canonical
                            
        except Exception as e:
            logger.error(f"[DualLane] Load error: {e}")
    
    # =========================================================================
    # FAST LANE: Instant Resolution (No LLM, No Network)
    # =========================================================================
    
    def fast_resolve(self, text: str) -> Set[str]:
        """
        FAST LANE: Extract canonical entities from text using local mappings only.
        Returns set of canonical names found. O(n) where n = words in text.
        """
        if not text:
            return set()
        
        found = set()
        text_lower = text.lower()
        
        # Strategy 1: Check each known alias against text
        for alias, canonical in self.canonical_map.items():
            if len(alias) >= 3 and alias in text_lower:
                # Avoid partial matches for short terms
                if alias in self.CONFUSING_TERMS:
                    continue
                found.add(canonical)
        
        return found
    
    def fast_match(self, poly_text: str, bf_text: str) -> Tuple[bool, Set[str]]:
        """
        FAST LANE: Check if two texts share canonical entities.
        Returns (is_match, shared_entities).
        """
        poly_entities = self.fast_resolve(poly_text)
        bf_entities = self.fast_resolve(bf_text)
        
        shared = poly_entities & bf_entities
        return (len(shared) > 0, shared)
    
    # =========================================================================
    # SLOW LANE: Queueing & Learning
    # =========================================================================
    
    def queue_for_learning(self, poly_text: str, bf_text: str, fuzzy_score: int):
        """
        SLOW LANE: Add a potential match to the learning queue.
        These will be analyzed later by the LLM enricher.
        """
        pending = PendingMatch(
            poly_text=poly_text,
            bf_text=bf_text,
            fuzzy_score=fuzzy_score
        )
        self.pending_queue.append(pending)
        logger.debug(f"[SlowLane] Queued: {poly_text[:40]}... <-> {bf_text[:40]}...")
    
    def add_learned_alias(self, canonical: str, new_alias: str, category: str = "learned"):
        """
        SLOW LANE: Add a new alias discovered by LLM analysis.
        Persists to JSON immediately.
        """
        new_alias_lower = new_alias.lower()
        
        # Avoid duplicates
        if new_alias_lower in self.canonical_map:
            return
        
        # Add to runtime maps
        self.canonical_map[new_alias_lower] = canonical
        self.learned_this_session[new_alias_lower] = canonical
        
        # Add to category structure
        if category not in self.categories:
            self.categories[category] = {}
        
        if canonical not in self.categories[category]:
            self.categories[category][canonical] = []
        
        self.categories[category][canonical].append(new_alias)
        
        # Persist immediately
        self._save_mappings()
        logger.info(f"[SlowLane] Learned: '{new_alias}' -> '{canonical}'")
    
    def _save_mappings(self):
        """Persist current mappings to JSON."""
        try:
            with open(self.mappings_path, 'w', encoding='utf-8') as f:
                json.dump(self.categories, f, indent=4, sort_keys=True, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[DualLane] Save error: {e}")
    
    def get_pending_batch(self, batch_size: int = 10) -> List[PendingMatch]:
        """Get a batch of pending matches for LLM processing."""
        batch = []
        for _ in range(min(batch_size, len(self.pending_queue))):
            if self.pending_queue:
                batch.append(self.pending_queue.popleft())
        return batch
    
    def get_stats(self) -> Dict:
        """Return resolver statistics."""
        return {
            "canonicals": len(self.canonicals),
            "aliases": len(self.canonical_map),
            "pending_queue": len(self.pending_queue),
            "learned_this_session": len(self.learned_this_session),
            "categories": list(self.categories.keys())
        }


# =============================================================================
# SLOW LANE WORKER: Background LLM Enrichment
# =============================================================================

class SlowLaneWorker:
    """
    Async worker that processes the pending queue and enriches mappings.
    Uses LLM to analyze potential entity matches.
    """
    
    def __init__(self, resolver: DualLaneResolver, llm_client=None):
        self.resolver = resolver
        self.llm_client = llm_client
        self.running = False
    
    async def process_pending(self):
        """Process one batch of pending matches."""
        batch = self.resolver.get_pending_batch(batch_size=5)
        
        if not batch:
            return 0
        
        enriched = 0
        for item in batch:
            # Use LLM to analyze if these are actually the same entity
            result = await self._analyze_with_llm(item)
            
            if result and result.get('is_match'):
                canonical = result.get('canonical_name')
                new_alias = result.get('poly_alias')
                category = result.get('category', 'learned')
                
                if canonical and new_alias:
                    self.resolver.add_learned_alias(canonical, new_alias, category)
                    enriched += 1
        
        return enriched
    
    async def _analyze_with_llm(self, item: PendingMatch) -> Optional[Dict]:
        """
        Use LLM to determine if Poly and BF texts refer to the same entity.
        Returns dict with canonical_name, poly_alias, category if match found.
        """
        if not self.llm_client:
            # Fallback: Simple heuristic if no LLM available
            return self._heuristic_analyze(item)
        
        # TODO: Implement actual LLM call
        # For now, use heuristic
        return self._heuristic_analyze(item)
    
    def _heuristic_analyze(self, item: PendingMatch) -> Optional[Dict]:
        """
        Simple heuristic analysis without LLM.
        Extracts common significant words.
        """
        if item.fuzzy_score < 60:
            return None
        
        # Extract significant tokens
        poly_tokens = self._get_tokens(item.poly_text)
        bf_tokens = self._get_tokens(item.bf_text)
        
        common = poly_tokens & bf_tokens
        
        if len(common) >= 1:
            # Use Betfair name as canonical (cleaner format usually)
            canonical = item.bf_text
            new_alias = item.poly_text
            
            return {
                'is_match': True,
                'canonical_name': canonical,
                'poly_alias': new_alias,
                'category': 'learned'
            }
        
        return None
    
    def _get_tokens(self, text: str) -> Set[str]:
        """Extract significant tokens from text."""
        stopwords = {
            'will', 'win', 'on', 'the', 'vs', 'v', 'fc', 'sc', 'game', 'match',
            '2024', '2025', '2026', 'over', 'under', 'spread', 'points', 'goals'
        }
        
        tokens = set()
        for word in text.lower().split():
            clean = ''.join(c for c in word if c.isalnum())
            if len(clean) >= 3 and clean not in stopwords:
                tokens.add(clean)
        
        return tokens


# =============================================================================
# INTEGRATION HELPER
# =============================================================================

def create_dual_lane_system(mappings_path: str = None) -> Tuple[DualLaneResolver, SlowLaneWorker]:
    """Factory function to create the complete dual-lane system."""
    resolver = DualLaneResolver(mappings_path)
    worker = SlowLaneWorker(resolver)
    return resolver, worker
