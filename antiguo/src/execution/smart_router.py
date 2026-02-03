import asyncio
import time
from typing import List, Dict, Any
from src.exchanges.polymarket_clob import PolymarketOrderExecutor
from src.execution.vwap_engine import VWAPEngine

class SmartRouter:
    """
    Orchestrates execution of complex arbitrage strategies.
    Enforces Strict Gating: Net Profit > $0.05.
    Uses Parallel Submission for atomicity-like behavior on CLOB.
    """
    
    def __init__(self, executor: PolymarketOrderExecutor):
        self.executor = executor
        self.min_net_profit = 0.05 # SRS Gating
        # Gas/Fee estimates (Polygon is cheap, but we account for it)
        self.estimated_fee_per_tx = 0.01 
        
    async def _place_order_task(self, leg: Dict):
        """
        Wrapper to run sync place_order in thread pool.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, 
            self.executor.place_order, 
            leg['token_id'], 
            leg['side'], 
            leg['limit_price'], 
            leg['size']
        )

    async def execute_strategy(self, strategy_legs: List[Dict], expected_payout: float) -> Dict:
        """
        Validates and executes a multi-leg strategy.
        
        Args:
            strategy_legs: List of dicts, each containing:
                - token_id
                - side ('BUY' or 'SELL')
                - size
                - limit_price (max pay / min receive)
                - order_book (snapshot for VWAP check)
            expected_payout: The gross value if all legs hit (e.g., $1.00 for arb).
            
        Returns:
            Dict with execution results and status.
        """
        total_cost_vwap = 0.0
        validated_legs = []
        
        # 1. VWAP Validation & Gating
        for leg in strategy_legs:
            side = leg['side'].upper()
            book = leg.get('order_book')
            size = leg['size']
            
            vwap_price = 0.0
            if not book:
                # If no book provided, assume limit price is the price (Risky, but fallback)
                vwap_price = leg['limit_price']
            else:
                if side == 'BUY':
                    vwap_price = VWAPEngine.calculate_buy_vwap(book['asks'], size)
                else:
                    vwap_price = VWAPEngine.calculate_sell_vwap(book['bids'], size)
                    
            if vwap_price is None:
                return {"success": False, "reason": f"Insufficient liquidity for leg {leg['token_id']}"}
                
            # If BUY, we pay cost. If SELL, we gain revenue (negative cost for profit calc)
            if side == 'BUY':
                total_cost_vwap += (vwap_price * size)
            else:
                # Selling something we don't own? 
                # In arb, we usually BUY YES + BUY NO.
                # If we are selling, revenue reduces cost base.
                total_cost_vwap -= (vwap_price * size)

        # Calculate Net Profit
        # Profit = Payout - Cost - Fees
        total_fees = len(strategy_legs) * self.estimated_fee_per_tx
        net_profit = expected_payout - total_cost_vwap - total_fees
        
        if net_profit < self.min_net_profit:
             return {
                 "success": False, 
                 "reason": f"Profit Gating Failed. Net: ${net_profit:.3f} < ${self.min_net_profit}"
             }
             
        # 2. Parallel Execution
        print(f"⚡ Executing Strategy. Net Projected: ${net_profit:.3f}")
        start_time = time.time()
        
        tasks = [self._place_order_task(leg) for leg in strategy_legs]
        order_ids = await asyncio.gather(*tasks, return_exceptions=True)
        
        duration = time.time() - start_time
        
        # 3. Result Compilation
        success_count = 0
        final_orders = []
        
        for i, res in enumerate(order_ids):
            if isinstance(res, Exception):
                print(f"❌ Leg {i} Failed: {res}")
                final_orders.append(None)
            elif res is None:
                print(f"❌ Leg {i} Failed (No ID)")
                final_orders.append(None)
            else:
                success_count += 1
                final_orders.append(res)
                
        execution_success = (success_count == len(strategy_legs))
        
        return {
            "success": execution_success,
            "net_profit_projected": net_profit,
            "order_ids": final_orders,
            "latency": duration,
            "reason": "Executed" if execution_success else "Partial Execution"
        }
