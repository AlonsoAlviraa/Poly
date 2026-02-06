
import asyncio
import argparse
import sys
import os
from datetime import datetime
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
from src.data.wss_manager import MarketUpdate, PolymarketStream, BetfairStream, SXBetPoller
from src.data.betfair_client import BetfairClient # For session management
from src.data.sx_bet_client import SXBetClient
from src.data.cache_manager import CacheManager
from src.arbitrage.realtime_scanner import RealTimeScanner # New Module

import numpy as np

BANNER = r"""
    ____        __                      __     _____                 ____  __           
   / __ \____  / /_  ______ ___  ____  / /_   / ___/____  ___  ___  / __ \/ /___  ____  
  / /_/ / __ \/ / / / / __ `__ \/ __ \/ __/   \__ \/ __ \/ _ \/ _ \/ / / / / __ \/ __ \ 
 / ____/ /_/ / / /_/ / / / / / / / / / /_    ___/ / /_/ /  __/  __/ /_/ / / /_/ / /_/ / 
/_/    \____/_/\__, /_/ /_/ /_/_/ /_/\__/   /____/ .___/\___/\___/_____/_/\____/ .___/  
              /____/                              /_/                           /_/       
              
    >> SYSTEM: APU (Arbitrage Processing Unit)
    >> MODE:   Hybrid (Poly/Betfair)
    >> STATUS: ONLINE
"""

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
            sys.exit(1)
        
        # 1. Data Layer: Real vs Mock
        real_exec = os.getenv("REAL_ORDER_EXECUTION", "FALSE").upper() == "TRUE"
        
        # Use Real Data if available (Hybrid Mode support)
        if self.data_client and real_exec:
            # Not implemented in this strict version - focus on Observer Mode for now
            pass 

        # 2. Math Core (Detection)
        if not self.polytope: return

        # ... (Rest of cycle logic usually here) ...

