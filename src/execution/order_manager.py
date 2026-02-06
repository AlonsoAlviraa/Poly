
import asyncio
import logging
import os
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

logger = logging.getLogger("OrderManager")

class CircuitBreaker:
    """
    Prevents cascading failures by stopping execution after repeated API errors.
    """
    def __init__(self, name: str, threshold: int = 3, reset_timeout: int = 60):
        self.name = name
        self.threshold = threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED" # CLOSED, OPEN

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.threshold:
            self.state = "OPEN"
            logger.critical(f"🛑 CIRCUIT BREAKER [{self.name}] OPENED! Emergency Stop Triggered.")

    def record_success(self):
        if self.state == "OPEN":
            logger.info(f"🟢 CIRCUIT BREAKER [{self.name}] CLOSED. System stable.")
        self.failures = 0
        self.state = "CLOSED"

    def can_execute(self) -> bool:
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.reset_timeout:
                logger.info(f"⚠️ CIRCUIT BREAKER [{self.name}] in HALF-OPEN state. Attempting recovery.")
                return True
            return False
        return True

class RiskGatekeeper:
    """
    Validates trades against hard safety limits.
    """
    def __init__(self, max_trade_size: float = 50.0, daily_loss_limit: float = 200.0):
        self.max_trade_size = max_trade_size
        self.daily_loss_limit = daily_loss_limit
        self.current_daily_loss = 0.0
        self.last_reset_day = datetime.now().date()

    def check_limits(self, size: float, min_liquidity_required: float, order_book: Dict) -> Tuple[bool, str]:
        today = datetime.now().date()
        if today > self.last_reset_day:
            self.current_daily_loss = 0.0
            self.last_reset_day = today

        # 1. Size Check
        if size > self.max_trade_size:
            return False, f"Trade size {size} exceeds MAX_TRADE_SIZE {self.max_trade_size}"
        
        # 2. Daily Loss Check
        if self.current_daily_loss >= self.daily_loss_limit:
            return False, f"Daily loss limit {self.daily_loss_limit} reached (${self.current_daily_loss})"

        # 3. Liquidity Depth Check (Slippage protection)
        # Verify if there is enough size at the top of the book or within acceptable range
        top_size = 0.0
        if order_book:
            for level in order_book.get('asks', []): # Assuming we want to BUY
                top_size += float(level.get('size', level.get('amount', 0)))
                if top_size >= min_liquidity_required:
                    break
        
        if top_size < min_liquidity_required:
            return False, f"Insufficient liquidity: Found ${top_size} but need ${min_liquidity_required}"

        return True, ""

    def record_pnl(self, pnl: float):
        if pnl < 0:
            self.current_daily_loss += abs(pnl)
            logger.warning(f"💸 Daily Loss Updated: -${abs(pnl)}. Total Today: -${self.current_daily_loss}")

class OrderResult:
    def __init__(self, success: bool, filled_size: float, price: float, order_id: str = None, error: str = None):
        self.success = success
        self.filled_size = filled_size
        self.price = price
        self.order_id = order_id
        self.error = error

