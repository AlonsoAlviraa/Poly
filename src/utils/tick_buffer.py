from collections import deque
from typing import Deque, Any


class TickBuffer:
    """
    Bounded tick buffer to prevent unbounded memory growth.
    """

    def __init__(self, maxlen: int = 1000):
        self.maxlen = maxlen
        self._buffer: Deque[Any] = deque(maxlen=maxlen)
        self.dropped = 0

    def push(self, tick: Any) -> None:
        if len(self._buffer) >= self.maxlen:
            self.dropped += 1
        self._buffer.append(tick)

    def __len__(self) -> int:
        return len(self._buffer)
