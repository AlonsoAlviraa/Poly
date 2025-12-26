import asyncio
import aiohttp

async def test_sx_pagination():
    """Test SX Bet API with nextKey pagination"""
    base_url = "https://api.sx.bet"
    all_markets = []
    seen_hashes = set()
    
    async with aiohttp.ClientSession() as session:
        next_key = ""
        page = 0
        
        while page < 20:  # Safety limit
            url = f"{base_url}/markets/active"
            if next_key:
                url += f"?nextKey={next_key}"
            
            print(f"Fetching page {page}...")
            
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    print(f"Error: {response.status}")
                    break
                
                data = await response.json()
                markets = data.get("data", {}).get("markets", [])
                next_key = data.get("data", {}).get("nextKey")
                
                print(f"  Got {len(markets)} markets, nextKey: {next_key[:20] if next_key else 'None'}...")
                
                for m in markets:
                    h = m.get("marketHash")
                    if h and h not in seen_hashes:
                        seen_hashes.add(h)
                        all_markets.append(m)
                
                if not next_key:
                    break
                    
                page += 1
    
    print(f"\nTOTAL UNIQUE MARKETS: {len(all_markets)}")
    
    # Show sports breakdown
    sports = {}
    for m in all_markets:
        s = m.get("sportLabel", "Unknown")
        sports[s] = sports.get(s, 0) + 1
    
    print("\nBreakdown by Sport:")
    for sport, count in sorted(sports.items(), key=lambda x: -x[1]):
        print(f"  {sport}: {count}")

if __name__ == "__main__":
    asyncio.run(test_sx_pagination())
