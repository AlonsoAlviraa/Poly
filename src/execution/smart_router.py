import asyncio
import time
import logging
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any, Optional, Tuple

from src.execution.vwap_engine import VWAPEngine
from src.execution.rpc_racer import RPCRacer
from src.execution.gas_estimator import GasEstimator
from src.execution.recovery_handler import RecoveryHandler
from src.risk.position_sizer import KellyPositionSizer
from src.alerts.command_center import CommandCenterNotifier
from src.execution.paper_engine import PaperExecutionEngine
from src.risk.risk_guardian import RiskGuardian
from src.utils.json_decimal import loads_decimal
from src.data.entity_resolution import EntityResolver

logger = logging.getLogger(__name__)

class SmartRouter:
    """
    Orchestrates execution of complex arbitrage strategies.
    Supports CLOB (API) and On-Chain (RPC Racing) legs.
    Enforces Strict Gating: Net Profit > $0.05.
    Implements FSM for 'Anti-Fragile' execution (Recovery on partials).
    """
    
    def __init__(
        self,
        executor_client: Any,
        rpc_urls: List[str] = [],
        metrics_server: Any = None,
        min_profit: float = 0.05,
        max_exposure_pct: float = 0.05,
        kelly_fraction: float = 0.25,
        notifier: Optional[CommandCenterNotifier] = None,
        paper_mode: bool = False,
        risk_guardian: Optional[RiskGuardian] = None
    ):
        """
        Args:
            executor_client: Client for CLOB orders.
            rpc_urls: List of Polygon RPC endpoints for On-Chain racing.
            metrics_server: Instance of MetricsServer for observability.
        """
        self.executor = executor_client
        self.min_net_profit = min_profit
        self.metrics = metrics_server
        self.max_exposure_pct = max_exposure_pct
        self.kelly = KellyPositionSizer(fraction=kelly_fraction)
        self.notifier = notifier or CommandCenterNotifier()
        self.paper_mode = paper_mode
        self.paper_engine = PaperExecutionEngine() if paper_mode else None
        self.risk_guardian = risk_guardian
        self._order_lock = asyncio.Lock()
        
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
            if self.paper_mode and self.paper_engine:
                return await self.paper_engine.execute_leg(leg)
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

    def _extract_execution_price(self, result: Any) -> Optional[float]:
        if isinstance(result, dict):
            for key in ("price", "avg_price", "executed_price", "fill_price"):
                if key in result:
                    return result[key]
        return None

    @staticmethod
    def parse_ws_payload(payload: str) -> Dict[str, Any]:
        return loads_decimal(payload)

    @staticmethod
    def normalize_entity(raw_name: str, resolver: Optional[EntityResolver] = None) -> Optional[str]:
        if not raw_name:
            return None
        resolver = resolver or EntityResolver()
        return resolver.resolve(raw_name)

    async def _cancel_leg(self, leg: Dict) -> bool:
        async with self._order_lock:
            return await self._cancel_leg_unlocked(leg)

    async def _cancel_leg_unlocked(self, leg: Dict) -> bool:
        cancel_fn = getattr(self.executor, "cancel_order", None)
        if not cancel_fn:
            return False
        order_id = leg.get("order_id")
        if not order_id:
            return False
        try:
            cancel_fn(order_id)
            return True
        except Exception as exc:
            logger.error(f"Failed to cancel order {order_id}: {exc}")
            return False

    def calculate_kelly_size(
        self,
        bankroll: float,
        edge_pct: float,
        win_prob: float,
        liquidity_limit: float,
        max_exposure_pct: Optional[float] = None,
        min_bet: float = 0.0
    ) -> float:
        max_exposure = bankroll * (max_exposure_pct if max_exposure_pct is not None else self.max_exposure_pct)
        profit_ratio = max(edge_pct / 100.0, 0.0)
        size = self.kelly.calculate_size(
            capital=bankroll,
            win_prob=win_prob,
            profit_ratio=profit_ratio,
            liquidity_limit=liquidity_limit
        )
        final_size = min(size, max_exposure)
        if final_size < min_bet:
            return 0.0
        return final_size

    def _is_worse_price(self, leg: Dict, new_price: float, reference: float) -> bool:
        price_format = leg.get("price_format", "odds")
        side = leg.get("side", "BACK").upper()
        if price_format == "probability":
            return new_price > reference if side in {"BUY", "BACK"} else new_price < reference
        if side == "BACK":
            return new_price < reference
        if side == "LAY":
            return new_price > reference
        return new_price < reference

    async def _chase_partial_fill(self, leg: Dict, result: Dict) -> Tuple[bool, Optional[Dict]]:
        if not leg.get("allow_chase"):
            return False, None
        breakeven_price = leg.get("breakeven_price")
        if breakeven_price is None:
            return False, None
        remaining = result.get("remaining_size", 0.0)
        if remaining <= 0:
            return True, result

        step_pct = leg.get("chase_step_pct", 0.5)
        max_attempts = leg.get("max_chase_attempts", 3)
        expected_price = leg.get("expected_price", leg.get("limit_price"))
        price = leg.get("limit_price", expected_price)

        for _ in range(max_attempts):
            direction = -1 if self._is_worse_price(leg, breakeven_price, price) else 1
            price = price * (1 + (step_pct / 100.0) * direction)
            if self._is_worse_price(leg, price, breakeven_price):
                break
            chase_leg = {**leg, "size": remaining, "limit_price": price}
            chase_result = await self._place_order_task(chase_leg)
            if isinstance(chase_result, dict) and chase_result.get("status") == "filled":
                return True, chase_result
            if isinstance(chase_result, dict):
                remaining = chase_result.get("remaining_size", remaining)
            if remaining <= 0:
                return True, chase_result
        return False, None

    def _apply_kelly_sizing(
        self,
        strategy_legs: List[Dict],
        bankroll: Optional[float],
        edge_pct: Optional[float],
        win_prob: float,
        liquidity_limit: float,
        max_exposure_pct: Optional[float],
        min_bet: float
    ) -> Tuple[List[Dict], Optional[float]]:
        if bankroll is None or edge_pct is None:
            return strategy_legs, None

        size = self.calculate_kelly_size(
            bankroll=bankroll,
            edge_pct=edge_pct,
            win_prob=win_prob,
            liquidity_limit=liquidity_limit,
            max_exposure_pct=max_exposure_pct,
            min_bet=min_bet
        )
        if size <= 0:
            return strategy_legs, 0.0

        sized = []
        for leg in strategy_legs:
            new_leg = {**leg}
            new_leg["size"] = min(new_leg.get("size", size), size)
            sized.append(new_leg)
        return sized, size

    async def execute_strategy(
        self,
        strategy_legs: List[Dict],
        expected_payout: float,
        bankroll: Optional[float] = None,
        edge_pct: Optional[float] = None,
        win_prob: float = 0.98,
        liquidity_limit: float = float("inf"),
        max_exposure_pct: Optional[float] = None,
        min_bet: float = 0.0
    ) -> Dict:
        """
        Validates and executes a multi-leg strategy.
        Stage - Pre-flight: Gating & Gas Logic.
        Stage - Execution: Parallel Dispatch.
        Stage - Monitoring & Resolution: Recovery Handler.
        """
        if self.risk_guardian and not self.risk_guardian.can_trade():
            return {"success": False, "reason": "RiskGuardian blocked trading"}

        total_cost_vwap = Decimal("0")
        
        # 0. Gas Estimation (if any on-chain legs)
        has_chain_legs = any(l.get('type') == 'ON_CHAIN' for l in strategy_legs)
        chain_fees = Decimal("0")
        
        if has_chain_legs:
            gas_params = await self.gas_estimator.get_optimal_gas()
            # Estimate fee: $0.05 per tx simplified
            chain_fees = Decimal("0.05") * Decimal(str(sum(1 for l in strategy_legs if l.get('type')=='ON_CHAIN')))
            logger.debug(f"Estimated Chain Fees: ${float(chain_fees):.4f}")

        # 0. Kelly sizing (optional)
        strategy_legs, kelly_size = self._apply_kelly_sizing(
            strategy_legs=strategy_legs,
            bankroll=bankroll,
            edge_pct=edge_pct,
            win_prob=win_prob,
            liquidity_limit=liquidity_limit,
            max_exposure_pct=max_exposure_pct,
            min_bet=min_bet
        )
        if kelly_size == 0:
            return {"success": False, "reason": "Kelly sizing returned 0 (no edge)"}

        # 1. VWAP Validation & Pre-flight Gating
        for leg in strategy_legs:
            side = leg['side'].upper()
            book = leg.get('order_book')
            size = leg['size']
            
            vwap_price = Decimal("0")
            if not book:
                if leg.get('type') == 'ON_CHAIN' and side == 'MINT':
                    vwap_price = Decimal("1")
                else:
                    vwap_price = Decimal(str(leg['limit_price']))
            else:
                if side == 'BUY':
                    vwap_price = Decimal(str(VWAPEngine.calculate_buy_vwap(book['asks'], size)))
                else:
                    vwap_price = Decimal(str(VWAPEngine.calculate_sell_vwap(book['bids'], size)))
                    
            if vwap_price is None:
                return {"success": False, "reason": f"Insufficient liquidity for leg {leg['token_id']}"}
                
            size_d = Decimal(str(size))
            if side == 'BUY' or (leg.get('type')=='ON_CHAIN' and side=='MINT'):
                total_cost_vwap += (vwap_price * size_d)
            else:
                total_cost_vwap -= (vwap_price * size_d)

        # Net Profit Check
        clob_fees = Decimal("0")
        try:
            expected_payout_d = Decimal(str(expected_payout))
        except (InvalidOperation, ValueError):
            expected_payout_d = Decimal("0")
        net_profit = expected_payout_d - total_cost_vwap - chain_fees - clob_fees
        
        if net_profit < Decimal(str(self.min_net_profit)):
             logger.info(f"Gating: Profit ${float(net_profit):.4f} < ${self.min_net_profit}. Aborted.")
             return {
                 "success": False, 
                 "reason": f"Profit Gating Failed. Net: ${float(net_profit):.3f} < ${self.min_net_profit}"
             }
             
        # 2. Parallel Execution (The "Hands")
        logger.info(f"⚡ Executing Strategy. Net Projected: ${float(net_profit):.3f}")
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
            self.notifier.send_trade(f"Ejecución Exitosa: +${float(net_profit):.2f} Profit")
            if self.risk_guardian:
                self.risk_guardian.record_trade(float(net_profit))
            return {
                "success": True,
                "net_profit_projected": float(net_profit),
                "latency": duration,
                "reason": "Full Execution",
                "order_ids": [l.get('order_id') for l in strategy_legs]
            }
        elif len(successful_legs) == 0:
            self.notifier.send_alert("Error Crítico: Fallo total en ejecución (todas las legs)")
            if self.risk_guardian:
                self.risk_guardian.record_trade(-abs(float(net_profit)))
            return {
                "success": False,
                "reason": "All Legs Failed"
            }
        else:
            # PARTIAL EXECUTION -> RECOVERY
            logger.warning(f"⚠️ PARTIAL FILL. Success: {len(successful_legs)}, Failed: {len(failed_legs)}. Triggering RecoveryHandler.")
            self.notifier.send_alert("Error Crítico: Ejecución parcial, activando recovery.")
            if self.risk_guardian:
                self.risk_guardian.record_trade(-abs(float(net_profit)))
            
            if self.metrics:
                self.metrics.recovery_counter.inc()
                
            # Fire and forget recovery? Or await?
            await self.recovery.handle_partial_failure(successful_legs, failed_legs)
            
            return {
                "success": False,
                "reason": "Partial Execution - Recovery Triggered",
                "recovery_active": True
            }

    async def execute_atomic_strategy(
        self,
        strategy_legs: List[Dict],
        expected_payout: float,
        bankroll: Optional[float] = None,
        edge_pct: Optional[float] = None,
        win_prob: float = 0.98,
        liquidity_limit: float = float("inf"),
        max_exposure_pct: Optional[float] = None,
        min_bet: float = 0.0
    ) -> Dict:
        """
        Execute legs concurrently. If any leg fails or exceeds slippage, cancel/hedge immediately.
        """
        if self.risk_guardian and not self.risk_guardian.can_trade():
            return {"success": False, "reason": "RiskGuardian blocked trading"}

        strategy_legs, kelly_size = self._apply_kelly_sizing(
            strategy_legs=strategy_legs,
            bankroll=bankroll,
            edge_pct=edge_pct,
            win_prob=win_prob,
            liquidity_limit=liquidity_limit,
            max_exposure_pct=max_exposure_pct,
            min_bet=min_bet
        )
        if kelly_size == 0:
            return {"success": False, "reason": "Kelly sizing returned 0 (no edge)"}

        tasks = [self._execute_leg_with_timeout(leg) for leg in strategy_legs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful_legs = []
        failed_legs = []

        for leg, result in zip(strategy_legs, results):
            if isinstance(result, Exception) or result is None:
                failed_legs.append(leg)
                continue

            order_id = result.get("order_id") if isinstance(result, dict) else result
            leg["order_id"] = order_id
            executed_price = self._extract_execution_price(result)
            expected_price = leg.get("expected_price", leg.get("limit_price"))
            max_slippage_pct = leg.get("max_slippage_pct", 0.0)

            if executed_price and expected_price and max_slippage_pct > 0:
                slippage_pct = abs(executed_price - expected_price) / expected_price * 100
                if slippage_pct > max_slippage_pct:
                    leg["slippage_pct"] = slippage_pct
                    failed_legs.append(leg)
                    continue

            if isinstance(result, dict) and result.get("status") == "partial":
                async with self._order_lock:
                    chased, chase_result = await self._chase_partial_fill(leg, result)
                if chased and chase_result:
                    successful_legs.append(leg)
                else:
                    failed_legs.append(leg)
                continue

            successful_legs.append(leg)

        if failed_legs:
            for leg in successful_legs:
                await self._cancel_leg(leg)
            if successful_legs:
                await self.recovery.handle_partial_failure(successful_legs, failed_legs)
            self.notifier.send_alert("Error Crítico: Ejecución atómica fallida, activando hedge/cancel.")
            if self.risk_guardian:
                self.risk_guardian.record_trade(-1.0)
            return {"success": False, "reason": "Atomic execution failed", "failed_legs": failed_legs}

        self.notifier.send_trade("Ejecución Exitosa: ejecución atómica completa.")
        if self.risk_guardian:
            self.risk_guardian.record_trade(1.0)
        return {
            "success": True,
            "reason": "Atomic execution success",
            "order_ids": [l.get('order_id') for l in strategy_legs]
        }

    async def _execute_leg_with_timeout(self, leg: Dict) -> Any:
        timeout_s = leg.get("timeout_s")
        if timeout_s:
            return await asyncio.wait_for(self._place_order_task(leg), timeout=timeout_s)
        return await self._place_order_task(leg)
