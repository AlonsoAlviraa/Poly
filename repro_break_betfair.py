
import asyncio
import os
import json
import logging
from src.data.betfair_client import BetfairClient
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Fuzz")

async def fuzz():
    load_dotenv()
    bf = BetfairClient(use_delay=True)
    await bf.login()
    
    # Test 1: Integers in list
    logger.info("Test 1: Integers in list")
    try:
        # Client expects List[str], but let's force passing raw dict to _api_request if we could
        # But we can only call list_events which types checks... wait, python doesn't enforce types at runtime
        await bf.list_events(event_type_ids=[1, 2])
        logger.info("Test 1: OK")
    except Exception as e:
        logger.error(f"Test 1 Failed: {e}")

    # Test 2: Invalid Key in Filter (requires monkeypatching or direct calling)
    logger.info("Test 2: Direct invalid payload")
    try:
        await bf._api_request('listEvents', {'filter': {'invalidKey': '123'}})
    except Exception as e:
         logger.error(f"Test 2 Failed: {e}")

    # Test 3: None in list
    logger.info("Test 3: None in list")
    try:
        await bf.list_events(event_type_ids=['1', None])
    except Exception as e:
        logger.error(f"Test 3 Failed: {e}")
        
    # Test 4: Mixed types
    logger.info("Test 4: Mixed Int/Str")
    try:
        await bf.list_events(event_type_ids=['1', 7522])
    except Exception as e:
        logger.error(f"Test 4 Failed: {e}")

if __name__ == "__main__":
    asyncio.run(fuzz())
