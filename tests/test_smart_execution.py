import pytest
import asyncio
from unittest.mock import MagicMock
from src.strategies.market_maker import SimpleMarketMaker

@pytest.mark.asyncio
async def test_smart_execution_skips_redundant_updates():
    # Setup
    executor = MagicMock()
    # Mock place_order to return an ID
    executor.place_order.return_value = "oid_123"
    
    maker = SimpleMarketMaker(
        token_ids=["T1"], 
        executor=executor, 
        dry_run=False
    )
    
    # 1. First Call: Should Place
    await maker.execute_quotes("T1", 0.50, 0.60, size=10.0)
    assert executor.place_order.call_count == 2 # Bid + Ask
    executor.place_order.reset_mock()
    executor.cancel_order.reset_mock()
    
    # 2. Second Call (Same params): Should Skip
    await maker.execute_quotes("T1", 0.50, 0.60, size=10.0)
    assert executor.place_order.call_count == 0
    assert executor.cancel_order.call_count == 0
    
    # 3. Third Call (Different Price): Should Update
    await maker.execute_quotes("T1", 0.51, 0.61, size=10.0)
    assert executor.cancel_order.call_count == 2
    assert executor.place_order.call_count == 2
    
    print("[PASS] Smart Execution Test Passed")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(test_smart_execution_skips_redundant_updates())
