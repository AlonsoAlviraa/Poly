
import asyncio
import logging
from src.data.gamma_client import GammaAPIClient

logging.basicConfig(level=logging.INFO)

async def search_polymarket_tennis_broad():
    gamma = GammaAPIClient()
    print("\n" + "="*60)
    print("🌊 POLYMARKET TENNIS BROAD SEARCH")
    print("="*60)
    
    # Method 1: Search by text "Tennis"
    print("\n>> [1/2] Searching by text 'Tennis'...")
    results_text = gamma.get_markets(closed=False, limit=100, query="Tennis")
    print(f"✅ Found {len(results_text)} markets matching 'Tennis' query.")
    for m in results_text[:10]:
        print(f"   - {m.get('question')} | Cat: {m.get('category')} | Tags: {m.get('tags')}")

    # Method 2: Search for names like "Alcaraz", "Nadal", "Djokovic", "Sinner"
    print("\n>> [2/2] Searching for specific player names...")
    players = ["Alcaraz", "Nadal", "Djokovic", "Sinner", "Sabalenka", "Swiatek"]
    for p in players:
        p_res = gamma.get_markets(closed=False, limit=10, query=p)
        print(f"   - Query '{p}': {len(p_res)} found.")
        for m in p_res:
            print(f"     - {m.get('question')}")

if __name__ == "__main__":
    asyncio.run(search_polymarket_tennis_broad())
