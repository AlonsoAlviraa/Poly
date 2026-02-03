import asyncio
import logging
import random
import uuid
import json
import os
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Tuple, Optional

from src.execution.vwap_engine import VWAPEngine

logger = logging.getLogger(__name__)


class PaperExecutionEngine:
    """
    High-fidelity paper trading engine.
    Simulates order book consumption, latency, and partial fills.
    """

    def __init__(self, min_latency_s: float = 0.2, max_latency_s: float = 0.8, state_file: str = "paper_state.json"):
        self.min_latency_s = min_latency_s
        self.max_latency_s = max_latency_s
        self.state_file = state_file
        self._state = self._load_state()

    async def execute_leg(self, leg: Dict) -> Dict:
        await asyncio.sleep(random.uniform(self.min_latency_s, self.max_latency_s))

        order_book = leg.get("order_book")
        size = leg.get("size", 0.0)
        side = leg.get("side", "BUY").upper()
        limit_price = leg.get("limit_price")

        if not order_book or not size:
            result = {
                "order_id": f"paper-{uuid.uuid4()}",
                "status": "filled",
                "executed_price": limit_price,
                "filled_size": size,
                "remaining_size": 0.0
            }
            self._record_result(result)
            return result

        price, filled, remaining = self._consume_order_book(order_book, size, side)
        status = "filled" if remaining <= 0 else "partial"

        result = {
            "order_id": f"paper-{uuid.uuid4()}",
            "status": status,
            "executed_price": price,
            "filled_size": filled,
            "remaining_size": remaining
        }
        self._record_result(result)
        return result

    def _normalize_levels(self, levels: List) -> List[Tuple[Decimal, Decimal]]:
        normalized = []
        for level in levels:
            if isinstance(level, dict):
                price = Decimal(str(level.get("price", 0)))
                size = Decimal(str(level.get("size", 0)))
            else:
                price, size = level
                price = Decimal(str(price))
                size = Decimal(str(size))
            normalized.append((price, size))
        return normalized

    def _consume_order_book(self, book: Dict, size: float, side: str) -> Tuple[Optional[float], float, float]:
        if side == "BUY":
            levels = self._normalize_levels(book.get("asks", []))
        else:
            levels = self._normalize_levels(book.get("bids", []))

        try:
            remaining = Decimal(str(size))
            total_size = Decimal(str(size))
        except (InvalidOperation, ValueError):
            return None, 0.0, size
        consumed = []
        for price, available in levels:
            if remaining <= 0:
                break
            take = min(available, remaining)
            consumed.append((price, take))
            remaining -= take

        if not consumed:
            return None, 0.0, size

        vwap_price = self._calculate_vwap(consumed, total_size)
        filled = total_size - remaining
        return float(vwap_price), float(filled), float(remaining)

    def _calculate_vwap(self, levels: List[Tuple[Decimal, Decimal]], total_size: Decimal) -> Decimal:
        if total_size <= 0:
            return Decimal("0")
        total_cost = Decimal("0")
        for price, size in levels:
            total_cost += price * size
        return total_cost / total_size

    def _load_state(self) -> Dict:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as handle:
                    return json.load(handle)
            except (json.JSONDecodeError, OSError):
                pass
        return {"orders": []}

    def _record_result(self, result: Dict) -> None:
        self._state.setdefault("orders", []).append(result)
        self._state["orders"] = self._state["orders"][-1000:]
        try:
            with open(self.state_file, "w", encoding="utf-8") as handle:
                json.dump(self._state, handle)
        except OSError:
            logger.warning("Failed to persist paper trading state.")
