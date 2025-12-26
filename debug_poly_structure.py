import aiohttp
import asyncio
import json

async def fetch_one():
    url = 'https://gamma-api.polymarket.com/events'
    params = {
        'closed': 'false',
        'limit': 1,
        'tag_slug': 'sports'
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            if data:
                event = data[0]
                print(f"Event Title: {event.get('title')}")
                markets = event.get('markets', [])
                if markets:
                    m = markets[0]
                    print(f"Market Question: {m.get('question')}")
                    print(f"clobTokenIds: {m.get('clobTokenIds')}")
                    print(f"outcomes: {m.get('outcomes')}")
                    print(f"outcomePrices: {m.get('outcomePrices')}")
                else:
                    print('No markets in event')
            else:
                print('No data returned')

asyncio.run(fetch_one())
