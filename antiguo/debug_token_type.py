import aiohttp
import asyncio
import json

async def check():
    # Use proper URL
    url = "https://gamma-api.polymarket.com/events?limit=1&closed=false&tag_slug=sports"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            if not data:
                print("No data")
                return
                
            m = data[0]['markets'][0]
            raw_ids = m.get('clobTokenIds')
            
            print(f"RAW clobTokenIds: {raw_ids}")
            print(f"Type of clobTokenIds: {type(raw_ids)}")
            
            if isinstance(raw_ids, str):
                print("IT IS A STRING! Parsing json...")
                parsed = json.loads(raw_ids)
                print(f"Parsed: {parsed}, Type: {type(parsed)}")
                t = parsed[0]
            elif isinstance(raw_ids, list):
                print("IT IS A LIST")
                t = raw_ids[0]
            
            print(f"Target Token: {t}")
            print(f"Type: {type(t)}")

asyncio.run(check())
