import asyncio
import aiohttp
from src.collectors.bookmakers import BookmakerClient

async def main():
    client = BookmakerClient()
    # Create manual session
    async with aiohttp.ClientSession() as session:
        print("Fetching NBA Player Points (Debug)...")
        # Manual request to control params fully
        url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"
        params = {
            "apiKey": client.api_key,
            "regions": "us", 
            "markets": "h2h", # Fallback to h2h to test key
            "oddsFormat": "decimal",
        }
        
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                print(f"Fetched {len(data)} events (H2H).")
                if data:
                    first_id = data[0].get("id")
                    print(f"Testing Event ID: {first_id}")
                    
                    # Now fetch props for this ID
                    url_event = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{first_id}/odds"
                    params_event = {
                        "apiKey": client.api_key,
                        "regions": "us",
                        "markets": "player_points",
                        "oddsFormat": "decimal",
                    }
                    async with session.get(url_event, params=params_event) as resp_event:
                        print(f"Event Props Status: {resp_event.status}")
                        if resp_event.status == 200:
                            data_event = await resp_event.json()
                            b = data_event.get("bookmakers", [])
                            if b:
                                print(f"Bookmaker: {b[0].get('key')}")
                                for m in b[0].get("markets", []):
                                    print(f"Market: {m.get('key')}")
                                    for o in m.get("outcomes", [])[:3]:
                                        print(f" - {o}")
                        else:
                            print(await resp_event.text())
            else:
                print(await response.text())

if __name__ == "__main__":
    asyncio.run(main())
