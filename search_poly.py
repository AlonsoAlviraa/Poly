import asyncio
from src.collectors.polymarket import PolymarketClient

async def search_poly():
    client = PolymarketClient()
    events = await client.search_events_async()
    print(f"Total: {len(events)}")
    
    targets = ["Munar", "Baez", "Tsitsipas", "Milan", "Arsenal"]
    for t in targets:
        matches = [e['title'] for e in events if t.lower() in e['title'].lower()]
        print(f"'{t}': {len(matches)} matches")
        for m in matches[:3]:
            print(f"  - {m}")

if __name__ == "__main__":
    asyncio.run(search_poly())
