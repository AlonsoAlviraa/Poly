import pytest
from src.strategies.market_maker import SimpleMarketMaker

def test_whale_action_updates_pressure():
    maker = SimpleMarketMaker(token_ids=["T1"])
    
    # Initial state
    assert maker.social_signals["T1"]["whale_pressure"] == 0.0
    
    # record BUY (Whale buys)
    maker.record_whale_action("T1", "BUY", size=100.0, confidence=0.8)
    
    # Check pressure
    pressure = maker.social_signals["T1"]["whale_pressure"]
    assert pressure > 0 # Should be positive (Bullish)
    print(f"Whale Pressure (BUY): {pressure}")
    
    # record SELL (Whale sells massive)
    maker.record_whale_action("T1", "SELL", size=500.0, confidence=1.0)
    
    # Check pressure - should tank or average down
    pressure_new = maker.social_signals["T1"]["whale_pressure"]
    print(f"Whale Pressure (SELL): {pressure_new}")
    
    # Since we append to a list `whale_heat`, the earlier BUY is still there.
    # The pressure is an average.
    assert pressure_new < pressure # Should decrease
    
    print("[PASS] Whale Integration Verified")

if __name__ == "__main__":
    test_whale_action_updates_pressure()
