import re

STOP_WORDS = [
    "will", "beat", "win", "winner", "vs", "against", "soccer", 
    "match", "uefa", "champions", "league", "fc", "cf"
]

def normalize_text(text):
    """
    Aggressive text normalization for matching.
    1. Lowercase.
    2. Remove special chars and numbers (years/dates).
    3. Remove stop words.
    """
    if not text:
        return ""
    
    # 1. Lowercase
    text = text.lower()
    
    # 2. Remove special chars and numbers (keep spaces and letters)
    # This removes dates like "2024", "2023"
    text = re.sub(r'[^a-z\s]', '', text)
    
    # 3. Remove Stop Words
    words = text.split()
    cleaned_words = [w for w in words if w not in STOP_WORDS]
    
    return " ".join(cleaned_words).strip()

def decimal_to_probability(decimal_odds):
    """
    Converts decimal odds to implied probability.
    e.g., 2.00 -> 0.50 (50%)
    """
    if decimal_odds <= 0:
        return 0.0
    return 1 / decimal_odds
