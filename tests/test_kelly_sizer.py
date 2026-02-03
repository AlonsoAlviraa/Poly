from src.execution.smart_router import SmartRouter


class DummyExecutor:
    def place_order(self, token_id, side, limit_price, size):
        return {"order_id": "dummy", "status": "filled", "executed_price": limit_price}


def test_kelly_max_exposure_cap():
    router = SmartRouter(executor_client=DummyExecutor(), max_exposure_pct=0.05, kelly_fraction=1.0)
    bankroll = 1000.0
    size = router.calculate_kelly_size(
        bankroll=bankroll,
        edge_pct=50.0,
        win_prob=0.99,
        liquidity_limit=10000,
        max_exposure_pct=0.05,
        min_bet=1.0
    )
    assert size <= bankroll * 0.05


def test_kelly_negative_edge_zero_size():
    router = SmartRouter(executor_client=DummyExecutor())
    size = router.calculate_kelly_size(
        bankroll=1000.0,
        edge_pct=-1.0,
        win_prob=0.5,
        liquidity_limit=10000,
        min_bet=1.0
    )
    assert size == 0.0


def test_kelly_min_bet_blocks_small_bankroll():
    router = SmartRouter(executor_client=DummyExecutor())
    size = router.calculate_kelly_size(
        bankroll=10.0,
        edge_pct=5.0,
        win_prob=0.6,
        liquidity_limit=100,
        min_bet=5.0
    )
    assert size == 0.0


def test_kelly_sanity_batch():
    router = SmartRouter(executor_client=DummyExecutor())
    for i in range(100):
        size = router.calculate_kelly_size(
            bankroll=1000.0,
            edge_pct=i * 0.1,
            win_prob=0.55,
            liquidity_limit=10000,
            min_bet=1.0
        )
        assert size <= 1000.0 * router.max_exposure_pct
