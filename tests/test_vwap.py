import pytest
import sys
import os

# Add root to path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.execution.vwap_engine import VWAPEngine

class TestVWAPEngine:
    def test_buy_vwap_simple(self):
        # Asks: 100 @ 0.50, 100 @ 0.60
        # Buy 150 -> 100*0.5 + 50*0.6 = 80. Raw VWAP = 80/150 = 0.5333
        # With 0.5% slippage: 0.5333 * 1.005 = 0.536
        asks = [[0.50, 100], [0.60, 100]]
        vwap = VWAPEngine.calculate_buy_vwap(asks, 150)
        assert vwap is not None
        raw_vwap = 0.533333333
        expected = raw_vwap * (1.0 + VWAPEngine.SLIPPAGE_PENALTY)
        assert abs(vwap - expected) < 1e-5

    def test_buy_insufficient_liquidity(self):
        asks = [[0.50, 100]]
        vwap = VWAPEngine.calculate_buy_vwap(asks, 150)
        assert vwap is None

    def test_sell_vwap_simple(self):
        # Bids: 100 @ 0.50, 100 @ 0.40
        # Sell 150 -> 100*0.5 + 50*0.4 = 70. Raw VWAP = 70/150 = 0.4667
        # With 0.5% slippage: 0.4667 * 0.995 = 0.4643
        bids = [[0.50, 100], [0.40, 100]]
        vwap = VWAPEngine.calculate_sell_vwap(bids, 150)
        assert vwap is not None
        raw_vwap = 0.466666666
        expected = raw_vwap * (1.0 - VWAPEngine.SLIPPAGE_PENALTY)
        assert abs(vwap - expected) < 1e-5
