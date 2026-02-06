
import re

def normalize_chain(text: str) -> str:
    """
    Normalizes a chain string for comparison.
    1. Lowercase
    2. Remove special chars
    3. Collapse whitespace
    """
    if not text:
        return ""
    
    # Lowercase
    text = text.lower()
    
    # Remove special chars (keep alphanumeric and spaces)
    text = re.sub(r'[^a-z0-9\s]', '', text)
    
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text
