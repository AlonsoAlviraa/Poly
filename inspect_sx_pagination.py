import asyncio
import aiohttp
import json

BASE_URL = "https://api.sx.bet"

async def probe_keys():
    async with aiohttp.ClientSession() as session:
        print("\n[1] Inspecting Response Structure...")
        async with session.get(f"{BASE_URL}/markets/active") as resp:
            data = await resp.json()
            # Check root keys
            print(f"    Root Keys: {list(data.keys())}")
            
            # Check data keys
            if 'data' in data:
                print(f"    Data Keys: {list(data['data'].keys())}")
                
                # Check if pagination info exists in 'data'
                if 'paginationKey' in data['data']:
                    print(f"    FOUND PAGINATION KEY: {data['data']['paginationKey']}")
                if 'nextKey' in data['data']:
                    print(f"    FOUND NEXT KEY: {data['data']['nextKey']}")
            
            # Check meta keys if any
            if 'meta' in data:
                print(f"    Meta Keys: {list(data['meta'].keys())}")

if __name__ == "__main__":
    asyncio.run(probe_keys())
