
import asyncio
from src.data.betfair_client import BetfairClient

async def list_bf_types():
    bf = BetfairClient()
    if await bf.login():
        types = await bf.list_event_types()
        if types:
            print("Available Event Types:")
            for item in types:
                print(f" - {item.get('name')} (ID: {item.get('id')}) | Markets: {item.get('market_count')}")
        else:
            print("Failed to fetch event types.")

if __name__ == "__main__":
    asyncio.run(list_bf_types())
