
import asyncio
from src.data.gamma_client import GammaAPIClient

async def search_all_tennis():
    client = GammaAPIClient()
    # Check multiple tags or just fetch a lot of markets
    all_markets = []
    # Fetch top volume markets across various tags or just a general list
    raw_markets = await client.get_all_match_markets(limit_per_tag=300)
    
    tennis_keywords = ['tennis', 'nadal', 'alcaraz', 'djokovic', 'atp', 'wta', 'open', 'set', 'match odds']
    found = []
    for m in raw_markets:
        q = m.get('question', '').lower()
        c = m.get('category', '').lower()
        s = m.get('slug', '').lower()
        if any(kw in q for kw in tennis_keywords) or any(kw in c for kw in tennis_keywords) or any(kw in s for kw in tennis_keywords):
            if 'tennis' in c or 'tennis' in q or 'atp' in s or 'wta' in s:
                found.append(m)
    
    print(f"Total Tennis-like markets found across all tags: {len(found)}")
    for m in found[:10]:
        print(f" - [{m.get('category')}] {m['question']}")

if __name__ == "__main__":
    asyncio.run(search_all_tennis())
