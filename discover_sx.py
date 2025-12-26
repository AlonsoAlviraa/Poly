import asyncio
import aiohttp

async def discover_sx_leagues():
    base_url = "https://api.sx.bet"
    async with aiohttp.ClientSession() as session:
        # Get sports
        async with session.get(f"{base_url}/sports") as resp:
            sports = await resp.json()
            print("Sports:")
            for s in sports.get('data', []):
                print(f"  {s.get('sportLabel')} (ID: {s.get('sportId')})")
                
        # Get all leagues
        async with session.get(f"{base_url}/leagues") as resp:
            leagues = await resp.json()
            print("\nLeagues (First 20):")
            for l in leagues.get('data', [])[:20]:
                print(f"  {l.get('leagueLabel')} (Sport: {l.get('sportLabel')})")

if __name__ == "__main__":
    asyncio.run(discover_sx_leagues())
