
import asyncio
import logging
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from src.execution.order_manager import OrderManager
from src.arbitrage.models import MarketMapping, ArbOpportunity

# Configure logging to see structured output
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger("IntegrationTest")

class MockPolyExecutor:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
    
    def place_fok_order(self, token_id, side, price, size):
        if self.should_fail:
            return type('obj', (object,), {'success': False, 'error': 'API Timeout', 'filled_size': 0})
        return type('obj', (object,), {'success': True, 'filled_size': size, 'avg_price': price, 'order_id': f"POLY_{token_id}"})

    def place_order(self, token_id, side, price, size):
        return self.place_fok_order(token_id, side, price, size)

    def get_order_book(self, token_id):
        return {'asks': [{'price': 0.5, 'size': 1000}]}

class MockHedgeExecutor:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
    
    async def place_order(self, market_id, side, price, size):
        if self.should_fail:
            return type('obj', (object,), {'success': False, 'error': 'Exchange Rejected', 'filled_size': 0})
        return type('obj', (object,), {'success': True, 'filled_size': size, 'avg_price': price, 'order_id': f"HEDGE_{market_id}", 'market_id': market_id})

async def run_test():
    print("\n" + "="*60)
    print("🚀 APU INTEGRATION SMOKE TEST (DRY-RUN)")
    print("="*60)

    # 1. Setup Mock Opportunity
    mapping = MarketMapping(
        polymarket_id="0xTEST_POLY",
        polymarket_question="Will Test Team A win?",
        betfair_event_id="BF_123",
        betfair_market_id="BF_M_456",
        betfair_event_name="Test Team A vs B",
        confidence=1.0,
        mapped_at=datetime.now(),
        source="test"
    )
    
    opp = ArbOpportunity(
        mapping=mapping,
        poly_yes_price=0.5,
        poly_no_price=0.5,
        betfair_back_odds=2.1,
        betfair_lay_odds=2.0,
        ev_net=5.0,
        is_profitable=True,
        direction="buy_poly_lay_bf",
        detected_at=datetime.now()
    )

    # CASE 1: SUCCESS IN BOTH LEGS
    print("\n[CASE 1] SUCCESSFUL ATOMIC EXECUTION")
    poly_ok = MockPolyExecutor(should_fail=False)
    hedge_ok = MockHedgeExecutor(should_fail=False)
    om_success = OrderManager(poly_ok, hedge_ok, dry_run=False) # We use Mocks anyway
    await om_success.execute_arbitrage(opp)

    # CASE 2: LEGGING RISK (HEDGE FAILS)
    print("\n[CASE 2] LEGGING RISK -> PANIC HEDGE (Hedge Fails)")
    poly_ok = MockPolyExecutor(should_fail=False)
    hedge_fail = MockHedgeExecutor(should_fail=True)
    om_panic = OrderManager(poly_ok, hedge_fail, dry_run=False)
    await om_panic.execute_arbitrage(opp)

    # CASE 3: CIRCUIT BREAKER TEST (3 FAILURES)
    print("\n[CASE 3] CIRCUIT BREAKER TRIGGER")
    poly_fail = MockPolyExecutor(should_fail=True)
    om_breaker = OrderManager(poly_fail, hedge_ok, dry_run=False)
    print("... Triggering 3 failures ...")
    for _ in range(3):
        await om_breaker.execute_arbitrage(opp)
    
    print("... Attempting 4th execution (Should be blocked) ...")
    await om_breaker.execute_arbitrage(opp)

    print("\n" + "="*60)
    print("✨ INTEGRATION TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_test())
