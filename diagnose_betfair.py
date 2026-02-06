
import asyncio
import os
import json
import logging
from src.data.betfair_client import BetfairClient
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("BF_Diag")

async def diagnose():
    load_dotenv()
    bf = BetfairClient(use_delay=True)
    
    logger.info("1. Attempting Login...")
    if not await bf.login():
        logger.error("Login failed!")
        return

    logger.info("2. Testing listEventTypes (No filter)...")
    types = await bf.list_event_types()
    if types:
        logger.info(f"Success! Found {len(types)} event types.")
        example_ids = [t['id'] for t in types[:5]]
        logger.info(f"Examples: {example_ids}")
    else:
        logger.error("listEventTypes failed!")

    logger.info("3. Testing listEvents (Empty filter)...")
    try:
        # Override _api_request temporarily to allow Empty filter test if list_events prohibits it
        # Actually client.list_events() sends {} filter if no args.
        evs = await bf.list_events()
        logger.info(f"Success! Found {len(evs)} events (Empty filter).")
    except Exception as e:
        logger.error(f"Failed (Empty filter): {e}")

    logger.info("4. Testing listEvents (Soccer Only - '1')...")
    try:
        evs = await bf.list_events(event_type_ids=['1'])
        logger.info(f"Success! Found {len(evs)} events (Soccer).")
    except Exception as e:
        logger.error(f"Failed (Soccer): {e}")

    logger.info("5. Testing listEvents (Politics Only - '2378961')...")
    try:
        evs = await bf.list_events(event_type_ids=['2378961'])
        logger.info(f"Success! Found {len(evs)} events (Politics).")
    except Exception as e:
        logger.error(f"Failed (Politics): {e}")

    logger.info("6. Testing listEvents (Full Poly List)...")
    # This matches observer_mode.py
    ids = ['1', '2', '7511', '7522', '2378961', '10']
    try:
        evs = await bf.list_events(event_type_ids=ids)
        logger.info(f"Success! Found {len(evs)} events (Full List).")
    except Exception as e:
        logger.error(f"Failed (Full List): {e}")

if __name__ == "__main__":
    asyncio.run(diagnose())
