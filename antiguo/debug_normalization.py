import asyncio
from src.core.arbitrage_detector import ArbitrageDetector
from src.utils.normalization import normalize_text

async def debug_matching():
    detector = ArbitrageDetector()
    poly_m, sx_m = await detector.fetch_all_markets()
    
    print(f"Sample Poly Titles:")
    for p in poly_m[:10]:
        title = p.get('title', '')
        print(f"  '{title}' -> '{normalize_text(title)}'")
        
    print(f"\nSample SX Labels:")
    for s in sx_m[:10]:
        label = s.get('label', '')
        print(f"  '{label}' -> '{normalize_text(label)}'")

if __name__ == "__main__":
    asyncio.run(debug_matching())
