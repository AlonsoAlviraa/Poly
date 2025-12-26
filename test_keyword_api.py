import asyncio
import aiohttp

async def test_keyword_search():
    url = "https://gamma-api.polymarket.com/events"
    
    keywords = ["Points", "LeBron", "Assists"]
    
    async with aiohttp.ClientSession() as session:
        for kw in keywords:
            params = {
                "q": kw,
                "closed": "false",
                "limit": 5
            }
            
            async with session.get(url, params=params) as response:
                print(f"\n=== Keyword: '{kw}' ===")
                print(f"Status: {response.status}")
                print(f"URL: {response.url}")
                
                if response.status == 200:
                    data = await response.json()
                    print(f"Results: {len(data)}")
                    for i, evt in enumerate(data[:3]):
                        print(f"  {i+1}. {evt.get('title')}")
                else:
                    print(await response.text())

if __name__ == "__main__":
    asyncio.run(test_keyword_search())
