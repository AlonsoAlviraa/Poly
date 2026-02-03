from dataclasses import dataclass
from typing import Dict
import time


@dataclass
class FeedStatus:
    last_seen: float


class FeedHealthMonitor:
    """
    Tracks multiple feeds and flags stale data for pause decisions.
    """

    def __init__(self, max_stale_s: float = 5.0):
        self.max_stale_s = max_stale_s
        self._feeds: Dict[str, FeedStatus] = {}

    def update_feed(self, name: str) -> None:
        self._feeds[name] = FeedStatus(last_seen=time.monotonic())

    def is_healthy(self) -> bool:
        now = time.monotonic()
        if not self._feeds:
            return False
        return all(now - status.last_seen <= self.max_stale_s for status in self._feeds.values())
