import pytest
import asyncio
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import MagicMock, AsyncMock
from src.execution.smart_router import SmartRouter
from src.execution.gas_estimator import GasEstimator
from src.execution.rpc_racer import RPCRacer

@pytest.mark.asyncio
async def test_smart_router_gating():
    # Mock Executor
    executor = MagicMock()
    executor.place_order = MagicMock(return_value="oid_123")
    
    router = SmartRouter(executor, rpc_urls=[])
    
    # Strategy that loses money (Cost > Payout)
    # Leg cost: 10 * 0.5 = 5.0
    # Payout: 1.0?? No, Payout is Total Payout.
    # If strategy is "Buy YES for 0.5", expected payout on win is 1.0 per share * 10 = 10.0.
    # Total Cost = 5.0. Profit = 5.0. This passes.
    
    # Let's mock a losing trade.
    # Cost: 10 * 0.99 = 9.90. Fees = 0.01. Net = 10.0 - 9.9 - 0.01 = 0.09. Passes 0.05.
    
    # Very losing trade:
    # Cost 10 * 1.1 (Arb gone wrong). Cost 11.0. Net = 10 - 11 = -1.0. Fails.
    
    legs = [{
        "token_id": "t1",
        "side": "BUY",
        "size": 10.0,
        "limit_price": 1.10,
        "type": "CLOB"
        # order_book missing -> falls back to limit_price
    }]
    
    res = await router.execute_strategy(legs, expected_payout=10.0)
    assert res['success'] == False
    assert "Profit Gating Failed" in res['reason']

@pytest.mark.asyncio
async def test_smart_router_racing_mock():
    executor = MagicMock()
    router = SmartRouter(executor, rpc_urls=["http://mock-rpc"])
    
    # Mock Racer and Gas
    router.rpc_racer = AsyncMock(spec=RPCRacer)
    router.rpc_racer.broadcast_tx_racing.return_value = "0xhash"
    
    router.gas_estimator = AsyncMock(spec=GasEstimator)
    router.gas_estimator.get_optimal_gas.return_value = {"maxFeePerGas": 100, "maxPriorityFeePerGas": 10}
    
    # On-Chain Leg
    legs = [{
        "token_id": "t_mint",
        "type": "ON_CHAIN",
        "side": "MINT",
        "size": 10.0,
        "raw_tx_hex": "0x123456"
    }]
    
    # Expected payout for minting 10 sets is usually 10 USDC cost -> 10 YES + 10 NO.
    # If we Arb, we Sell YES and NO.
    # Here we just test execution flow.
    # Payout is irrelevant for execution success if Profit passes.
    # Cost for MINT is fixed 1.0 per set -> 10.0 cost.
    # Payout = 10.2 (Arbitrage). Net = 0.2 - fees.
    
    res = await router.execute_strategy(legs, expected_payout=10.20)
    
    assert res['success'] == True
    assert res['order_ids'][0] == "0xhash"
    # Check gas called
    router.gas_estimator.get_optimal_gas.assert_called_once()
    # Check racing called
    router.rpc_racer.broadcast_tx_racing.assert_called_with("0x123456")
