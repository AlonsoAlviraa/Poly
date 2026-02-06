
import asyncio
from src.data.gamma_client import GammaAPIClient
from src.data.betfair_client import BetfairClient

async def check_tennis():
    client = GammaAPIClient()
    # Check Tennis tag
    markets = await client.get_all_match_markets(limit_per_tag=100)
    tennis_markets = [m for m in markets if m.get('category') == 'Tennis']
    print(f"Polymarket Tennis Markets Found: {len(tennis_markets)}")
    for m in tennis_markets[:5]:
        print(f" - {m['question']} (ID: {m['id']})")

    bf = BetfairClient()
    await bf.login()
    events = await bf.list_events(event_type_ids=['2'])
    print(f"Betfair Tennis Events Found: {len(events)}")
    for e in events[:5]:
        print(f" - {e.get('name') or e.get('event', {}).get('name')}")

if __name__ == "__main__":
    asyncio.run(check_tennis())
