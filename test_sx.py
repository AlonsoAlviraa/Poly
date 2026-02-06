
import asyncio
from src.data.sx_bet_client import SXBetClient
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SXTest")

async def test():
    client = SXBetClient()
    logger.info("Fetching SX Markets...")
    start = time.time()
    markets = await client.get_active_markets()
    logger.info(f"Fetched {len(markets)} markets in {time.time()-start:.2f}s")
    await client.close()

if __name__ == "__main__":
    asyncio.run(test())
