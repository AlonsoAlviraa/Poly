
import asyncio
import logging
import json
from src.data.betfair_client import BetfairClient

# Force higher level of logging to see everything
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("PriceDebug")

async def test_price_raw():
    bf = BetfairClient()
    if not await bf.login():
        print("Login failed")
        return
    
    # One of the failing market IDs from user report
    market_id = "1.253503480" 
    
    print(f"\n>>> TESTING listMarketBook for Market: {market_id}")
    
    # Try with original parameters
    payload = {
        'marketIds': [market_id],
        'priceProjection': {
            'priceData': ['EX_BEST_OFFERS'],
            'exBestOffersOverrides': {
                'bestPricesDepth': 3,
                'rollupLimit': 3
            },
            'virtualise': True
        }
    }
    
    try:
        res = await bf._api_request('listMarketBook', payload)
        print(f"Result with original params: {res}")
    except Exception as e:
        print(f"FAILED with original params: {e}")
        import traceback
        traceback.print_exc()

    print("\n>>> TESTING listMarketBook with MINIMAL params")
    payload_min = {
        'marketIds': [market_id],
        'priceProjection': {
            'priceData': ['EX_BEST_OFFERS']
        }
    }
    try:
        res_min = await bf._api_request('listMarketBook', payload_min)
        print(f"Result with minimal params: {res_min}")
    except Exception as e:
        print(f"FAILED with minimal params: {e}")

if __name__ == "__main__":
    asyncio.run(test_price_raw())
