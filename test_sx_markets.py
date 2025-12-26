import asyncio
import aiohttp

async def test_sx_markets():
    base_url = "https://api.sx.bet"
    
    # Test 1: Active markets with pagination
    print("=== Test 1: /markets/active (default) ===")
    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/markets/active"
        async with session.get(url) as response:
            data = await response.json()
            markets = data.get("data", {}).get("markets", [])
            print(f"Total markets: {len(markets)}")
            if markets:
                print(f"Sample market: {markets[0].get('sportLabel', 'N/A')} - {markets[0].get('label', 'N/A')}")
    
    # Test 2: Check if there's pagination
    print("\n=== Test 2: Check for pagination params ===")
    async with aiohttp.ClientSession() as session:
        for page in [0, 1, 2]:
            url = f"{base_url}/markets/active?page={page}"
            async with session.get(url) as response:
                data = await response.json()
                markets = data.get("data", {}).get("markets", [])
                print(f"Page {page}: {len(markets)} markets")
                if not markets:
                    break
    
    # Test 3: Try with limit parameter
    print("\n=== Test 3: Try with limit parameter ===")
    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/markets/active?limit=1000"
        async with session.get(url) as response:
            data = await response.json()
            markets = data.get("data", {}).get("markets", [])
            print(f"With limit=1000: {len(markets)} markets")
    
    # Test 4: Check sports breakdown
    print("\n=== Test 4: Sports breakdown ===")
    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/markets/active"
        async with session.get(url) as response:
            data = await response.json()
            markets = data.get("data", {}).get("markets", [])
            sports = {}
            for m in markets:
                sport = m.get("sportLabel", "Unknown")
                sports[sport] = sports.get(sport, 0) + 1
            
            for sport, count in sorted(sports.items(), key=lambda x: -x[1]):
                print(f"  {sport}: {count} markets")

if __name__ == "__main__":
    asyncio.run(test_sx_markets())
