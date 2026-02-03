
import re

# Centralized stop words for sports context
STOP_WORDS = {
    'will', 'win', 'on', 'the', 'vs', 'v', 'game', 'match',
    'bet', 'odds', 'score', 'team', 'club', 'united', 'city', 'real', 'soccer',
    'football', 'basket', 'points', 'goals', 'over', 'under', 'total', 'handicap',
    'and', 'or', 'for', 'to', 'be', 'is', 'at', 'by', 'of', 'a', 'an', 'this',
    '2024', '2025', '2026', '2027', '2028',
    'first', 'second', 'third', 'quarter', 'half', 'period', 'championship', 'league',
    'receiving', 'yards', 'assists', 'rebounds', 'player', 'props'
}

# Corporate/Sports suffixes that clutter entity names
ENTITY_SUFFIXES = [
    r'\s+fc$', r'\s+cf$', r'\s+sc$', r'\s+ac$', r'\s+cs$', r'\s+cd$', r'\s+sv$',
    r'\s+s\.a\.d\.$', r'\s+sad$', r'\s+inc$', r'\s+corp$', r'\s+limited$', r'\s+ltd$',
    r'\s+esports$', r'\s+gaming$', r'\s+team$', r'\s+club$',
    r'\s+united$', r'\s+city$', r'\s+real$', r'\s+atletico$', r'\s+sporting$'
]

def clean_entity_name(text: str) -> str:
    """
    Aggressively normalizes entity names by stripping sports/corp suffixes.
    Example: "Girona FC" -> "girona", "Real Madrid CF" -> "madrid" (or "real madrid" depending on order)
    """
    if not text:
        return ""
        
    text = text.lower().strip()
    
    # Remove noise patterns (prefixes like "lol:", "valorant:")
    noise_patterns = [
        r'valorant:', r'cs:go:', r'counter-strike:', r'lol:', r'dota 2:', 
        r'nba:', r'nfl:', r'nhl:', r'mlb:', r'epl:',
        r'bo3', r'bo5', r'map \d', r'game \d', r'round \d'
    ]
    for p in noise_patterns:
        text = re.sub(p, '', text)
        
    # Remove suffixes
    for p in ENTITY_SUFFIXES:
        text = re.sub(p, '', text)
        
    # Remove punctuation
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    
    return text.strip()

def get_clean_tokens(text: str) -> set:
    """Extract significant tokens from text."""
    clean_text = clean_entity_name(text)
    tokens = set()
    for word in clean_text.split():
        if word not in STOP_WORDS and len(word) >= 2:
            tokens.add(word)
    return tokens
