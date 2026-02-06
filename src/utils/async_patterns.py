
import asyncio
import random
import logging

logger = logging.getLogger(__name__)

class RobustConnection:
    """
    Standardizes connection lifecycle with exponential backoff and jitter.
    """
    def __init__(self, name: str, base_delay: float = 1.0, max_delay: float = 60.0):
        self.name = name
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.retries = 0

    async def sleep(self):
        # Exponential backoff + Jitter (Full Jitter)
        delay = min(self.max_delay, self.base_delay * (2 ** self.retries))
        jitter = random.uniform(0, delay)
        logger.warning(f"[{self.name}] Retrying in {jitter:.2f}s... (Attempt {self.retries + 1})")
        await asyncio.sleep(jitter)
        self.retries += 1

    def reset(self):
        if self.retries > 0:
            logger.info(f"[{self.name}] Connection established. Resetting backoff.")
        self.retries = 0

class AsyncQueueProcessor:
    """
    Generic Processor for Decoupled Producer/Consumer logic.
    """
    def __init__(self, worker_func, num_workers: int = 4):
        self.queue = asyncio.Queue()
        self.worker_func = worker_func
        self.num_workers = num_workers
        self.tasks = []

    async def start(self):
        self.tasks = [asyncio.create_task(self._worker(i)) for i in range(self.num_workers)]
        logger.info(f"Started {self.num_workers} workers for queue processing.")

    async def stop(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def _worker(self, i):
        while True:
            try:
                item = await self.queue.get()
                await self.worker_func(item)
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {i} error: {e}", exc_info=True)

    def put(self, item):
        self.queue.put_nowait(item)
