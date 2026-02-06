"""
Cross-Platform Market Mapper (Optimized).
"""

import os
import json
import logging
import time
import bisect
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
from dotenv import load_dotenv

load_dotenv()

# Import Validator & Vector Matcher
from src.arbitrage.arbitrage_validator import ArbitrageValidator
from src.arbitrage.entity_resolver_logic import date_blocker, static_matcher, get_resolver
from src.arbitrage.ai_mapper import get_ai_mapper
from src.arbitrage.ml_match_classifier import HybridMatchClassifier
from src.utils.sx_normalizer import SXNormalizer

# Attempt Vector Matcher import
try:
    from src.arbitrage.vector_matcher import VectorMatcher
except ImportError:
    VectorMatcher = None

try:
    from thefuzz import fuzz
except ImportError:
    fuzz = None

logger = logging.getLogger(__name__)

from src.arbitrage.models import MarketMapping, ArbOpportunity

# Import Validator & Vector Matcher

class CrossPlatformMapper:
    def __init__(self, min_ev_threshold: float = -100.0):
        self.min_ev = min_ev_threshold
        self.resolver = get_resolver() # CACHE LAYER
        self.ai_mapper = get_ai_mapper() 
        self.vector_matcher = VectorMatcher() if VectorMatcher else None
        self._token_cache: Dict[str, set] = {}
        self._negative_match_cache: Dict[Tuple[str, str], bool] = {}
        self._prompted_cache: Dict[Tuple[str, str], bool] = {}
        self._ml_classifier = HybridMatchClassifier.load_if_available()
        
        self.stats = {
            'mapping_attempts': 0,
            'successful_mappings': 0,
            'cache_hits': 0,
            'vector_hits': 0,
            'ai_hits': 0
        }
        
    def _harvest_orphan(self, poly_q, best_candidate, score, sport):
        """Phase 1: Harvest unmatched candidate for offline learning."""
        try:
            import json
            queue_path = "data/learning/unmatched_queue.json"
            
            # Load existing
            try:
                with open(queue_path, 'r', encoding='utf-8') as f:
                    queue = json.load(f)
            except:
                queue = []
                
            # Create entry
            entry = {
                "poly_name": poly_q,
                "bf_candidate": best_candidate.get('name') or best_candidate.get('event_name'),
                "bf_market_id": best_candidate.get('market_id') or best_candidate.get('id'),
                "score": score,
                "sport": sport,
                "date": datetime.now().isoformat()
            }
            
            # Avoid duplicates
            if not any(q['poly_name'] == entry['poly_name'] and q['bf_candidate'] == entry['bf_candidate'] for q in queue):
                queue.append(entry)
                with open(queue_path, 'w', encoding='utf-8') as f:
                    json.dump(queue, f, indent=2)
            self._persist_temporal_event({
                "type": "near_miss",
                "poly_name": entry["poly_name"],
                "bf_candidate": entry["bf_candidate"],
                "bf_market_id": entry["bf_market_id"],
                "score": score,
                "sport": sport,
            })
        except Exception as e:
            logger.warning(f"Failed to harvest orphan: {e}")

    async def map_market(self, 
                         poly_market: Dict, 
                         betfair_events: List[Dict],
                         polymarket_slug: Optional[str] = None,
                         sport_category: str = "soccer",
                         bf_buckets: Optional[Dict[Any, List[Dict]]] = None) -> Optional[MarketMapping]:
        """
        Main Mapping Pipeline:
        1. Date Blocker (Filter candidates)
        2. Static Matcher (Exact/Known matches)
        3. Resolver Cache (Previous AI results)
        4. Vector Matcher (Semantic search)
        5. AI Auto-Mapper (LLM - Last Resort)
        """
        self.stats['mapping_attempts'] += 1
        poly_question = poly_market.get('question', '')
        poly_question_low = poly_question.lower()
        poly_id = str(poly_market.get('id', ''))
        resolver = self._get_market_resolver(poly_question)
        poly_fingerprint = poly_market.get('_market_fingerprint') or self._market_fingerprint_from_text(
            poly_question, market_type=poly_market.get('market_type')
        )
        poly_market['_market_fingerprint'] = poly_fingerprint
        
        # --- 1. DATE BLOCKER ---
        candidates = self._apply_date_blocker(poly_market, betfair_events, bf_buckets)
        if not candidates:
            return None

        # --- SX BET "VS" SPLITTER (Authorized via SXNormalizer Tool) ---
        # Robustly handle different separators (vs, v, @, -) using the specialized tool
        expanded_candidates = []
        for ev in candidates:
            # Use the tool to generate [Original, Team A, Team B]
            # Verify if this is an SX event or just apply generally (safer for all exchanges?)
            # Applying to all allows catching "Real Madrid - Barcelona" on Betfair too.
            normalized_list = SXNormalizer.expand_candidates(ev)
            expanded_candidates.extend(normalized_list)
        
        candidates = expanded_candidates

        # --- 2. STATIC MATCHER ---
        for ev in candidates:
            bf_name = ev.get('name') or ev.get('event_name', '')
            bf_id = str(ev.get('id') or ev.get('market_id') or '')
            if poly_id and bf_id and self._negative_match_cache.get((poly_id, bf_id)):
                continue

            ev_fingerprint = ev.get('_market_fingerprint') or self._market_fingerprint_from_text(
                bf_name, market_type=ev.get('market_type')
            )
            ev['_market_fingerprint'] = ev_fingerprint
            if poly_fingerprint and ev_fingerprint and poly_fingerprint != ev_fingerprint:
                continue
            
            # Anti-Hallucination: Both teams must have some overlap
            if not self._verify_team_overlap(poly_question_low, bf_name.lower(), sport_category, allow_fuzzy=False):
                if poly_id and bf_id:
                    self._negative_match_cache[(poly_id, bf_id)] = True
                continue

            match_status = static_matcher(poly_question, bf_name, sport_category)
            
            if match_status == "MATCH":
                # Check sport cross-check
                if not self._sport_cross_check(poly_market, ev, sport_category):
                    continue
                
                if not resolver["semantic_check"](poly_question, ev):
                    continue

                sel_id, sel_name = resolver["selection_resolver"](poly_question, ev.get('runners', []), sport_category)
                
                # PERSISTENCE (Agent Memory): Save static match to avoid recalculation/splitting overhead
                self.resolver.add_mapping(canonical=poly_question, alias=bf_name, sport_category=sport_category)
                # self.resolver.save_mappings() # Optional: Save immediately or let cache manager handle it
                
                mapping = self._create_mapping(poly_market, ev, bf_name, 1.0, 'static_v2', sel_id, sel_name, sport_category)
                self._persist_temporal_event({
                    "type": "match",
                    "poly_id": poly_id,
                    "bf_market_id": mapping.betfair_market_id,
                    "bf_event_id": mapping.betfair_event_id,
                    "fingerprint": poly_fingerprint,
                    "confidence": mapping.confidence,
                    "source": mapping.source,
                    "sport": sport_category,
                })
                return mapping

        # --- 3. CACHE CHECK (RESOLVER) ---
        # Check if we already resolved this Polygon question to ANY of the candidates
        # Currently the resolver maps "Canonical" -> "Alias". 
        # We can scan candidates to see if any match what we have in cache.
        # Ideally, 'static_matcher' uses the resolver internally, but let's double check.
        # Actually `static_matcher` DOES check the loaded mappings. So step 2 covers this.
        
        # --- 4. VECTOR MATCHER ---
        if self.vector_matcher:
            # Vector matcher searches the whole DB, but we should prioritize our candidates.
            # However, VectorMatcher usually indexes everything. 
            # For efficiency, we trust VectorMatcher to return candidates, then validte against our date-blocked list.
            matches, _ = self.vector_matcher.find_matches(poly_question, top_k=3)
            
            for meta, score in matches:
                if score > 0.85:
                    # Check if this vector match is in our date-valid candidates
                    matched_ev = next((e for e in candidates if str(e.get('id','')) == str(meta['id'])), None)
                    if matched_ev:
                        # Anti-Hallucination
                        if not self._verify_team_overlap(poly_question_low, meta['name'].lower(), sport_category, allow_fuzzy=False):
                            continue
                        if not self._sport_cross_check(poly_market, matched_ev, sport_category):
                            continue
                        
                        if not resolver["semantic_check"](poly_question, matched_ev):
                            continue

                        self.stats['vector_hits'] += 1
                        sel_id, sel_name = resolver["selection_resolver"](poly_question, matched_ev.get('runners', []), sport_category)
                        mapping = self._create_mapping(poly_market, matched_ev, meta['name'], score, 'vector', sel_id, sel_name, sport_category)
                        self._persist_temporal_event({
                            "type": "match",
                            "poly_id": poly_id,
                            "bf_market_id": mapping.betfair_market_id,
                            "bf_event_id": mapping.betfair_event_id,
                            "fingerprint": poly_fingerprint,
                            "confidence": mapping.confidence,
                            "source": mapping.source,
                            "sport": sport_category,
                        })
                        return mapping

        # --- 5. AI AUTO-MAPPER (LLM) ---
        # Only proceed if we have candidates and AI is enabled
        if self.ai_mapper.enabled and candidates:
            # Optimization: Try only top 3 candidates by Jaccard to save tokens
            top_candidates = self._pre_rank_candidates(poly_question, candidates)
            
            for ev in top_candidates[:3]:
                bf_name = ev.get('name', '')
                low_conf_queue = ev.get('_pre_rank_jaccard', 0.0) < 0.15
                
                # Check negative cache if possible? (Resolver doesn't support it yet)
                
                # --- 5.1 SEMANTIC & TEAM CHECK ---
                if not resolver["semantic_check"](poly_question, ev):
                    continue

                if not self._verify_team_overlap(poly_question_low, bf_name.lower(), sport_category, allow_fuzzy=low_conf_queue):
                    bf_id = str(ev.get('id') or ev.get('market_id') or '')
                    if poly_id and bf_id:
                        prompted_key = (poly_id, bf_id)
                        prompted_result = self._prompted_cache.get(prompted_key)
                        if prompted_result is None:
                            is_match, confidence = await self.ai_mapper.check_similarity(poly_question, bf_name, sport_category)
                            prompted_result = is_match and confidence >= 0.92
                            self._prompted_cache[prompted_key] = prompted_result
                        if not prompted_result:
                            ml_score = self._ml_classifier.predict_proba(poly_question, bf_name)
                            if ml_score < 0.75:
                                continue
                    else:
                        continue

                # Sport Cross-Check again
                if not self._sport_cross_check(poly_market, ev, sport_category):
                    continue
                
                is_match, confidence = await self.ai_mapper.check_similarity(poly_question, bf_name, sport_category)
                if is_match and confidence >= 0.90:
                    # MEMORIZE IT!
                    self.resolver.add_mapping(canonical=poly_question, alias=bf_name, sport_category=sport_category)
                    self.resolver.save_mappings() # Persist immediate
                    
                    self.stats['ai_hits'] += 1
                    sel_id, sel_name = resolver["selection_resolver"](poly_question, ev.get('runners', []), sport_category)
                    mapping = self._create_mapping(poly_market, ev, bf_name, confidence, 'ai_auto_mapper', sel_id, sel_name, sport_category)
                    self._persist_temporal_event({
                        "type": "match",
                        "poly_id": poly_id,
                        "bf_market_id": mapping.betfair_market_id,
                        "bf_event_id": mapping.betfair_event_id,
                        "fingerprint": poly_fingerprint,
                        "confidence": mapping.confidence,
                        "source": mapping.source,
                        "sport": sport_category,
                    })
                    return mapping
        
        # --- 6. ORPHAN HARVESTING (The Collector) ---
        # If we reached here, NO match was found (returns None).
        # We should check if vector matcher found something "close but not enough".
        
        # We need to run vector matcher search again OR reuse results if we had them.
        # Ideally, we should have captured the 'best rejected' in step 4.
        # But step 4 returns immediately on hit.
        
        # Retro-active Vector Check for Orphans:
        if self.vector_matcher:
            matches, _ = self.vector_matcher.find_matches(poly_question, top_k=2) # Get top 2 for context
            
            # DEBUG DUMP: Capture what the vector matcher sees
            try:
                debug_entry = {
                    "poly": poly_question, 
                    "matches": [{"name": m[0]['name'], "score": m[1]} for m in matches]
                }
                with open("data/learning/debug_vectors.json", "a", encoding="utf-8") as f:
                    import json
                    f.write(json.dumps(debug_entry) + "\n")
            except: pass

            if matches:
                meta, score = matches[0]
                # Thresholds: Lowered to 0.40 to capture weak matches
                if 0.40 <= score < 0.85:
                    # Find the event object
                    orphan_ev = next((e for e in candidates if str(e.get('id','')) == str(meta['id'])), None)
                    if orphan_ev:
                         self._harvest_orphan(poly_question, orphan_ev, score, sport_category)
                    else:
                        # Fallback: If not in candidates (date blocked?), try to harvest anyway if score is decent
                        # But we need the ID/MarketID which is in meta? meta has 'id' and 'name'.
                        # Let's trust meta for the name at least.
                        if score > 0.60:
                             # Create synthetic rejection for analysis
                             fake_ev = {'name': meta['name'], 'id': meta['id'], 'market_id': meta.get('market_id')}
                             self._harvest_orphan(poly_question, fake_ev, score, sport_category)
        
        return None

    def _is_semantically_compatible(self, poly_q: str, bf_ev: Dict) -> bool:
        """Centralized check for market type and numerical consistency."""
        poly_q_low = poly_q.lower()
        bf_type = bf_ev.get('market_type', 'MATCH_ODDS')
        bf_name = bf_ev.get('name', '').lower()
        
        is_ou = any(x in poly_q_low for x in ['over', 'under', 'o/u', 'total'])
        is_spread = any(x in poly_q_low for x in ['spread', 'handicap', 'line'])
        is_btts = any(x in poly_q_low for x in ['btts', 'both teams to score', 'ambos marcan'])
        
        # SX Bet Bypass: SX often has empty market_type, so we trust name match
        if bf_type == '' or bf_type is None:
            return True

        if is_ou:
            # If Poly is O/U, BF must be O/U (or skipped if empty)
            if 'OVER_UNDER' not in bf_type and bf_type != '': return False
        elif is_spread:
            # If Poly is Spread, BF must be Handicap/Asian Handicap (or skipped if empty)
            if 'HANDICAP' not in bf_type and 'ASIAN_HANDICAP' not in bf_type and bf_type != '': return False
        elif is_btts:
            # If Poly is BTTS, BF must be BOTH_TEAMS_TO_SCORE (or skipped if empty)
            if 'BOTH_TEAMS_TO_SCORE' not in bf_type and bf_type != '': return False
        else:
            # Must be a Winner/Moneyline/1X2 type
            if any(x in bf_type for x in ['OVER_UNDER', 'HANDICAP', 'BOTH_TEAMS_TO_SCORE']): return False
            if bf_type not in ['MATCH_ODDS', 'WINNER', 'MONEY_LINE', 'HEAD_TO_HEAD']:
                # Allow some flexibility for soccer 'MATCH_ODDS'
                if bf_type != 'MATCH_ODDS': return False

        # 2. Numerical Value Filter (for O/U and Spreads)
        if is_ou or is_spread:
            p_val = self._extract_line_value(poly_q_low)
            # BF value might be in market name or market description
            bf_val = self._extract_line_value(bf_name)
            
            if p_val is not None and bf_val is not None:
                if abs(p_val - bf_val) > 0.01: return False
            else:
                # If we're an O/U or Spread, we MUST have a line value to match
                return False
                
        return True

    def _sport_cross_check(self, poly, bf_ev, sport_cat):
        """Prevent matching different leagues/sports."""
        p_slug = str(poly.get('slug', '')).lower()
        p_cat = str(poly.get('category', '')).lower()
        bf_name = str(bf_ev.get('name', '')).lower()
        bf_comp = str(bf_ev.get('competition', '')).lower()
        bf_region = str(bf_ev.get('_region_tag', '')).lower()
        
        # 1. NCAAB vs NBA
        if ('ncaab' in p_slug or 'college-basketball' in p_slug) and ('nba' in bf_name):
            return False
        if ('nba' in p_slug) and ('ncaa' in bf_name or 'college basketball' in bf_name):
            return False
        
        # 2. League consistency (Soccer)
        if sport_cat == 'soccer':
            league_map = {
                'premier-league': ['premier league', 'england premier league'],
                'la-liga': ['la liga', 'laliga'],
                'serie-a': ['serie a', 'italy serie a'],
                'bundesliga': ['bundesliga'],
                'ligue-1': ['ligue 1', 'ligue1'],
                'ucl': ['champions league', 'uefa champions league'],
                'europa-league': ['europa league', 'uefa europa league'],
            }
            for league_key, league_names in league_map.items():
                if league_key in p_slug or any(name in p_slug for name in league_names):
                    if bf_comp:
                        if not any(name in bf_comp for name in league_names):
                            return False
                    else:
                        # No competition label; keep soft pass but log if needed
                        pass

        # 3. Hard filter when competition is available
        if bf_comp:
            league_tokens = {
                'nba': ['nba'],
                'wnba': ['wnba'],
                'ncaa': ['ncaa', 'college'],
                'atp': ['atp'],
                'wta': ['wta'],
                'mlb': ['mlb', 'major league'],
                'nfl': ['nfl'],
                'nhl': ['nhl', 'hockey'],
            }
            for key, tokens in league_tokens.items():
                if any(t in p_slug or t in p_cat for t in tokens):
                    if not any(t in bf_comp for t in tokens):
                        return False

        # 4. Region/geography consistency (batch-merge guardrail)
        if bf_region:
            region_tokens = {
                'england': ['england', 'premier league', 'efl', 'fa cup'],
                'spain': ['spain', 'la liga', 'laliga', 'copa del rey'],
                'italy': ['italy', 'serie a', 'coppa italia'],
                'germany': ['germany', 'bundesliga', 'dfb'],
                'france': ['france', 'ligue 1', 'ligue1'],
                'usa': ['usa', 'mlb', 'nba', 'nfl', 'nhl', 'wnba'],
            }
            for region, tokens in region_tokens.items():
                if any(t in p_slug or t in p_cat for t in tokens):
                    if bf_region != region:
                        return False
            
        return True

    def _get_market_resolver(self, poly_q: str) -> Dict[str, Any]:
        """Route to specialized resolvers by market type (draw, totals, spreads, BTTS)."""
        q_low = poly_q.lower()
        is_ou = any(x in q_low for x in ['over', 'under', 'o/u', 'total'])
        is_spread = any(x in q_low for x in ['spread', 'handicap', 'line'])
        is_btts = any(x in q_low for x in ['btts', 'both teams to score', 'ambos marcan'])
        is_draw = 'draw' in q_low or 'empate' in q_low

        if is_ou:
            return {
                "semantic_check": self._is_semantically_compatible,
                "selection_resolver": self._resolve_over_under_selection,
            }
        if is_spread:
            return {
                "semantic_check": self._is_semantically_compatible,
                "selection_resolver": self._resolve_spread_selection,
            }
        if is_btts:
            return {
                "semantic_check": self._is_semantically_compatible,
                "selection_resolver": self._resolve_btts_selection,
            }
        if is_draw:
            return {
                "semantic_check": self._is_semantically_compatible,
                "selection_resolver": self._resolve_draw_selection,
            }
        return {
            "semantic_check": self._is_semantically_compatible,
            "selection_resolver": self._resolve_winner_selection,
        }

    def _verify_team_overlap(self, poly_text: str, bf_text: str, sport: str, allow_fuzzy: bool = False) -> bool:
        """Ensure that both 'teams' or at least significant identifiers overlap."""
        import re
        # Robust split for various vs. formats
        # SX Bet often uses "Team A vs Team B" format in the event name itself.
        # We need to explicitly parse this to handle "Team A" and "Team B" as separate entities.
        
        def parse_versus_format(text: str) -> List[str]:
             # 1. Normalize
             t = text.lower()
             # 2. Split on common separators
             # Priority: " vs ", " @ ", " - "
             if " vs " in t: return [s.strip() for s in t.split(" vs ")]
             if " @ " in t: return [s.strip() for s in t.split(" @ ")]
             # Careful with "-" as it can be in names like "Saint-Germain"
             if " - " in t: return [s.strip() for s in t.split(" - ")]
             return [t] # No split found

        def normalize_side(text: str) -> str:
            t = text.lower().strip()
            if sport == 'soccer':
                t = t.replace("utd", "united")
                t = t.replace("man city", "manchester city")
                t = t.replace("man utd", "manchester united")
                t = t.replace("psg", "paris saint germain")
            return t

        # If bf_text (Exchange Event) looks like "A vs B", split it effectively to treat it as 2 sides
        bf_sides = [
            normalize_side(s)
            for part in parse_versus_format(bf_text)
            for s in re.split(r' vs\.? | v\.? | @ | - ', part)
            if len(s.strip()) > 2
        ]
        
        # Poly sides split
        p_sides = [
            normalize_side(s.strip())
            for s in re.split(r' vs\.? | v\.? | @ | - ', poly_text)
            if len(s.strip()) > 2
        ]
        
        if not p_sides or not bf_sides: return True 
        
        # Helper to get significant tokens
        def get_sig_tokens(text):
            # Remove very common words, keep nouns/names
            stop = {'the', 'and', 'for', 'will', 'win', 'match', 'odds', 'ends', 'draw', 'both', 'teams', 'score', 'end'}
            text_key = text.lower().strip()
            cached = self._token_cache.get(text_key)
            if cached is not None:
                return cached
            tokens = set(re.findall(r'\w+', text_key))
            cleaned = tokens - stop
            self._token_cache[text_key] = cleaned
            return cleaned

        # If it's a "Vs" match (2 sides), we need overlap on both sides or a very strong single match
        matches_per_p_side = []
        generic = {'city', 'united', 'fc', 'bc', 'real', 'st', 'st.', 'san', 'santa', 'state', 'tech', 'university', 'univ', 'college'}
        negative_dict = {
            'soccer': {'city', 'united', 'real', 'atletico'},
            'basketball': {'state', 'st'},
            'baseball': {'sox', 'state'},
            'tennis': {'jr', 'sr'},
        }
        bf_tokens_list = [(bf_side, get_sig_tokens(bf_side)) for bf_side in bf_sides]
        for p_side in p_sides:
            p_tokens = get_sig_tokens(p_side)
            found_match = False
            for bf_side, bf_tokens in bf_tokens_list:
                intersection = p_tokens & bf_tokens
                # If they share at least one significant token
                if intersection:
                    # Special check for generic tokens
                    if len(intersection) == 1 and list(intersection)[0] in generic:
                        # For common names, we need at least a partial match of the WHOLE side
                        # e.g., "Man City" vs "Manchester City" -> "city" overlaps, "man" matches "manchester"
                        # Simply check if the LONGER name contains a significant portion of the SHORTER one
                        p_clean = p_side.replace('fc', '').replace('bc', '').strip()
                        bf_clean = bf_side.replace('fc', '').replace('bc', '').strip()
                        if p_clean in bf_clean or bf_clean in p_clean or (len(p_tokens & bf_tokens) > 1):
                            found_match = True
                    else:
                        # STRICT US SPORTS CHECK
                        # If overlap is good but one has "state" and other doesn't, FAIL logic
                        has_p_state = 'state' in p_tokens or 'st' in p_tokens
                        has_bf_state = 'state' in bf_tokens or 'st' in bf_tokens
                        if has_p_state != has_bf_state:
                             # "Illinois" vs "Illinois State" -> mismatch
                             found_match = False
                        else:
                             # Require at least one non-generic token overlap for soccer
                             if sport == 'soccer' and intersection <= generic:
                                 found_match = False
                             else:
                                 negatives = negative_dict.get(sport, set())
                                 if negatives and ((p_tokens & negatives) ^ (bf_tokens & negatives)):
                                     found_match = False
                                 else:
                                     found_match = True
                if found_match: break
            matches_per_p_side.append(found_match)
        
        # Success criteria: 
        # If 2 sides in Poly, both must have a match in BF
        if len(p_sides) >= 2:
            return all(matches_per_p_side)
            
        if any(matches_per_p_side):
            return True

        # Fallback: allow strong fuzzy match on full names to expand coverage
        if allow_fuzzy and fuzz:
            full_score = fuzz.token_set_ratio(poly_text, bf_text)
            if full_score >= 92:
                return True

        return False

    def _extract_line_value(self, text: str) -> Optional[float]:
        """Extract the numeric line value from text (e.g., 2.5, -4.5, 220.5)."""
        import re
        # Look for patterns like "o/u 2.5", "(-3.5)", "220.5 points", etc.
        # Handles optional +/- and decimals
        matches = re.findall(r'([+-]?\d+\.?\d*)', text)
        if not matches:
            return None
        
        # We usually want the LAST number in a market description as it's often the line
        # e.g., "Over 2.5" -> 2.5
        # e.g., "Lakers (-3.5)" -> -3.5
        try:
            return float(matches[-1])
        except:
            return None

    def _market_fingerprint_from_text(self, text: str, market_type: Optional[str] = None) -> Optional[str]:
        if not text:
            return None
        q_low = text.lower()
        base_type = market_type or ''
        if not base_type:
            if any(x in q_low for x in ['over', 'under', 'o/u', 'total']):
                base_type = 'TOTALS'
            elif any(x in q_low for x in ['spread', 'handicap', 'line']):
                base_type = 'SPREAD'
            elif any(x in q_low for x in ['btts', 'both teams to score', 'ambos marcan']):
                base_type = 'BTTS'
            elif 'draw' in q_low or 'empate' in q_low:
                base_type = 'DRAW'
            else:
                base_type = 'WINNER'

        line = self._extract_line_value(q_low)
        period = 'full_time'
        if any(x in q_low for x in ['1h', '1st half', 'primer tiempo', 'first half']):
            period = 'first_half'
        elif any(x in q_low for x in ['2h', '2nd half', 'second half', 'segundo tiempo']):
            period = 'second_half'
        elif 'quarter' in q_low or 'q1' in q_low or 'q2' in q_low:
            period = 'quarter'

        if base_type in {'TOTALS', 'SPREAD'} and line is not None:
            return f"{base_type}:{line}:{period}"
        if base_type:
            return f"{base_type}:{period}"
        return None

    def _persist_temporal_event(self, payload: Dict[str, Any]) -> None:
        try:
            os.makedirs("data/learning", exist_ok=True)
            payload["timestamp"] = datetime.now().isoformat()
            with open("data/learning/temporal_events.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception as exc:
            logger.debug(f"Failed to persist temporal event: {exc}")

    def _create_mapping(self, poly, ev, bf_name, conf, source, selection_id=None, selection_name=None, sport="unknown"):
        return MarketMapping(
            polymarket_id=poly.get('condition_id') or poly.get('id'),
            polymarket_question=poly.get('question', ''),
            betfair_event_id=ev.get('event_id') or ev.get('id', ''),
            betfair_market_id=ev.get('market_id') or ev.get('id', ''), 
            betfair_event_name=bf_name,
            confidence=conf,
            mapped_at=datetime.now(),
            source=source,
            polymarket_slug=poly.get('slug'),
            bf_selection_id=str(selection_id) if selection_id else None,
            bf_runner_name=selection_name,
            market_type=ev.get('market_type'),
            exchange=ev.get('exchange', 'bf'),
            sport=sport
        )

    def _resolve_draw_selection(self, poly_q: str, bf_runners: List[Dict], sport: str) -> Tuple[Optional[str], Optional[str]]:
        """Resolver for draw markets."""
        if not bf_runners:
            return None, None
        draw_runner = next(
            (r for r in bf_runners if 'draw' in r.get('runnerName', '').lower() or 'empate' in r.get('runnerName', '').lower()),
            None,
        )
        if draw_runner:
            return str(draw_runner.get('selectionId')), draw_runner.get('runnerName')
        return None, None

    def _resolve_btts_selection(self, poly_q: str, bf_runners: List[Dict], sport: str) -> Tuple[Optional[str], Optional[str]]:
        """Resolver for both-teams-to-score markets."""
        if not bf_runners:
            return None, None
        yes_runner = next(
            (r for r in bf_runners if r.get('runnerName', '').lower() in {'yes', 'sí'}),
            None,
        )
        if yes_runner:
            return str(yes_runner.get('selectionId')), yes_runner.get('runnerName')
        return None, None

    def _resolve_over_under_selection(self, poly_q: str, bf_runners: List[Dict], sport: str) -> Tuple[Optional[str], Optional[str]]:
        """Resolver for totals markets."""
        if not bf_runners:
            return None, None
        q_low = poly_q.lower()
        if 'over' in q_low or 'más de' in q_low:
            over_runner = next(
                (r for r in bf_runners if 'over' in r.get('runnerName', '').lower() or 'más' in r.get('runnerName', '').lower()),
                None,
            )
            if over_runner:
                return str(over_runner.get('selectionId')), over_runner.get('runnerName')
        if 'under' in q_low or 'menos de' in q_low:
            under_runner = next(
                (r for r in bf_runners if 'under' in r.get('runnerName', '').lower() or 'menos' in r.get('runnerName', '').lower()),
                None,
            )
            if under_runner:
                return str(under_runner.get('selectionId')), under_runner.get('runnerName')
        return None, None

    def _resolve_spread_selection(self, poly_q: str, bf_runners: List[Dict], sport: str) -> Tuple[Optional[str], Optional[str]]:
        """Resolver for spread/handicap markets."""
        return self._resolve_winner_selection(poly_q, bf_runners, sport)

    def _resolve_winner_selection(self, poly_q: str, bf_runners: List[Dict], sport: str) -> Tuple[Optional[str], Optional[str]]:
        """Resolver for standard match-winner markets."""
        if not bf_runners:
            return None, None
        q_low = poly_q.lower()
        best_runner = None
        max_overlap = 0
        def get_sig(t):
            stop = {'the', 'win', 'will', 'match', 'odds', 'fc', 'bc', 'st', 'san', 'club', 'de', 'vs', 'and'}
            import re
            return set(re.findall(r'\w+', t.lower())) - stop

        q_sig = get_sig(q_low)
        
        # 4.1 BASKETBALL SPECIFIC SYNNONYMS
        if sport == 'basketball':
            basket_syns = {
                '76ers': 'philadelphia', 'sixers': 'philadelphia',
                'cavs': 'cleveland', 'mavs': 'dallas',
                'blazers': 'portland', 'wolves': 'minnesota',
                'okc': 'oklahoma', 'bucks': 'milwaukee'
            }
            for syn, target in basket_syns.items():
                if syn in q_low: q_sig.add(target)

        # 4.2 CITY TEAM PROTECTION (e.g. Paris FC vs PSG)
        if 'paris' in q_low and 'st-g' not in q_low and 'saint' not in q_low:
             q_sig.add('paris_fc_only')

        for r in bf_runners:
            r_name = r.get('runnerName', '').lower()
            if not r_name: continue
            
            # Apply Synonyms to Runner Name too
            r_sig = get_sig(r_name)
            if sport == 'basketball':
                for syn, target in basket_syns.items():
                    if syn in r_name: r_sig.add(target)

            if 'paris' in r_name and 'st-g' not in r_name and 'saint' not in r_name:
                 r_sig.add('paris_fc_only')

            overlap = len(q_sig & r_sig)
            if overlap > max_overlap:
                max_overlap = overlap
                best_runner = r

        # Threshold: At least one token overlap or special case
        if best_runner and max_overlap > 0:
            return str(best_runner.get('selectionId')), best_runner.get('runnerName')
            
        return None, None

    def _apply_date_blocker(self, poly_market, betfair_events, bf_buckets=None):
        poly_date = poly_market.get('_event_date_parsed')
        poly_region = poly_market.get('_region_tag') or 'global'
        
        # Fallback date parsing
        if not poly_date:
            poly_start_str = poly_market.get('gameStartTime') or poly_market.get('startDate')
            if poly_start_str:
                try:
                    poly_start_str = str(poly_start_str).replace('Z', '+00:00')
                    poly_date = datetime.fromisoformat(poly_start_str)
                except: pass
        
        if not poly_date:
            return [] # Can't map without date

        # Bucketing Optimization
        valid_candidates = []
        if bf_buckets:
            target_date = poly_date.date()
            target_hour_bucket = poly_date.hour // 6
            candidates = (
                bf_buckets.get((target_date, target_hour_bucket, poly_region), []) +
                bf_buckets.get((target_date, target_hour_bucket, 'global'), []) +
                bf_buckets.get((target_date - timedelta(days=1), target_hour_bucket, poly_region), []) +
                bf_buckets.get((target_date + timedelta(days=1), target_hour_bucket, poly_region), []) +
                bf_buckets.get(('NO_DATE', 'NO_TIME', 'global'), [])
            )
            # Fine-grain check: Strict for dated events, skip for undated (SX)
            valid_candidates = []
            for ev in candidates:
                ev_dt = ev.get('_start_date_parsed')
                if ev_dt is None:
                    valid_candidates.append(ev)
                elif date_blocker(poly_date, ev_dt):
                    valid_candidates.append(ev)
        else:
            # Classic Loop
            for ev in betfair_events:
                 bf_date = ev.get('_start_date_parsed')
                 if not bf_date:
                     start = ev.get('openDate')
                     if start:
                         try: bf_date = datetime.fromisoformat(start.replace('Z', '+00:00'))
                         except: continue
                 
                 if bf_date and date_blocker(poly_date, bf_date):
                     valid_candidates.append(ev)
        
        return valid_candidates

    def _pre_rank_candidates(self, poly_q: str, bf_events: List[Dict]) -> List[Dict]:
        poly_tokens = self._token_cache.get(poly_q.lower())
        if poly_tokens is None:
            poly_tokens = set(poly_q.lower().split())
            self._token_cache[poly_q.lower()] = poly_tokens
        scored = []
        for ev in bf_events:
            bf_name = ev.get('name') or ev.get('event_name', '')
            bf_tokens = self._token_cache.get(bf_name.lower())
            if bf_tokens is None:
                bf_tokens = set(bf_name.lower().split())
                self._token_cache[bf_name.lower()] = bf_tokens
            intersection = poly_tokens.intersection(bf_tokens)
            union = poly_tokens.union(bf_tokens)
            score = len(intersection)
            jaccard = len(intersection) / max(len(union), 1)
            ev['_pre_rank_jaccard'] = jaccard
            scored.append((score, ev))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [x[1] for x in scored]
