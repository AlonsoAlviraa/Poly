import asyncio
import time
import logging
from typing import List, Dict, Any, Optional

from src.execution.vwap_engine import VWAPEngine
from src.execution.rpc_racer import RPCRacer
from src.execution.gas_estimator import GasEstimator
from src.execution.recovery_handler import RecoveryHandler

logger = logging.getLogger(__name__)

class SmartRouter:
    """
    Orchestrates execution of complex arbitrage strategies.
    Supports CLOB (API) and On-Chain (RPC Racing) legs.
    Enforces Strict Gating: Net Profit > $0.05.
    Implements FSM for 'Anti-Fragile' execution (Recovery on partials).
    """
    
    def __init__(self, executor_client: Any, rpc_urls: List[str] = [], metrics_server: Any = None, min_profit: float = 0.05):
        """
        Args:
            executor_client: Client for CLOB orders.
            rpc_urls: List of Polygon RPC endpoints for On-Chain racing.
            metrics_server: Instance of MetricsServer for observability.
        """
        self.executor = executor_client
        self.min_net_profit = min_profit
        self.metrics = metrics_server
        
        # execution subsystems
        self.rpc_racer = RPCRacer(rpc_urls) if rpc_urls else None
        self.gas_estimator = GasEstimator()
        self.recovery = RecoveryHandler(executor_client)
        
    async def _place_order_task(self, leg: Dict):
        """
        Executes a single leg (CLOB or ON_CHAIN).
        Returns: Order ID (str) if success, None if failed.
        """
        leg_type = leg.get('type', 'CLOB') # Default to CLOB
        
        try:
            if leg_type == 'CLOB':
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    None, 
                    self.executor.place_order, 
                    leg['token_id'], 
                    leg['side'], 
                    leg['limit_price'], 
                    leg['size']
                )
            elif leg_type == 'ON_CHAIN':
                # Assume leg['raw_tx_hex'] provided
                raw_tx = leg.get('raw_tx_hex')
                if self.rpc_racer and raw_tx:
                    logger.info(f"🏎️ Racing On-Chain Tx for {leg['token_id']}...")
                    return await self.rpc_racer.broadcast_tx_racing(raw_tx)
                else:
                    return None
                    
        except Exception as e:
            logger.error(f"Leg execution failed for {leg['token_id']}: {e}")
            return None

    async def execute_strategy(self, strategy_legs: List[Dict], expected_payout: float) -> Dict:
        """
        Validates and executes a multi-leg strategy.
        Stage - Pre-flight: Gating & Gas Logic.
        Stage - Execution: Parallel Dispatch.
        Stage - Monitoring & Resolution: Recovery Handler.
        """
        total_cost_vwap = 0.0
        
        # 0. Gas Estimation (if any on-chain legs)
        has_chain_legs = any(l.get('type') == 'ON_CHAIN' for l in strategy_legs)
        chain_fees = 0.0
        
        if has_chain_legs:
            gas_params = await self.gas_estimator.get_optimal_gas()
            # Estimate fee: $0.05 per tx simplified
            chain_fees = 0.05 * sum(1 for l in strategy_legs if l.get('type')=='ON_CHAIN')
            logger.debug(f"Estimated Chain Fees: ${chain_fees}")

        # 1. VWAP Validation & Pre-flight Gating
        for leg in strategy_legs:
            side = leg['side'].upper()
            book = leg.get('order_book')
            size = leg['size']
            
            vwap_price = 0.0
            if not book:
                if leg.get('type') == 'ON_CHAIN' and side == 'MINT':
                    vwap_price = 1.0 
                else:
                    vwap_price = leg['limit_price']
            else:
                if side == 'BUY':
                    vwap_price = VWAPEngine.calculate_buy_vwap(book['asks'], size)
                else:
                    vwap_price = VWAPEngine.calculate_sell_vwap(book['bids'], size)
                    
            if vwap_price is None:
                return {"success": False, "reason": f"Insufficient liquidity for leg {leg['token_id']}"}
                
            if side == 'BUY' or (leg.get('type')=='ON_CHAIN' and side=='MINT'):
                total_cost_vwap += (vwap_price * size)
            else:
                total_cost_vwap -= (vwap_price * size)

        # Net Profit Check
        clob_fees = 0.0 
        net_profit = expected_payout - total_cost_vwap - chain_fees - clob_fees
        
        if net_profit < self.min_net_profit:
             logger.info(f"Gating: Profit ${net_profit:.4f} < ${self.min_net_profit}. Aborted.")
             return {
                 "success": False, 
                 "reason": f"Profit Gating Failed. Net: ${net_profit:.3f} < ${self.min_net_profit}"
             }
             
        # 2. Parallel Execution (The "Hands")
        logger.info(f"⚡ Executing Strategy. Net Projected: ${net_profit:.3f}")
        start_time = time.time()
        
        tasks = [self._place_order_task(leg) for leg in strategy_legs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        duration = time.time() - start_time
        
        # 3. Detection (Result Analysis)
        successful_legs = []
        failed_legs = []
        
        for i, res in enumerate(results):
            leg = strategy_legs[i]
            if isinstance(res, Exception) or res is None:
                logger.error(f"❌ Leg {i} ({leg['token_id']}) FAILED.")
                failed_legs.append(leg)
            else:
                logger.info(f"✅ Leg {i} ({leg['token_id']}) FILLED. ID: {res}")
                # Attach Order ID to leg for tracking
                leg['order_id'] = res 
                successful_legs.append(leg)
                
        # 4. Resolution (FSM Logic)
        if len(failed_legs) == 0:
            return {
                "success": True,
                "net_profit_projected": net_profit,
                "latency": duration,
                "reason": "Full Execution",
                "order_ids": [l.get('order_id') for l in strategy_legs]
            }
        elif len(successful_legs) == 0:
            return {
                "success": False,
                "reason": "All Legs Failed"
            }
        else:
            # PARTIAL EXECUTION -> RECOVERY
            logger.warning(f"⚠️ PARTIAL FILL. Success: {len(successful_legs)}, Failed: {len(failed_legs)}. Triggering RecoveryHandler.")
            
            if self.metrics:
                self.metrics.recovery_counter.inc()
                
            # Fire and forget recovery? Or await?
            await self.recovery.handle_partial_failure(successful_legs, failed_legs)
            
            return {
                "success": False,
                "reason": "Partial Execution - Recovery Triggered",
                "recovery_active": True
            }
