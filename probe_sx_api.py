import asyncio
import aiohttp
import json

BASE_URL = "https://api.sx.bet"

async def probe():
    async with aiohttp.ClientSession() as session:
        # 1. Fetch Sports
        print("\n[1] Fetching /sports...")
        async with session.get(f"{BASE_URL}/sports") as resp:
            if resp.status == 200:
                data = await resp.json()
                sports = data.get('data', [])
                print(f"    Found {len(sports)} sports.")
                for s in sports:
                    print(f"    - ID: {s.get('sportId')} | Label: {s.get('label')}")
            else:
                print(f"    Error: {resp.status}")

        # 2. Probe /markets/active default
        print("\n[2] Probing /markets/active (No params)...")
        async with session.get(f"{BASE_URL}/markets/active") as resp:
            data = await resp.json()
            mkts = data.get('data', {}).get('markets', [])
            print(f"    Returned {len(mkts)} markets.")

        # 3. Probe /markets/active with pagination guess
        print("\n[3] Probing /markets/active?paginationKey=... or limit?")
        # Try common params
        for param in ['limit=1000', 'pageSize=1000', 'size=1000']:
            async with session.get(f"{BASE_URL}/markets/active?{param}") as resp:
                data = await resp.json()
                mkts = data.get('data', {}).get('markets', [])
                print(f"    Params '{param}': Returned {len(mkts)} markets.")

        # 4. Probe per Sport (if sports found)
        # Using hardcoded IDs if fetch failed, or dynamic
        # Based on user info: Soccer=5. Let's try Tennis if visible in list.
        # Let's try getting markets for Sport ID 5 (Soccer) explicitly
        print("\n[4] Probing /markets/active?sportId=5 (Soccer)...")
        async with session.get(f"{BASE_URL}/markets/active?sportId=5") as resp:
            data = await resp.json()
            mkts = data.get('data', {}).get('markets', [])
            print(f"    Returned {len(mkts)} markets for Soccer.")

if __name__ == "__main__":
    asyncio.run(probe())
