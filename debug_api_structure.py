import asyncio
import aiohttp
import json

async def debug_api():
    url = "https://gamma-api.polymarket.com/events?closed=false&limit=2"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            print(f"Got {len(data)} events")
            if data:
                event = data[0]
                print(f"Event keys: {list(event.keys())}")
                print(f"Title: {event.get('title')}")
                markets = event.get('markets')
                if markets:
                    print(f"Markets count: {len(markets)}")
                    print(f"First market keys: {list(markets[0].keys())}")
                    print(f"clobTokenIds: {markets[0].get('clobTokenIds')}")
                else:
                    print("No 'markets' key found")
                    # Check if market info is at event level
                    print(f"clobTokenIds at event level: {event.get('clobTokenIds')}")

if __name__ == "__main__":
    asyncio.run(debug_api())
