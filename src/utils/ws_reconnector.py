
import asyncio
import logging

logger = logging.getLogger(__name__)

class WSReconnector:
    """
    Handles WebSocket reconnection logic with exponential backoff.
    """
    def __init__(self, connect_func, max_retries=5):
        self.connect_func = connect_func
        self.max_retries = max_retries

    async def connect_forever(self):
        retries = 0
        while True:
            try:
                await self.connect_func()
                retries = 0  # Reset on success (if it returns)
            except Exception as e:
                retries += 1
                wait = min(2 ** retries, 60)
                logger.error(f"WS Connection failed (Attempt {retries}/{self.max_retries}): {e}. Retrying in {wait}s...")
                if retries > self.max_retries:
                    logger.error("Max retries exceeded.")
                    raise e
                await asyncio.sleep(wait)
