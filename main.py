import asyncio
import argparse
import sys
import os
from dotenv import load_dotenv

# Load Env
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Logging replaced by StructuredLogger where applicable
from src.utils.structured_log import audit_logger 

# Modules
from src.math.polytope import MarginalPolytope
from src.math.bregman import barrier_frank_wolfe_projection
from src.execution.smart_router import SmartRouter
from src.execution.clob_executor import PolymarketCLOBExecutor
from src.data.graph_factory import GraphFactory
from src.utils.metrics import MetricsServer
from src.risk.circuit_breaker import CircuitBreaker
from src.risk.position_sizer import KellyPositionSizer
from src.observer_mode import ObserverMode
from src.ui.terminal_dashboard import TerminalDashboard
from src.data.wss_manager import MarketUpdate, PolymarketStream, BetfairStream
from src.data.betfair_client import BetfairClient # For session management

import numpy as np

class QuantArbitrageEngine:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        
        # 0. Data Factory
        self.graph_factory = GraphFactory()
        self.active_market_ids = []
        self.polytope = None
        
        # 1. Observability (Module 3)
        self.metrics = MetricsServer(port=8000)
        self.metrics.start()
        
        # 2. Risk Management (Module 4)
        # Load Risk Config from Env or Defaults
        initial_cap = float(os.getenv("INITIAL_CAPITAL", 1000.0))
        self.breaker = CircuitBreaker(initial_capital=initial_cap)
        self.kelly = KellyPositionSizer(fraction=0.25)
        
        # 3. Execution & Data
        real_exec = os.getenv("REAL_ORDER_EXECUTION", "FALSE").upper() == "TRUE"
        clob_host = os.getenv("CLOB_API_HOST", "https://clob.polymarket.com")
        pk = os.getenv("PRIVATE_KEY", "dummy_key")
        
        # Validation Bypass for Dry Run logic with Real Data
        if pk == "dummy_key":
            # Use valid hex format (64 chars) to satisfy py_clob_client
            pk = "0" * 64
        
        # Always init Real Client for Data (Read-Only)
        try:
            self.data_client = PolymarketCLOBExecutor(host=clob_host, key=pk)
        except Exception as e:
            self.data_client = None
            audit_logger.warning("Could not init Real Data Client.", error=str(e))

        if real_exec and not self.dry_run:
            audit_logger.info("⚠️ INITIALIZING REAL EXECUTOR")
            self.executor_client = self.data_client
        else:
            class MockExecutor:
                def place_order(self, tid, side, price, size):
                    import time; time.sleep(0.05) 
                    return f"OID_{tid}_{int(time.time())}"
                # Add mock balance
                def get_balance(self): return 1000.0
                
            self.executor_client = MockExecutor()
            audit_logger.info("Using MOCK Executor")
        
        # Load RPCs from Env
        rpc_primary = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
        rpc_backup = os.getenv("BACKUP_RPC_URL", "https://rpc-mainnet.maticvigil.com")
        rpc_urls = [rpc_primary, rpc_backup]
        
        # Risk: Min Profit to cover 3x Gas (approx $0.05 * 3 = $0.15)
        min_profit_env = float(os.getenv("MIN_NET_PROFIT", 0.15))
        
        self.router = SmartRouter(self.executor_client, rpc_urls=rpc_urls, metrics_server=self.metrics, min_profit=min_profit_env)
        self.min_liquidity_depth = 500.0 # Task 3 Threshold
        
        # 4. TUI (Task 4)
        self.dashboard = None
        if os.getenv("USE_TUI", "FALSE").upper() == "TRUE":
            self.dashboard = TerminalDashboard()
            self.dashboard.start()
        
        # 4. WebSocket Streams (Task 1)
        self.poly_stream = None
        self.bf_stream = None
        self.use_wss = os.getenv("USE_WEBSOCKETS", "FALSE").upper() == "TRUE"
        
        audit_logger.info("ENGINE_STARTUP", dry_run=self.dry_run, status="INITIALIZED", rpcs=len(rpc_urls), min_profit=min_profit_env, real_exec=real_exec)

    async def run(self):
        audit_logger.info("LOOP_START", port=8000)
        
        if self.use_wss:
            # Discovery tokens & markets (simplified for demo)
            # In a real scenario, we'd fetch these from Gamma/Discovery
            token_ids = self.active_market_ids or ["0x..."] 
            market_ids = [] # To be filled by Discovery
            
            # Instantiate Streams
            self.poly_stream = PolymarketStream(token_ids)
            
            # Setup Betfair Session
            bf_client = BetfairClient()
            if await bf_client.login():
                self.bf_stream = BetfairStream(bf_client._session.ssoid, bf_client.app_key)
            
            # Subscribe (Pub/Sub Pattern)
            if self.poly_stream: self.poly_stream.subscribe(self.router.handle_market_update)
            if self.bf_stream: self.bf_stream.subscribe(self.router.handle_market_update)
            
            # Connect
            if self.poly_stream: await self.poly_stream.connect()
            if self.bf_stream: await self.bf_stream.connect(market_ids)
            
            audit_logger.info("📡 Real-Time Streams WIRING COMPLETE")

        while True:
            try:
                # RISK CHECK
                if not self.breaker.can_trade():
                    audit_logger.error("CIRCUIT_BREAKER_ACTIVE", reason=self.breaker.state['broken_reason'])
                    await asyncio.sleep(60)
                    continue

                # ... (Mock Cycle similar to previous) ...
                # Use polling only if WSS is NOT active
                if not self.use_wss:
                    await self._process_mock_cycle()

                # Update Dashboard
                if self.dashboard:
                    self.dashboard.update_summary(
                        balance=self.breaker.state.get('current_balance', 0.0),
                        pnl_daily=0.0, # Placeholder
                        exposure=0.0   # Placeholder
                    )
                    self.dashboard.update_websocket_status("active" if self.use_wss else "polling")

                await asyncio.sleep(5)
            except KeyboardInterrupt:
                break
            except Exception as e:
                audit_logger.error("CRITICAL_LOOP_ERROR", error=e)
                self.metrics.fill_rate_counter.labels(status='failed').inc()
                await asyncio.sleep(5)
    
    def _check_liquidity_gatekeeper(self, market_id: str, side: str) -> bool:
        """Task 3: Enforce $500 threshold in top 3 levels."""
        if not self.data_client: return True
        try:
            book = self.data_client.get_order_book(market_id)
            levels = book.get('asks' if side == 'BUY' else 'bids', [])
            liquidity = sum(float(l.get('price', 0)) * float(l.get('size', 0)) for l in levels[:3])
            
            is_ok = liquidity >= self.min_liquidity_depth
            if not is_ok:
                audit_logger.warning("GATEKEEPER_REJECT", market_id=market_id, liquidity=liquidity, threshold=self.min_liquidity_depth)
            return is_ok
        except Exception as e:
            audit_logger.error("GATEKEEPER_ERROR", error=str(e))
            return False

    async def _process_mock_cycle(self):
        """
        Executes one full cycle. 
        Supports Real Data Injection if REAL_ORDER_EXECUTION is set.
        """
        
        # --- SAFETY: HARD STOP & BALANCE SYNC ---
        current_balance = self.breaker.state.get('current_balance', 21.0)
        
        # Try to sync real balance
        if self.data_client and hasattr(self.data_client, 'get_balance'):
            try:
                real_bal = self.data_client.get_balance()
                if real_bal is not None and real_bal > 0:
                    current_balance = real_bal
                    self.breaker.state['current_balance'] = real_bal
            except Exception as e:
                audit_logger.warning("BALANCE_SYNC_FAILED", error=str(e))
        
        # Hard Stop Check
        if current_balance < 10.0:
            audit_logger.critical("EMERGENCY_SHUTDOWN", 
                                   reason="HARD_STOP_BALANCE_LOW", 
                                   balance=current_balance,
                                   action="HALT_AND_LIQUIDATE")
            # Attempt emergency position close (if any open)
            # In atomic arb, positions should be closed per trade. 
            # This is a final safety net.
            sys.exit(1)
        
        # 1. Data Layer: Real vs Mock
        real_exec = os.getenv("REAL_ORDER_EXECUTION", "FALSE").upper() == "TRUE"
        
        # Use Real Data if available (Hybrid Mode support)
        if self.data_client and real_exec:
            # LIVE DATA FEED - Use SAMPLING markets (have orderbooks)
            if not self.active_market_ids:
                try:
                    # KEY FIX: Use get_sampling_simplified_markets instead of get_markets
                    # This returns markets that actually have orderbooks
                    if hasattr(self.data_client.client, 'get_sampling_simplified_markets'):
                         next_cursor = ""
                         found = False
                         for _ in range(10): # Sampling markets are fewer, 10 pages enough
                             try:
                                 resp = self.data_client.client.get_sampling_simplified_markets(next_cursor=next_cursor)
                             except Exception as e:
                                 audit_logger.warning("SAMPLING_MARKETS_ERROR", error=str(e))
                                 break
                             
                             data = resp.get('data', []) if isinstance(resp, dict) else resp
                             if not data: break

                             for mkt in data:
                                 # Sampling markets: check accepting_orders flag
                                 if not mkt.get('accepting_orders', False): continue
                                 if mkt.get('closed', False): continue
                                 
                                 tokens = mkt.get('tokens', [])
                                 if len(tokens) >= 2:
                                     self.active_market_ids = [t.get('token_id') for t in tokens[:2]]
                                     
                                     # Verify orderbook exists
                                     try:
                                         book = self.data_client.get_order_book(self.active_market_ids[0])
                                         has_bids = len(book.bids if hasattr(book, 'bids') else book.get('bids', [])) > 0
                                         has_asks = len(book.asks if hasattr(book, 'asks') else book.get('asks', [])) > 0
                                         
                                         if has_bids and has_asks:
                                             audit_logger.info("MARKET_AUTO_CONFIG", 
                                                 msg=f"Found market with orderbook: {mkt.get('condition_id', 'N/A')[:30]}",
                                                 ids=self.active_market_ids,
                                                 bids=has_bids, asks=has_asks)
                                             constraints = [{'coeffs': [(0, 1), (1, 1)], 'sense': '=', 'rhs': 1}]
                                             self.polytope = MarginalPolytope(2, constraints)
                                             found = True
                                             break
                                         else:
                                             self.active_market_ids = None
                                     except Exception:
                                         self.active_market_ids = None
                                         continue
                                         
                             if found: break
                             next_cursor = resp.get('next_cursor', '') if isinstance(resp, dict) else ''
                             if not next_cursor or next_cursor == "LTE=": break
                except Exception as e:
                    audit_logger.error("MARKET_DISCOVERY_FAILED", error=str(e))

            if not self.active_market_ids:
                audit_logger.warning("NO_ACTIVE_MARKETS", msg="No Active Markets found for Live Feed.")
                return

            # Fetch Live Prices (Theta)
            theta, ts = self.graph_factory.get_live_theta(self.data_client, self.active_market_ids)
            
            # --- 4. Filtering: Empty/Dead Books ---
            if np.any(theta <= 0.0001):
                audit_logger.warning("LOW_LIQUIDITY_SKIP", msg="One or more assets have 0 price (Empty Book).", prices=theta.tolist())
                # If persistent, clear active_market_ids to find new one?
                # self.active_market_ids = [] 
                return

            import time
            if time.time() - ts > 0.5:
                # logger.warning("⚠️ Market Data Stale (>500ms).")
                pass 
                
            market_ids = self.active_market_ids
            
        else:
            # MOCK DATA
            market_ids = ["m_A", "m_B"]
            theta = np.array([0.40, 0.40])
            constraints = [{'coeffs': [(0, 1), (1, 1)], 'sense': '=', 'rhs': 1}]
            if not self.polytope:
                self.polytope = MarginalPolytope(n_conditions=len(theta), constraints=constraints)


        # 2. Math Core (Detection)
        if not self.polytope: return

        if self.polytope.is_feasible(theta):
            # Only return if feasible (no arb). 
            # But wait, feasible means Theta is INSIDE polytope.
            # If Theta is OUTSIDE, we have Arb.
            # is_feasible checks Ax=b.
            # If our constraint is Yes+No=1. And prices 0.4+0.4=0.8.
            # 0.8 != 1. So it is NOT feasible.
            # So is_feasible returns False.
            # Code says: if is_feasible: return. (Correct, no arb).
            return 
            
        audit_logger.info("ARBITRAGE_DETECTED", prices=theta.tolist(), real_data=bool(self.data_client))
        self.metrics.arb_opportunities_gauge.inc()
        
        try:
            mu_star = barrier_frank_wolfe_projection(theta, self.polytope)
        except Exception as e:
            audit_logger.error("MATH_SOLVER_FAILED", error=e)
            return

        # 3. Strategy Formulation & Inventory Management (Kelly)
        diff = mu_star - theta
        legs = []
        est_gas_fee = 0.05 # From GasEstimator (simplified per leg)
        
        for i, change in enumerate(diff):
            mid = market_ids[i]
            if change <= 0.01: continue 
            
            # Kelly Inputs
            price = theta[i]
            target_price = mu_star[i] # Bregman Projection
            b_odds = (1.0 - price) / price
            liquidity = 1000.0 
            
            # Calculate Size
            size = self.kelly.calculate_size(
                capital=self.breaker.state['current_balance'],
                win_prob=1.0,
                profit_ratio=b_odds,
                liquidity_limit=liquidity
            )
            
            # --- 1. Gas-Aware Kelly Adjustment (Strict EV Check) ---
            # EV_net = (P_win * Profit) - (P_loss * Loss) - Gas
            # Profit = Size * (1.0 - Price)
            # Loss = Size * Price (if we lose 100%)
            
            # For pure arb, P_win=1.0.
            p_win = 1.0
            p_loss = 0.0
            gross_profit = size * (1.0 - price)
            potential_loss = size * price
            
            ev_net = (p_win * gross_profit) - (p_loss * potential_loss) - est_gas_fee
            
            if ev_net <= 0:
                 audit_logger.info("EV_NEGATIVE_GAS", ev=ev_net, size=size, msg="Skipping Leg: Gas eats Edge")
                 continue
            
            # Track Drift (Target vs Execution Limit)
            # In simulation limit = theta[i] (taking liquidity).
            drift = abs(target_price - price)
            self.metrics.arb_drift_gauge.set(drift)
            
            legs.append({
                "token_id": mid,
                "side": "BUY",
                "size": size,
                "limit_price": theta[i], 
                "order_book": {"asks": [[theta[i], 1000]]}
            })
            
        if not legs: 
            return

        # 4. Liquidity Gatekeeper (Task 3)
        for i, leg in enumerate(legs):
            if not self._check_liquidity_gatekeeper(leg['token_id'], leg['side']):
                audit_logger.warning("SKIP_TRADE_LOW_LIQUIDITY", leg=i)
                return

        # 5. Execution (Smart Router FSM)
        # Assuming Payout=1.0 * Size (if balanced). 
        # Simplified: Expected Payout = Sum(Size * 1.0) for the bundle?
        # Only if we buy A and B.
        
        total_payout = sum(l['size'] for l in legs) # Approx if A+B=1
        
        result = await self.router.execute_strategy(legs, expected_payout=total_payout)
        
        # 5. Result Handling
        if result['success']:
            audit_logger.info("EXECUTION_SUCCESS", net_profit=result['net_profit_projected'])
            self.metrics.pnl_gauge.inc(result['net_profit_projected'])
            # Since fees were deducted from Net Profit calc, we can infer gross vs net or just track estimate
            # est_gas_fee is per leg... or per strategy? In loop we defined est_gas_fee = 0.05
            # We used est_gas_fee in Kelly check per leg.
            # Total Gas = est_gas_fee * number of executed ON_CHAIN legs (assuming all buy).
            # For this mock cycle we assumed gas check passed.
            self.metrics.gas_spent_counter.inc(est_gas_fee)
            
            self.breaker.record_tx(success=True)
            self.breaker.update_balance(self.breaker.state['current_balance'] + result['net_profit_projected'])
        else:
            if result.get('recovery_active'):
                audit_logger.warning("RECOVERY_TRIGGERED", details=result)
                # Breaker logic depends on final outcome of recovery, which is async/background?
                # For now record as potential fail or wait.
            else:
                 audit_logger.warning("EXECUTION_FAILED", reason=result['reason'])
                 # self.breaker.record_tx(success=False) # Only if technical failure, not gating.
                 if "Gating" not in result['reason']:
                     self.breaker.record_tx(success=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mode", type=str, choices=["live", "paper", "observer"], default="paper")
    parser.add_argument("--use-websockets", action="store_true")
    parser.add_argument("--record-db", action="store_true")
    parser.add_argument("--tui", action="store_true")
    args = parser.parse_args()
    
    # Map CLI to Env
    os.environ["MODE"] = args.mode.upper()
    if args.use_websockets: os.environ["USE_WEBSOCKETS"] = "TRUE"
    if args.record_db: os.environ["RECORD_DB"] = "TRUE"
    if args.tui: os.environ["USE_TUI"] = "TRUE"
    
    if args.mode.upper() == "OBSERVER":
        observer = ObserverMode()
        try:
            asyncio.run(observer.start())
        except KeyboardInterrupt:
            pass
    else:
        engine = QuantArbitrageEngine(dry_run=(args.mode == "paper" or args.dry_run))
        try:
            asyncio.run(engine.run())
        except KeyboardInterrupt:
            pass
