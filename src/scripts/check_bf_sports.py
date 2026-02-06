import asyncio
import json
import logging
from src.data.betfair_client import BetfairClient

logging.basicConfig(level=logging.INFO)

async def check_sports():
    client = BetfairClient()
    if not await client.login():
        print("Login failed")
        return

    print("\n>> CHECKING SOCCER (1) MARKETS...")
    from datetime import datetime
    soccer_payload = {
        "filter": {
            "eventTypeIds": ["1"],
            "marketTypeCodes": ["MATCH_ODDS"],
            "marketStartTime": {"from": datetime.utcnow().isoformat() + "Z"}
        },
        "maxResults": 100,
        "marketProjection": ["EVENT", "MARKET_DESCRIPTION"]
    }
    markets = await client._api_request('listMarketCatalogue', soccer_payload)
    if markets:
        print(f"Found {len(markets)} Soccer markets.")
    else:
        print("No Soccer markets found with Match Odds + Time filter.")

    print("\n>> CHECKING BASKETBALL (7522) MARKETS...")
    basket_payload = {
        "filter": {"eventTypeIds": ["7522"]},
        "maxResults": 1000,
        "marketProjection": ["EVENT", "MARKET_DESCRIPTION"]
    }
    markets = await client._api_request('listMarketCatalogue', basket_payload)
    if markets:
        print(f"Found {len(markets)} Basketball markets.")
        # Check first 5 market types
        types = set(m.get('description', {}).get('marketType') for m in markets)
        print(f"Market Types found: {list(types)[:10]}")
    else:
        print("No Basketball markets found with default filter.")

    print("\n>> CHECKING TENNIS (2) MARKETS...")
    tennis_payload = {
        "filter": {"eventTypeIds": ["2"]},
        "maxResults": 1000
    }
    markets = await client._api_request('listMarketCatalogue', tennis_payload)
    if markets:
        print(f"Found {len(markets)} Tennis markets.")
    else:
        print("No Tennis markets found.")

if __name__ == "__main__":
    asyncio.run(check_sports())
