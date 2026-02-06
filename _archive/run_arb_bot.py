#!/usr/bin/env python3
"""
Unified Arbitrage Bot Runner.
Combines all components: scanning, alerting, recording, and execution.

Usage:
    python run_arb_bot.py --mode scan      # One-time scan
    python run_arb_bot.py --mode monitor   # Continuous monitoring with alerts
    python run_arb_bot.py --mode record    # Record data for backtesting
    python run_arb_bot.py --mode full      # All features enabled
"""

import argparse
import logging
import os
import sys
import time
import signal
from datetime import datetime

# Load .env file FIRST
from dotenv import load_dotenv
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.execution.clob_executor import PolymarketCLOBExecutor
from src.arbitrage.combinatorial_scanner import CombinatorialArbScanner
from src.data.backtesting import DataRecorder
from src.alerts.telegram_notifier import AlertManager, ArbitrageAlertIntegration
from src.risk.circuit_breaker import CircuitBreaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('arb_bot.log')
    ]
)
logger = logging.getLogger('ArbBot')


class UnifiedArbBot:
    """
    Unified controller for all arbitrage bot components.
    """
    
    def __init__(self,
                 mode: str = 'scan',
                 min_edge_pct: float = 0.5,
                 scan_interval: int = 30,
                 record_interval: int = 60):
        """
        Args:
            mode: 'scan', 'monitor', 'record', 'full'
            min_edge_pct: Minimum edge to alert on
            scan_interval: Seconds between scans
            record_interval: Seconds between data recordings
        """
        self.mode = mode
        self.min_edge = min_edge_pct
        self.scan_interval = scan_interval
        self.record_interval = record_interval
        
        self._running = False
        
        # Initialize components
        self._init_components()
        
    def _init_components(self):
        """Initialize all bot components."""
        logger.info("Initializing bot components...")
        
        # CLOB Client (read-only mode with dummy key)
        private_key = os.getenv('PRIVATE_KEY', '0x' + '1' * 64)
        
        self.clob = PolymarketCLOBExecutor(
            host='https://clob.polymarket.com',
            key=private_key,
            chain_id=137
        )
        logger.info("✅ CLOB client initialized")
        
        # Arbitrage Scanner
        self.scanner = CombinatorialArbScanner(
            clob_client=self.clob,
            min_edge_pct=self.min_edge,
            min_liquidity_usd=25.0
        )
        logger.info("✅ Arbitrage scanner initialized")
        
        # Circuit Breaker
        self.breaker = CircuitBreaker(
            state_file='breaker_state.json',
            initial_capital=1000.0
        )
        logger.info("✅ Circuit breaker initialized")
        
        # Alert Manager
        self.alerts = AlertManager(
            telegram_token=os.getenv('TELEGRAM_BOT_TOKEN'),
            telegram_chat_id=os.getenv('TELEGRAM_CHAT_ID'),
            min_alert_interval=60,
            min_edge_alert=self.min_edge
        )
        logger.info("✅ Alert manager initialized")
        
        # Data Recorder
        self.recorder = DataRecorder(db_path='market_data.db')
        logger.info("✅ Data recorder initialized")
        
        # Alert integration
        self.arb_monitor = ArbitrageAlertIntegration(
            scanner=self.scanner,
            alert_manager=self.alerts
        )
        
    def run(self):
        """Run the bot in configured mode."""
        self._running = True
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
        logger.info(f"🚀 Starting bot in {self.mode.upper()} mode")
        
        try:
            if self.mode == 'scan':
                self._run_single_scan()
            elif self.mode == 'monitor':
                self._run_monitoring()
            elif self.mode == 'record':
                self._run_recording()
            elif self.mode == 'full':
                self._run_full()
            else:
                logger.error(f"Unknown mode: {self.mode}")
                
        except Exception as e:
            logger.exception(f"Bot error: {e}")
            self.alerts.send_error("Bot Crash", str(e), critical=True)
            
        finally:
            self._shutdown()
            
    def _run_single_scan(self):
        """Run a single arbitrage scan and exit."""
        logger.info("Running single scan...")
        
        opportunities = self.scanner.scan_all()
        
        print("\n" + "=" * 70)
        print(f"SCAN RESULTS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        if not opportunities:
            print("\n  No arbitrage opportunities found.")
            print("  This is normal - arbs are quickly captured by other bots.")
        else:
            print(f"\n  Found {len(opportunities)} opportunities:\n")
            
            for i, opp in enumerate(opportunities[:10]):
                status = "✅" if opp.liquidity_ok else "⚠️"
                print(f"  [{i+1}] {status} {opp.event_title[:40]}")
                print(f"      Strategy: {opp.strategy}")
                print(f"      Edge: {opp.edge_pct:.2f}% | Confidence: {opp.confidence:.0%}")
                print(f"      Cost: ${opp.total_cost:.4f} -> Payout: ${opp.guaranteed_payout:.2f}")
                print()
                
        print("=" * 70)
        
    def _run_monitoring(self):
        """Run continuous monitoring with alerts."""
        logger.info(f"Starting monitoring (interval: {self.scan_interval}s)")
        
        self.alerts.start()
        self.alerts.send_info("Bot Started", f"Monitoring mode (interval: {self.scan_interval}s)")
        
        while self._running:
            if not self.breaker.can_trade():
                logger.warning("Circuit breaker tripped - pausing monitoring")
                time.sleep(60)
                continue
                
            try:
                opportunities = self.scanner.scan_all()
                
                for opp in opportunities:
                    if opp.liquidity_ok and opp.edge_pct >= self.min_edge:
                        self.alerts.send_arb_opportunity(
                            event_title=opp.event_title,
                            strategy=opp.strategy,
                            edge_pct=opp.edge_pct,
                            total_cost=opp.total_cost,
                            guaranteed_payout=opp.guaranteed_payout,
                            liquidity_ok=opp.liquidity_ok,
                            confidence=opp.confidence
                        )
                        logger.info(f"💰 Opportunity: {opp.edge_pct:.2f}% in {opp.event_title[:30]}")
                        
                logger.info(f"Scan complete: {len(opportunities)} opportunities")
                
            except Exception as e:
                logger.error(f"Scan error: {e}")
                
            time.sleep(self.scan_interval)
            
    def _run_recording(self):
        """Run data recording only."""
        logger.info(f"Starting data recording (interval: {self.record_interval}s)")
        
        self.recorder.start_recording(self.clob, interval_seconds=self.record_interval)
        
        while self._running:
            count = self.recorder.get_snapshot_count()
            logger.info(f"Total snapshots recorded: {count}")
            time.sleep(60)
            
    def _run_full(self):
        """Run all features: scanning, monitoring, recording."""
        logger.info("Starting FULL mode - all features enabled")
        
        # Start recording
        self.recorder.start_recording(self.clob, interval_seconds=self.record_interval)
        
        # Start alerts
        self.alerts.start()
        self.alerts.send_info("Bot Started", "Full mode - scanning, alerting, recording")
        
        # Start monitoring
        self._run_monitoring()
        
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signal."""
        logger.info("Shutdown signal received")
        self._running = False
        
    def _shutdown(self):
        """Clean shutdown of all components."""
        logger.info("Shutting down...")
        
        self.recorder.stop_recording()
        self.alerts.stop()
        
        logger.info("Bot stopped")


def main():
    parser = argparse.ArgumentParser(description='Polymarket Arbitrage Bot')
    
    parser.add_argument(
        '--mode', '-m',
        choices=['scan', 'monitor', 'record', 'full'],
        default='scan',
        help='Operating mode'
    )
    
    parser.add_argument(
        '--min-edge', '-e',
        type=float,
        default=0.5,
        help='Minimum edge %% to alert (default: 0.5)'
    )
    
    parser.add_argument(
        '--scan-interval', '-s',
        type=int,
        default=30,
        help='Seconds between scans (default: 30)'
    )
    
    parser.add_argument(
        '--record-interval', '-r',
        type=int,
        default=60,
        help='Seconds between recordings (default: 60)'
    )
    
    args = parser.parse_args()
    
    bot = UnifiedArbBot(
        mode=args.mode,
        min_edge_pct=args.min_edge,
        scan_interval=args.scan_interval,
        record_interval=args.record_interval
    )
    
    bot.run()


if __name__ == '__main__':
    main()
