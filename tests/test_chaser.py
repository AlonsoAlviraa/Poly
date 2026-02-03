import asyncio
import pytest

from src.execution.smart_router import SmartRouter


class DummyExecutor:
    def place_order(self, token_id, side, limit_price, size):
        return {"order_id": "dummy", "status": "filled", "executed_price": limit_price}

    def cancel_order(self, order_id):
        return True


class DummyRouter(SmartRouter):
    def __init__(self, results):
        super().__init__(executor_client=DummyExecutor())
        self._results = list(results)
        self.chase_calls = 0

    async def _place_order_task(self, leg):
        result = self._results.pop(0)
        if callable(result):
            return await result()
        return result

    async def _chase_partial_fill(self, leg, result):
        self.chase_calls += 1
        return await super()._chase_partial_fill(leg, result)


@pytest.mark.asyncio
async def test_chaser_happy_path_filled():
    router = DummyRouter([
        {"order_id": "poly", "status": "filled", "executed_price": 1.0},
        {"order_id": "bf", "status": "filled", "executed_price": 2.0}
    ])
    legs = [
        {"token_id": "poly", "side": "BUY", "limit_price": 0.5, "size": 100},
        {"token_id": "bf", "side": "BACK", "limit_price": 2.0, "size": 100}
    ]
    result = await router.execute_atomic_strategy(legs, expected_payout=110)
    assert result["success"] is True
    assert router.chase_calls == 0


@pytest.mark.asyncio
async def test_chaser_partial_fill_then_chase_success():
    router = DummyRouter([
        {"order_id": "poly", "status": "filled", "executed_price": 1.0},
        {"order_id": "bf", "status": "partial", "executed_price": 2.0, "filled_size": 20, "remaining_size": 80},
        {"order_id": "bf-chase", "status": "filled", "executed_price": 1.95, "filled_size": 80, "remaining_size": 0}
    ])
    legs = [
        {"token_id": "poly", "side": "BUY", "limit_price": 0.5, "size": 100},
        {
            "token_id": "bf",
            "side": "BACK",
            "limit_price": 2.0,
            "size": 100,
            "allow_chase": True,
            "breakeven_price": 1.9,
            "chase_step_pct": 1.0,
            "max_chase_attempts": 2
        }
    ]
    result = await router.execute_atomic_strategy(legs, expected_payout=110)
    assert result["success"] is True
    assert router.chase_calls == 1


@pytest.mark.asyncio
async def test_chaser_partial_fill_cancel_on_negative_spread():
    router = DummyRouter([
        {"order_id": "poly", "status": "filled", "executed_price": 1.0},
        {"order_id": "bf", "status": "partial", "executed_price": 2.0, "filled_size": 20, "remaining_size": 80}
    ])
    legs = [
        {"token_id": "poly", "side": "BUY", "limit_price": 0.5, "size": 100},
        {
            "token_id": "bf",
            "side": "BACK",
            "limit_price": 2.0,
            "size": 100,
            "allow_chase": True,
            "breakeven_price": 2.1,
            "chase_step_pct": 1.0,
            "max_chase_attempts": 2
        }
    ]
    result = await router.execute_atomic_strategy(legs, expected_payout=110)
    assert result["success"] is False
    assert router.chase_calls == 1


@pytest.mark.asyncio
async def test_chaser_timeout_triggers_failure():
    async def slow_result():
        await asyncio.sleep(0.2)
        return {"order_id": "slow", "status": "filled", "executed_price": 2.0}

    router = DummyRouter([slow_result])
    legs = [
        {"token_id": "bf", "side": "BACK", "limit_price": 2.0, "size": 100, "timeout_s": 0.05}
    ]
    result = await router.execute_atomic_strategy(legs, expected_payout=110)
    assert result["success"] is False
