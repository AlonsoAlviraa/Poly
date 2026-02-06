
import logging
import json
import os
import re
import unicodedata
from datetime import datetime, timedelta
from typing import List, Set, Optional, Dict, Tuple
from thefuzz import fuzz
from src.config.matching_config import UNIQUE_IDS, COMMON_TOKENS, SPORT_ALIASES
from src.data.cache_manager import CacheManager

logger = logging.getLogger(__name__)

class EntityResolverLogic:
    def __init__(self, mappings_path: str = None):
        if mappings_path is None:
            mappings_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'mappings.json')
        self.mappings_path = mappings_path
        
        # Integración con el nuevo CacheManager (Seeding Layer)
        self.cache_mgr = CacheManager()
        
        self._mappings: Dict[str, Dict[str, List[str]]] = {}
        self._dirty = False
        self._load_mappings()

    def _load_mappings(self):
        try:
            if os.path.exists(self.mappings_path):
                with open(self.mappings_path, 'r', encoding='utf-8') as f:
                    self._mappings = json.load(f)
            else:
                logger.warning(f"Mappings file not found: {self.mappings_path}")
        except Exception as e:
            logger.error(f"Error loading mappings: {e}")

    def get_entity_from_cache(self, name: str, sport: str) -> Optional[str]:
        """
        Paso 0: Intenta resolver usando el CacheManager (datos pre-cargados/ETL).
        Si existe en el JSON de entidades (O(1) RAM), lo devolvemos inmediatamente.
        """
        return self.cache_mgr.get_entity(name, sport)

    def add_mapping(self, canonical: str, alias: str, sport_category: str, auto_save: bool = True):
        """Learn and also update cache for future sessions."""
        # Update classic mappings.json
        target_shard = sport_category.lower()
        for shard_name, aliases in SPORT_ALIASES.items():
            if target_shard == shard_name or target_shard in aliases:
                target_shard = shard_name
                break
        
        if target_shard not in self._mappings:
            self._mappings[target_shard] = {}
        
        shard = self._mappings[target_shard]
        if canonical not in shard:
            shard[canonical] = []
        if alias not in shard[canonical]:
            shard[canonical].append(alias)
            self._dirty = True
        
        if self._dirty and auto_save:
            self.save_mappings()
            
        # Update the new Seed Cache Manager
        self.cache_mgr.save_entity(alias, canonical, sport_category)

    def save_mappings(self):
        if not self._dirty: return
        try:
            with open(self.mappings_path, 'w', encoding='utf-8') as f:
                json.dump(self._mappings, f, indent=4, ensure_ascii=False)
            self._dirty = False
        except Exception as e:
            logger.error(f"Error saving mappings: {e}")

    def date_blocker(self, query_date: datetime, entity_date: datetime) -> bool:
        if abs(query_date - entity_date) >= timedelta(hours=24):
            return False
        return True

    def normalize_player_name(self, name: str) -> str:
        """
        Specialized normalization for athletes.
        - "Sinner, Jannik" -> "Jannik Sinner"
        - "J. Sinner" -> "Sinner"
        """
        name = name.strip()
        
        # 1. Handle "Lastname, Firstname"
        if "," in name:
            parts = [p.strip() for p in name.split(",")]
            if len(parts) == 2:
                name = f"{parts[1]} {parts[0]}"
        
        # 2. Handle "J. Sinner" or "R. Nadal-Parera"
        # Remove single letter initials like "J. " or "J."
        name = re.sub(r"^[A-Z]\.?\s+", "", name)
        
        return name

    def static_matcher(self, 
                       query_text: str, 
                       entity_text: str, 
                       sport_category: str) -> Optional[str]:
        # logger.debug(f"[MATCHER] Q: {query_text} | E: {entity_text}")
        
        # --- 0. KNOWLEDGE BASE CHECK (Cache Manager) ---
        # Resolve both names to their canonical forms using entities.json
        # "Lakers" -> "Los Angeles Lakers"
        # "L.A. Lakers" -> "Los Angeles Lakers"
        # If Canonical(A) == Canonical(B), MATCH.
        
        q_canonical = self.cache_mgr.get_entity(query_text, sport_category)
        e_canonical = self.cache_mgr.get_entity(entity_text, sport_category)
        
        if q_canonical and e_canonical and q_canonical == e_canonical:
            return "MATCH"
            
        # Also check if one resolves to the other directly
        if q_canonical and q_canonical.lower() == entity_text.lower(): return "MATCH"
        if e_canonical and e_canonical.lower() == query_text.lower(): return "MATCH"

        q_norm = query_text.lower().strip()
        e_norm = entity_text.lower().strip()
        
        # 1. Fast exact match (pre-normalization)
        if q_norm == e_norm: return "MATCH"

        def get_clean_tokens(text):
            text = self.normalize_player_name(text).lower()
            # Remove ONLY very generic junk
            # "W" -> Women
            text = re.sub(r'\b(fc|cf|sc|afc|cd|esports|club|de|the|v|vs|u21|u23|fk|sk|al|utd|united|city|town)\b', '', text)
            # Handle accents
            text = "".join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
            # Split on non-alphanumeric
            text = re.sub(r'[^a-z0-9]', ' ', text)
            return set(text.split())

        q_tokens = get_clean_tokens(query_text)
        e_tokens = get_clean_tokens(entity_text)

        synonyms = {
            "man utd": "manchester united",
            "man city": "manchester city",
            "barca": "barcelona",
            "g2": "g2 esports",
            "psg": "paris saint germain"
        }
        
        q_norm_clean = "".join(c for c in unicodedata.normalize('NFD', q_norm) if unicodedata.category(c) != 'Mn')
        q_norm_clean = re.sub(r'[^a-z0-9]', ' ', q_norm_clean)
        
        e_norm_clean = "".join(c for c in unicodedata.normalize('NFD', e_norm) if unicodedata.category(c) != 'Mn')
        e_norm_clean = re.sub(r'[^a-z0-9]', ' ', e_norm_clean)

        for syn, target in synonyms.items():
            if syn in q_norm_clean: q_tokens.update(target.split())
            if syn in e_norm_clean: e_tokens.update(target.split())

        intersection = q_tokens & e_tokens

        # 2.2 Anti-Collision: Rival Check
        rivals = [
            ("city", "united"), 
            ("real", "atletico"), 
            ("paris", "psg"), 
        ]
        # Specific Paris Check (More robust)
        if "paris" in q_tokens and "paris" in e_tokens:
            psg_pats = {"psg", "saint", "germain", "st germain", "saint germain"}
            is_psg_q = any(p in q_norm_clean for p in psg_pats) or any(p in q_tokens for p in psg_pats)
            is_psg_e = any(p in e_norm_clean for p in psg_pats) or any(p in e_tokens for p in psg_pats)
            if is_psg_q != is_psg_e: return None # One is PSG, other is likely Paris FC
            
        for r1, r2 in rivals:
            if (r1 in q_tokens and r2 in e_tokens) or (r2 in q_tokens and r1 in e_tokens):
                return None

        ratio = fuzz.token_set_ratio(query_text, entity_text)
        if ratio >= 85: return "MATCH" # Relaxed from 95
        
        # Intersection logic
        if intersection:
            # If all tokens of one are in the other
            if len(intersection) == len(q_tokens) or len(intersection) == len(e_tokens):
                # But don't match purely generic things
                if intersection - {'fc', 'club', 'team', 'real'}:
                    return "MATCH"

        if q_norm_clean in e_norm_clean or e_norm_clean in q_norm_clean:
            if len(intersection) >= 1: 
                return "MATCH"
                
        # --- 2. DYNAMIC NAME NORMALIZATION (Structural Fix for "J. Sinner") ---
        # Instead of hardcoding 475 aliases, we parse the structure of the name.
        
        def normalize_human_name(name: str) -> dict:
            n = name.lower().replace('.', ' ').strip()
            # "Sinner, J" -> "j sinner"
            if ',' in n:
                parts = n.split(',')
                if len(parts) == 2:
                    return {'first': parts[1].strip(), 'last': parts[0].strip()}
            
            parts = n.split()
            if len(parts) >= 2:
                # Heuristic: Last token is surname
                return {'first': " ".join(parts[:-1]), 'last': parts[-1]}
            return {'first': '', 'last': n}

        q_parsed = normalize_human_name(query_text)
        e_parsed = normalize_human_name(entity_text)
        
        # LOGIC: Surname MUST match. First name parsed must be compatible.
        if q_parsed['last'] and e_parsed['last']:
            # Check Surname (Allowing 'Garfia' in 'Alcaraz Garfia')
            surname_match = (q_parsed['last'] == e_parsed['last']) or \
                            (q_parsed['last'] in e_parsed['last']) or \
                            (e_parsed['last'] in q_parsed['last'])
                            
            if surname_match:
                # Check First Name Compatibility
                # q="jannik", e="j" -> Match
                # q="j", e="jannik" -> Match
                # q="carlos", e="jannik" -> Mismatch
                f1 = q_parsed['first']
                f2 = e_parsed['first']
                
                if not f1 or not f2:
                    # ONE missing first name -> Ambiguous but likely match if sport/time aligns
                    # For now, require STRICT context or accept as loose match
                    return "MATCH"
                
                # Initial check
                if f1 and f2 and f1[0] == f2[0]:
                    return "MATCH"
                    
        # --- 3. ORGANIZATION NORMALIZATION (Structural Fix for "Carabobo FC") ---
        # Remove "legal" suffixes
        legal_suffixes = [' fc', ' cf', ' cd', ' bc', ' sc', ' united', ' city', ' club']
        
        def strip_suffixes(t):
            for s in legal_suffixes:
                if t.endswith(s):
                    return t[:-len(s)].strip()
            return t
            
        q_org = strip_suffixes(q_norm)
        e_org = strip_suffixes(e_norm)
        
        if q_org == e_org and len(q_org) > 3:
            return "MATCH"

        try:
            t_set = fuzz.token_set_ratio(q_norm_clean, e_norm_clean)
            if t_set >= 90: return "MATCH"
        except: pass
        
        return None

# Singleton instance
_resolver = None

def get_resolver():
    global _resolver
    if _resolver is None:
        _resolver = EntityResolverLogic()
    return _resolver

def date_blocker(query_date: datetime, entity_date: datetime) -> bool:
    return get_resolver().date_blocker(query_date, entity_date)

def static_matcher(query_text: str, entity_text: str, sport_category: str) -> Optional[str]:
    return get_resolver().static_matcher(query_text, entity_text, sport_category)
