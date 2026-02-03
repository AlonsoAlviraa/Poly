import asyncio
import logging
import random
import uuid
from typing import Dict, List, Tuple, Optional

from src.execution.vwap_engine import VWAPEngine

logger = logging.getLogger(__name__)


class PaperExecutionEngine:
    """
    High-fidelity paper trading engine.
    Simulates order book consumption, latency, and partial fills.
    """

    def __init__(self, min_latency_s: float = 0.2, max_latency_s: float = 0.8):
        self.min_latency_s = min_latency_s
        self.max_latency_s = max_latency_s

    async def execute_leg(self, leg: Dict) -> Dict:
        await asyncio.sleep(random.uniform(self.min_latency_s, self.max_latency_s))

        order_book = leg.get("order_book")
        size = leg.get("size", 0.0)
        side = leg.get("side", "BUY").upper()
        limit_price = leg.get("limit_price")

        if not order_book or not size:
            return {
                "order_id": f"paper-{uuid.uuid4()}",
                "status": "filled",
                "executed_price": limit_price,
                "filled_size": size,
                "remaining_size": 0.0
            }

        price, filled, remaining = self._consume_order_book(order_book, size, side)
        status = "filled" if remaining <= 0 else "partial"

        return {
            "order_id": f"paper-{uuid.uuid4()}",
            "status": status,
            "executed_price": price,
            "filled_size": filled,
            "remaining_size": remaining
        }

    def _normalize_levels(self, levels: List) -> List[Tuple[float, float]]:
        normalized = []
        for level in levels:
            if isinstance(level, dict):
                price = float(level.get("price", 0))
                size = float(level.get("size", 0))
            else:
                price, size = level
            normalized.append((price, size))
        return normalized

    def _consume_order_book(self, book: Dict, size: float, side: str) -> Tuple[Optional[float], float, float]:
        if side == "BUY":
            levels = self._normalize_levels(book.get("asks", []))
        else:
            levels = self._normalize_levels(book.get("bids", []))

        remaining = size
        consumed = []
        for price, available in levels:
            if remaining <= 0:
                break
            take = min(available, remaining)
            consumed.append((price, take))
            remaining -= take

        if not consumed:
            return None, 0.0, size

        vwap_price = VWAPEngine.calculate_buy_vwap(consumed, size) if side == "BUY" else VWAPEngine.calculate_sell_vwap(consumed, size)
        filled = size - remaining
        return vwap_price, filled, remaining
