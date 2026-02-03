import asyncio
from thefuzz import fuzz

# Simulate real data from APIs
POLY_SAMPLES = [
    "AC Milan vs. Genoa CFC",
    "Arsenal FC vs. Liverpool FC", 
    "Real Madrid vs Barcelona",
    "Jaume Munar vs Sebastian Baez",
    "Stefanos Tsitsipas vs Shintaro Mochizuki",
    "2 de Mayo vs Alianza Lima",
    "Liverpool Montevideo vs Independiente Medellin"
]

SX_SAMPLES = [
    "Jaume Munar vs Sebastian Baez",
    "Stefanos Tsitsipas vs Shintaro Mochizuki",
    "2 de Mayo vs Alianza Lima",
    "Liverpool Montevideo vs Independiente Medellín",
    "Carabobo FC vs Huachipato",
    "Juventud de Las Piedras vs Universidad Catolica del Ecuador"
]

def normalize(text):
    import re
    text = text.lower()
    text = re.sub(r'[^a-z\s]', '', text)
    return text.strip()

print("=== Fuzzy Matching Test ===\n")

for poly in POLY_SAMPLES:
    poly_norm = normalize(poly)
    best_score = 0
    best_match = None
    
    for sx in SX_SAMPLES:
        sx_norm = normalize(sx)
        score = fuzz.token_sort_ratio(poly_norm, sx_norm)
        if score > best_score:
            best_score = score
            best_match = sx
    
    status = "[MATCH]" if best_score > 82 else "[NO MATCH]"
    print(f"Poly: '{poly[:40]}'")
    print(f"  Best SX: '{best_match[:40] if best_match else 'None'}' ({best_score}%) {status}")
    print()
