import pytest
from src.execution.vwap_engine import VWAPEngine

class TestVWAPEngine:
    def test_buy_vwap_simple(self):
        # Asks: 100 @ 0.50, 100 @ 0.60
        # Buy 150
        # Cost: 100*0.5 + 50*0.6 = 50 + 30 = 80
        # VWAP: 80 / 150 = 0.5333
        asks = [[0.50, 100], [0.60, 100]]
        vwap = VWAPEngine.calculate_buy_vwap(asks, 150)
        assert vwap is not None
        assert abs(vwap - 0.533333333) < 1e-5

    def test_buy_insufficient_liquidity(self):
        asks = [[0.50, 100]]
        vwap = VWAPEngine.calculate_buy_vwap(asks, 150)
        assert vwap is None

    def test_sell_vwap_simple(self):
        # Bids: 100 @ 0.50, 100 @ 0.40
        # Sell 150
        # Revenue: 100*0.5 + 50*0.4 = 50 + 20 = 70
        # VWAP: 70 / 150 = 0.4666
        bids = [[0.50, 100], [0.40, 100]]
        vwap = VWAPEngine.calculate_sell_vwap(bids, 150)
        assert vwap is not None
        assert abs(vwap - 0.466666666) < 1e-5
