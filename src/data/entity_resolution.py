import json
import os
import logging
from typing import Dict, List, Optional, Tuple, Set

logger = logging.getLogger(__name__)

try:
    from thefuzz import fuzz, process
    FUZZY_AVAILABLE = True
except ImportError:
    logger.warning("thefuzz not installed. Fuzzy matching disabled.")
    FUZZY_AVAILABLE = False

class EntityResolver:
    """
    Implements Hub & Spoke Entity Resolution.
    Maps 'dirty' raw names to 'Canonical' IDs/names.
    """
    
    def __init__(self, mappings_path: str = None):
        if mappings_path is None:
            mappings_path = os.path.join(os.path.dirname(__file__), 'mappings.json')
        
        self.mappings_path = mappings_path
        self.canonical_map: Dict[str, str] = {} # alias -> canonical
        self.canonicals: Set[str] = set()       # set of canonical names
        self.categories: Dict[str, Dict] = {}   # full loaded json structure
        
        # Terms that are too generic to resolve safely without context
        self.CONFUSING_TERMS = {
            "united", "city", "real", "fc", "cf", "sc", "club", "atletico", 
            "inter", "ac", "sporting", "racing", "cd", "sv", "manchester", 
            "milan", "madrid", "new york", "los angeles"
        }
        self.PREFERRED_CANONICALS = {
            "man city": "Manchester City",
            "manchester city": "Manchester City"
        }
        
        self._load_mappings()
        
    def _load_mappings(self):
        """Load and flatten the mappings JSON into a lookup table."""
        if not os.path.exists(self.mappings_path):
            logger.warning(f"Mappings file not found at {self.mappings_path}")
            return

        try:
            with open(self.mappings_path, 'r', encoding='utf-8') as f:
                self.categories = json.load(f)
                
            self.canonical_map.clear()
            self.canonicals.clear()
            
            count = 0
            # Handle nested structure: Sport -> Canonical -> [Aliases]
            for sport, entities in self.categories.items():
                if not isinstance(entities, dict):
                    continue
                    
                for canonical, aliases in entities.items():
                    # Register canonical itself
                    self.canonicals.add(canonical)
                    self.canonical_map[canonical.lower()] = canonical
                    
                    # Register aliases
                    for alias in aliases:
                        self.canonical_map[alias.lower()] = canonical
                        count += 1
            
            logger.info(f"[EntityResolver] Loaded {len(self.canonicals)} canonicals and {count} aliases.")
            
        except Exception as e:
            logger.error(f"[EntityResolver] Error loading mappings: {e}")

    def resolve(self, raw_name: str, threshold: int = 85) -> Optional[str]:
        """
        Resolve a raw name to a Canonical Name.
        1. Exact match (case insensitive)
        2. Fuzzy match against aliases & canonicals
        """
        if not raw_name:
            return None
            
        clean_name = raw_name.strip().lower()
        
        # 0. Ambiguity Check
        if clean_name in self.CONFUSING_TERMS:
            logger.debug(f"[EntityResolver] '{raw_name}' is ambiguous. Skipping.")
            return None
        
        # 1. Exact Lookup (O(1))
        if clean_name in self.canonical_map:
            canonical = self.canonical_map[clean_name]
            return self.PREFERRED_CANONICALS.get(clean_name, canonical)
            
        if not FUZZY_AVAILABLE:
            return None

        # 2. Fuzzy Search (O(N)) - "The standard approach"
        # We search against all known keys (canonicals + aliases) in our map
        # process.extractOne returns (match, score, index)
        # We extract from the KEYS of the map to find the best matching alias
        candidates = list(self.canonical_map.keys())
        
        best_match, score = process.extractOne(
             clean_name, 
             candidates, 
             scorer=fuzz.token_sort_ratio
        )
        
        if score >= threshold:
            canonical = self.canonical_map[best_match]
            logger.debug(f"[EntityResolver] Fuzzy resolved: '{raw_name}' -> '{canonical}' (via '{best_match}', score={score})")
            return canonical
            
        return None

    def add_alias(self, canonical: str, alias: str, category: str = "teams"):
        """Add a new alias to a canonical entity and save."""
        if canonical not in self.canonicals:
            logger.warning(f"[EntityResolver] Canonical '{canonical}' does not exist.")
            return

        if category not in self.categories:
            self.categories[category] = {}
            
        raw_aliases = self.categories[category].get(canonical, [])
        if alias not in raw_aliases:
            raw_aliases.append(alias)
            self.categories[category][canonical] = raw_aliases
            
            # Update memory maps
            self.canonical_map[alias.lower()] = canonical
            
            # Persist
            self._save_mappings()
            logger.info(f"[EntityResolver] Learned new alias: '{alias}' -> '{canonical}'")

    def _save_mappings(self):
        try:
            with open(self.mappings_path, 'w', encoding='utf-8') as f:
                json.dump(self.categories, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save mappings: {e}")
