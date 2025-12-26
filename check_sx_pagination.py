import asyncio
import aiohttp

async def check_sx_pagination():
    base_url = "https://api.sx.bet"
    all_hashes = set()
    async with aiohttp.ClientSession() as session:
        for page in range(5):
            url = f"{base_url}/markets/active?page={page}"
            async with session.get(url) as response:
                data = await response.json()
                markets = data.get("data", {}).get("markets", [])
                new_hashes = {m['marketHash'] for m in markets}
                print(f"Page {page}: {len(markets)} markets. Unique in this page: {len(new_hashes)}")
                
                intersect = all_hashes.intersection(new_hashes)
                if intersect:
                    print(f"  Overlap with previous: {len(intersect)}")
                
                all_hashes.update(new_hashes)
                if not markets:
                    break
                    
    print(f"Total Unique Markets found across 5 pages: {len(all_hashes)}")

if __name__ == "__main__":
    asyncio.run(check_sx_pagination())
