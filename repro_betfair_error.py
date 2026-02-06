
import asyncio
import os
import json
import logging
from src.data.betfair_client import BetfairClient
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Repro")

async def repro():
    load_dotenv()
    bf = BetfairClient(use_delay=True)
    await bf.login()
    
    # Payload causing the error
    event_type_ids = ['1', '2', '7511', '7522', '2378961', '10']
    
    logger.info(f"Testing list_events with: {event_type_ids}")
    
    try:
        events = await bf.list_events(event_type_ids=event_type_ids)
        logger.info(f"Success! Found {len(events)} events.")
    except Exception as e:
        logger.error(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(repro())