if __name__ == "__main__":
    print(BANNER)
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mode", type=str, choices=["live", "paper", "observer", "audit", "realtime", "mega-audit"], default="paper")
    parser.add_argument("--use-websockets", action="store_true")
    parser.add_argument("--record-db", action="store_true")
    parser.add_argument("--tui", action="store_true")
    args = parser.parse_args()
    
    # Map CLI to Env
    os.environ["MODE"] = args.mode.upper()
    if args.use_websockets: os.environ["USE_WEBSOCKETS"] = "TRUE"
    if args.record_db: os.environ["RECORD_DB"] = "TRUE"
    if args.tui: os.environ["USE_TUI"] = "TRUE"
    
    if args.mode.upper() in ["OBSERVER", "AUDIT"]:
        observer = ObserverMode()
        try:
            asyncio.run(observer.start())
        except KeyboardInterrupt:
            pass
            
    elif args.mode.upper() == "MEGA-AUDIT":
        print(">> STARTING MEGA AUDIT MODE...")
        from src.mega_audit import run_mega_audit
        try:
            asyncio.run(run_mega_audit())
        except KeyboardInterrupt:
            pass
    elif args.mode.upper() == "REALTIME":
        # Initialize RealTime components
        print(">> STARTING REALTIME MODE (WSS)...")
        from src.data.gamma_client import GammaAPIClient
        from src.arbitrage.cross_platform_mapper import CrossPlatformMapper
        from src.execution.order_manager import OrderManager

        async def run_realtime():
            print(">> [Warmup] Initializing realtime engine...")
            cache_mgr = CacheManager()
            sx_client = SXBetClient()
            gamma = GammaAPIClient()
            bf_client = BetfairClient()
            
            # 1. Warmup: Load Mappings from Cache or Perform Discovery
            mappings = cache_mgr.get_all_mappings()
            if not mappings:
                print(">> [Warmup] No cache found. Performing live discovery...")
                
                # Parallel fetch of source data
                tasks = [
                    gamma.get_all_match_markets(limit=1000),
                    bf_client.login(),
                    sx_client.get_markets_standardized()
                ]
                results = await asyncio.gather(*tasks)
                poly_markets, bf_login_success, sx_evs = results
                
                target_evs = sx_evs or []
                
                if bf_login_success:
                    target_ids = ['1', '2', '7522', '10']
                    if "betfair.es" in bf_client.base_url: target_ids = ['1', '2', '7522', '11', '4', '7']
                    bf_evs = await bf_client.list_events(event_type_ids=target_ids)
                    target_evs.extend(bf_evs)
                
                if not target_evs:
                    print(">> [Warmup] Warning: No target events found from BF or SX.")
                else:
                    # Bucketing for speed
                    from collections import defaultdict
                    ev_buckets = defaultdict(list)
                    for event in target_evs:
                        ev_start_str = event.get('open_date') or event.get('openDate')
                        if ev_start_str:
                            try:
                                clean_str = ev_start_str.replace('Z', '+00:00').replace(' ', 'T')
                                ev_dt = datetime.fromisoformat(clean_str)
                                event['_start_date_parsed'] = ev_dt
                                ev_buckets[ev_dt.date()].append(event)
                            except: pass

                    mapper = CrossPlatformMapper(min_ev_threshold=-100.0)
                    print(f">> [Warmup] Mapping {len(poly_markets)} Poly markets against {len(target_evs)} target events...")
                    
                    for pm in poly_markets:
                        m = await mapper.map_market(poly_market=pm, betfair_events=target_evs, bf_buckets=ev_buckets)
                        if m: 
                            if m.confidence > 0.8:
                                mappings.append(m)
                    
                    if mappings:
                        cache_mgr.bulk_save(mappings)
                        print(f">> [Warmup] Saved {len(mappings)} mappings to cache.")
            
            # 2. Setup Executors & OrderManager
            dry_run = args.dry_run or (os.getenv("REAL_ORDER_EXECUTION", "FALSE").upper() == "FALSE")
            
            # Poly Executor
            clob_host = os.getenv("CLOB_API_HOST", "https://clob.polymarket.com")
            pk = os.getenv("PRIVATE_KEY", "0" * 64)
            poly_executor = PolymarketCLOBExecutor(host=clob_host, key=pk)
            
            # Hedge Executor (Mock for now, or real SX/BF if available)
            class MockHedgeExecutor:
                async def place_order(self, market_id, side, price, size):
                    return type('obj', (object,), {'success': True, 'filled_size': size, 'avg_price': price, 'order_id': f"HEDGE_{market_id}", 'market_id': market_id})
            
            hedge_executor = MockHedgeExecutor() 
            
            order_manager = OrderManager(poly_executor, hedge_executor, dry_run=dry_run)
            print(f">> [System] OrderManager Initialized (DryRun: {dry_run})")

            # 3. Extract Token IDs for WSS
            print(">> [Warmup] Syncing token IDs...")
            poly_markets = await gamma.get_all_match_markets(limit=200)
            token_ids = []
            market_map = {m['id']: m for m in poly_markets}
            for mapping in mappings:
                m = market_map.get(mapping.polymarket_id)
                if m and m.get('tokens'):
                    for t in m['tokens']:
                        tid = t.get('token_id') or t.get('clobTokenId')
                        if tid: token_ids.append(tid)
            
            token_ids = list(set(token_ids))
            print(f">> [Warmup] Final: {len(mappings)} mappings | {len(token_ids)} WSS tokens.")

            # 4. Init Streams & Poller
            poly_stream = PolymarketStream(token_ids=token_ids)
            if not bf_client.is_authenticated: await bf_client.login()
            bf_stream = BetfairStream(bf_client.session_token, bf_client.app_key)
            
            # SX Poller
            sx_market_ids = list(set([m.sx_market_id for m in mappings if m.sx_market_id]))
            sx_poller = SXBetPoller(sx_client, sx_market_ids)
            if sx_market_ids:
                print(f">> [Warmup] Monitoring {len(sx_market_ids)} markets on SX Bet.")

            # 5. Init Scanner
            scanner = RealTimeScanner(poly_stream, bf_stream, sx_poller, order_manager=order_manager)
            scanner.load_mappings(mappings)
            
            async def log_opp(opp):
                print(f"🚀 REALTIME ARB FOUND! ROI: {opp.ev_net:.2f}% | {opp.mapping.polymarket_question} (Poly: {opp.poly_yes_price} | BF Lay: {opp.betfair_lay_odds})")
            scanner.add_callback(log_opp)
            
            # 6. Extract BF Market IDs
            bf_market_ids = list(set([m.betfair_market_id for m in mappings if m.betfair_market_id]))
            print(f">> [Warmup] Subscribing to {len(bf_market_ids)} Betfair MArkets.")

            # 7. Connect and Run
            print(">> [System] CONNECTING TO STREAMS...")
            tasks = [
                poly_stream.connect(),
                bf_stream.connect(bf_market_ids), # PASS IDS HERE
                sx_poller.connect(),
                scanner.start()
            ]
            
            try:
                await asyncio.gather(*tasks)
            except (KeyboardInterrupt, asyncio.CancelledError):
                print(">> Stopping RealTime Engine...")
            finally:
                await poly_stream.disconnect()
                await bf_stream.disconnect()
                await sx_poller.disconnect()
                scanner.running = False
                
                # 📊 GENERATE REPORT ON EXIT
                print("📊 Generando reporte del Mega Debugger...")
                report_path = scanner.audit_logger.generate_html_report()
                if report_path:
                    print(f"📊 Mega Debugger: Summary report ready at {report_path}")

        try:
            asyncio.run(run_realtime())
        except KeyboardInterrupt:
            print("\n🛑 SYSTEM SHUTDOWN")
    else:
        # For simple paper/observer modes
        engine = QuantArbitrageEngine(dry_run=(args.mode == "paper" or args.dry_run))
        try:
            asyncio.run(engine.run())
        except KeyboardInterrupt:
            print("\n🛑 SYSTEM SHUTDOWN")