class OrderManager:
    """
    Handles Atomic Execution and Autonomous Panic Hedging.
    """
    def __init__(self, poly_executor: Any, hedge_executor: Any, dry_run: bool = False):
        self.poly_executor = poly_executor
        self.hedge_executor = hedge_executor
        self.dry_run = dry_run
        
        self.cb_poly = CircuitBreaker("Polymarket")
        self.cb_hedge = CircuitBreaker("HedgeExchange")
        self.risk = RiskGatekeeper(
            max_trade_size=float(os.getenv("MAX_TRADE_SIZE", "50.0")),
            daily_loss_limit=float(os.getenv("DAILY_LOSS_LIMIT", "200.0"))
        )

    async def execute_arbitrage(self, opportunity: Any):
        """
        Main entry point for atomic execution.
        """
        # Validate Circuit Breakers
        if not self.cb_poly.can_execute() or not self.cb_hedge.can_execute():
            logger.error("🛑 Blocked by Circuit Breaker. Check API status.")
            return

        # Pre-Execution Checklist
        target_size = 10.0 # TODO: Implement dynamic sizing based on Kelly/Bankroll
        # Fetch latest book for liquidity check
        poly_book = await self._safe_call(self.poly_executor.get_order_book, opportunity.mapping.polymarket_id)
        
        allowed, reason = self.risk.check_limits(target_size, target_size * 2, poly_book)
        if not allowed:
            logger.warning(f"⛔ Trade Rejected by RiskGatekeeper: {reason}")
            return

        logger.info(f"⚡ [EXEC] Starting Atomic Arb | EV: {opportunity.ev_net:.2f}% | Size: ${target_size}")

        if self.dry_run:
            await self._simulate_execution(opportunity, target_size)
            return

        # PARALLEL DISPATCH (RACE CONDITION PREVENTION)
        tasks = [
            self._execute_leg_poly(opportunity, target_size),
            self._execute_leg_hedge(opportunity, target_size)
        ]
        
        results = await asyncio.gather(*tasks)
        poly_res, hedge_res = results

        # POST-EXECUTION RECOVERY (PANIC HEDGE)
        await self._synchronize_state(poly_res, hedge_res)

    async def _execute_leg_poly(self, opp: Any, size: float) -> OrderResult:
        """Leg A: Polymarket (FOK preferred)"""
        try:
            # Polymarket executor is sync, use to_thread
            res = await asyncio.to_thread(
                self.poly_executor.place_fok_order,
                token_id=opp.mapping.polymarket_id,
                side="BUY",
                price=opp.poly_yes_price,
                size=size
            )
            if res.success:
                self.cb_poly.record_success()
                logger.info(f"🚀 [EXECUTION] 🔵 POLY: FILLED @ {res.avg_price:.3f} | ID: {res.order_id}")
                return OrderResult(True, res.filled_size, res.avg_price, res.order_id)
            else:
                self.cb_poly.record_failure()
                logger.warning(f"❌ [EXECUTION] 🔵 POLY: FAILED ({res.error})")
                return OrderResult(False, 0, 0, error=res.error)
        except Exception as e:
            self.cb_poly.record_failure()
            logger.error(f"💀 [EXECUTION] 🔵 POLY: CRITICAL ERROR ({str(e)})")
            return OrderResult(False, 0, 0, error=str(e))

    async def _execute_leg_hedge(self, opp: Any, size: float) -> OrderResult:
        """Leg B: Betfair/SX Hedge"""
        try:
            res = await self.hedge_executor.place_order(
                market_id=opp.mapping.betfair_market_id,
                side="LAY",
                price=opp.betfair_lay_odds,
                size=size
            )
            if res.success:
                self.cb_hedge.record_success()
                logger.info(f"🚀 [EXECUTION] 🔴 HEDGE: FILLED @ {res.avg_price:.3f} | ID: {res.order_id}")
                return OrderResult(True, res.filled_size, res.avg_price, res.order_id)
            else:
                self.cb_hedge.record_failure()
                logger.warning(f"❌ [EXECUTION] 🔴 HEDGE: FAILED ({res.error})")
                return OrderResult(False, 0, 0, error=res.error)
        except Exception as e:
            self.cb_hedge.record_failure()
            logger.error(f"💀 [EXECUTION] 🔴 HEDGE: CRITICAL ERROR ({str(e)})")
            return OrderResult(False, 0, 0, error=str(e))

    async def _synchronize_state(self, poly: OrderResult, hedge: OrderResult):
        """Autonomous Decision Tree for Legging Risk."""
        if poly.success and hedge.success:
            logger.info("🎯 [RISK] ARBITRAGE NEUTRALIZED. Both legs filled correctly.")
            return

        if not poly.success and not hedge.success:
            logger.info("💨 [RISK] BOTH LEGS REJECTED. Safety first - position remained flat.")
            return

        # LEGGING RISK: One leg filled, one failed.
        logger.critical("🚨 [RISK] LEGGING RISK DETECTED! Position is unbalanced.")
        
        if poly.success and not hedge.success:
            logger.warning(f"⚠️ [RISK] PANIC HEDGE TRIGGERED: Selling Poly @ Market to neutralize.")
            await self._emergency_exit("poly", poly)
            self.risk.record_pnl(-(poly.filled_size * 0.02)) 

        if hedge.success and not poly.success:
            logger.warning(f"⚠️ [RISK] PANIC HEDGE TRIGGERED: Neutering Hedge (Closing position).")
            await self._emergency_exit("hedge", hedge)
            self.risk.record_pnl(-(hedge.filled_size * 0.05)) 

    async def _emergency_exit(self, platform: str, leg: OrderResult):
        """autonomous-agent-pattern: Self-liquidation logic."""
        logger.warning(f"🔥 EMERGENCY EXIT on {platform.upper()}. Attempting to go flat...")
        try:
            if platform == "poly":
                await asyncio.to_thread(
                    self.poly_executor.place_order, 
                    token_id=leg.order_id, # Or use the token_id from opp
                    side="SELL",
                    price=0.01, # Sacrifice price to get filled
                    size=leg.filled_size
                )
            else:
                await self.hedge_executor.place_order(
                    market_id=leg.order_id,
                    side="BACK",
                    price=1000, 
                    size=leg.filled_size
                )
            logger.info(f"✅ Emergency liquidation order sent to {platform}.")
        except Exception as e:
            logger.critical(f"💀 TOTAL CAPITULATION: Panic Hedge failed on {platform}! {e}")

    async def _safe_call(self, func, *args):
        """Wrapper for sync/async agnostic calls."""
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args)
            return await asyncio.to_thread(func, *args)
        except:
            return None

    async def _simulate_execution(self, opp: Any, size: float):
        """Simulation mode for testing Panic Hedge logic."""
        logger.info("[DRY-RUN] Simulating Parallel Execution (200ms latency)...")
        await asyncio.sleep(0.2)
        
        import random
        # 20% chance of failure to test recovery
        p_success = random.random() > 0.2
        h_success = random.random() > 0.2
        
        poly = OrderResult(p_success, size if p_success else 0, opp.poly_yes_price, "SIM_ID_P")
        hedge = OrderResult(h_success, size if h_success else 0, opp.betfair_lay_odds, "SIM_ID_H")
        
        await self._synchronize_state(poly, hedge)
