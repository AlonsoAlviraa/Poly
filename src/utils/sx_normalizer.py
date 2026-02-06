"""
SX Bet Normalizer Tool.
Handles the parsing and normalization of SX Bet event names, specifically handling
various "Versus" formats to split events into searchable team entities.
"""

import re
from typing import List, Dict, Optional

class SXNormalizer:
    """
    Normalizes SX Bet event names and generates virtual candidates for matching.
    """
    
    # Common separators in betting markets
    SEPARATORS = [
        r'\s+vs\.?\s+',  # " vs ", " vs. "
        r'\s+v\.?\s+',   # " v ", " v. "
        r'\s+@\s+',      # " @ "
        r'\s+-\s+'       # " - " (Careful with hyphenated names)
    ]
    
    # Compile regex for performance
    SPLIT_REGEX = re.compile('|'.join(SEPARATORS), re.IGNORECASE)
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Basic cleaning of event names."""
        return name.strip()

    @staticmethod
    def expand_candidates(event: Dict) -> List[Dict]:
        """
        Takes a raw SX event and returns a list of candidates:
        1. The original event.
        2. Virtual event for Team A (if split possible).
        3. Virtual event for Team B (if split possible).
        
        Args:
            event: The raw event dictionary (must have 'name' or 'label')
            
        Returns:
            List of event dictionaries (including virtual ones).
        """
        candidates = [event]
        
        name = event.get('name') or event.get('label') or ''
        if not name:
            return candidates
            
        # Attempt to split
        parts = SXNormalizer.SPLIT_REGEX.split(name)
        
        # We only care if we get exactly 2 parts (Team A and Team B)
        # If we get > 2, it's ambiguous or a complex name, safer to keep original only?
        # Actually, split might return 3 if multiple separators... 
        # But regex split usually splits on ALL occurrences.
        # "Team A vs Team B" -> ["Team A", "Team B"]
        
        if len(parts) == 2:
            team_a = parts[0].strip()
            team_b = parts[1].strip()
            
            if len(team_a) > 2 and len(team_b) > 2:
                # Create Virtual Candidate A
                cand_a = event.copy()
                cand_a['name'] = team_a
                cand_a['_original_name'] = name
                cand_a['_is_virtual'] = True
                cand_a['_virtual_side'] = 'home'
                
                # Create Virtual Candidate B
                cand_b = event.copy()
                cand_b['name'] = team_b
                cand_b['_original_name'] = name
                cand_b['_is_virtual'] = True
                cand_b['_virtual_side'] = 'away'
                
                candidates.extend([cand_a, cand_b])
                
        return candidates

    @staticmethod
    def get_search_tokens(name: str) -> set:
        """Extract significant search tokens."""
        stop_words = {'the', 'fc', 'cf', 'bc', 'sc', 'united', 'city', 'real', 'club', 'de', 'vs', 'v', 'and'}
        tokens = set(re.findall(r'\w+', name.lower()))
        return {t for t in tokens if t not in stop_words and len(t) > 2}
