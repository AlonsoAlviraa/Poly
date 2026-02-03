
import aiohttp
import asyncio
import json

async def check_gamma():
    url = "https://gamma-api.polymarket.com/events?limit=1&closed=false&order=volume24hr"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            if data:
                event = data[0]
                print("Event Keys:", event.keys())
                markets = event.get('markets', [])
                if markets:
                    m = markets[0]
                    print("\nMarket Keys:", m.keys())
                    print("\nSample Market Data:\n", json.dumps(m, indent=2))
            else:
                print("No data")

if __name__ == "__main__":
    asyncio.run(check_gamma())
