"""
Historical Data Recording and Backtesting System.
Records live market data and allows replay for strategy testing.

Features:
1. Live data recording (prices, orderbooks, events)
2. SQLite storage for efficient queries
3. Replay engine for backtesting
4. Performance metrics calculation
"""

import sqlite3
import json
import time
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Generator, Callable
from pathlib import Path
import threading
from queue import Queue

logger = logging.getLogger(__name__)


@dataclass
class MarketSnapshot:
    """Point-in-time market data."""
    timestamp: str
    condition_id: str
    token_id: str
    outcome: str
    mid_price: float
    best_bid: float
    best_ask: float
    bid_depth: float  # Total bid liquidity
    ask_depth: float  # Total ask liquidity
    spread: float
    

@dataclass
class TradeRecord:
    """Simulated or real trade record."""
    timestamp: str
    token_id: str
    side: str  # 'buy' or 'sell'
    price: float
    size: float
    pnl: float
    strategy: str


class DataRecorder:
    """
    Records live market data to SQLite database.
    Designed to run continuously in background.
    """
    
    def __init__(self, db_path: str = "market_data.db"):
        self.db_path = db_path
        self._init_db()
        self._queue: Queue = Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Market snapshots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                condition_id TEXT NOT NULL,
                token_id TEXT NOT NULL,
                outcome TEXT,
                mid_price REAL,
                best_bid REAL,
                best_ask REAL,
                bid_depth REAL,
                ask_depth REAL,
                spread REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Index for fast queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_time 
            ON snapshots(timestamp, token_id)
        """)
        
        # Events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_id TEXT NOT NULL,
                event_title TEXT,
                n_markets INTEGER,
                data JSON
            )
        """)
        
        # Trades table for backtest results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                token_id TEXT NOT NULL,
                side TEXT,
                price REAL,
                size REAL,
                pnl REAL,
                strategy TEXT,
                backtest_id TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {self.db_path}")
        
    def start_recording(self, clob_client, interval_seconds: int = 60):
        """
        Start background recording of market data.
        
        Args:
            clob_client: CLOB executor for fetching data
            interval_seconds: How often to snapshot (default 60s)
        """
        if self._running:
            logger.warning("Recorder already running")
            return
            
        self._running = True
        self._thread = threading.Thread(
            target=self._recording_loop,
            args=(clob_client, interval_seconds),
            daemon=True
        )
        self._thread.start()
        logger.info(f"Data recording started (interval: {interval_seconds}s)")
        
    def stop_recording(self):
        """Stop the recording thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Data recording stopped")
        
    def _recording_loop(self, clob_client, interval: int):
        """Main recording loop."""
        while self._running:
            try:
                self._record_snapshot(clob_client)
            except Exception as e:
                logger.error(f"Recording error: {e}")
            time.sleep(interval)
            
    def _record_snapshot(self, clob_client):
        """Record current market state."""
        timestamp = datetime.utcnow().isoformat()
        snapshots = []
        
        try:
            # Get sampling markets
            resp = clob_client.client.get_sampling_simplified_markets(next_cursor='')
            markets = resp.get('data', []) if isinstance(resp, dict) else resp
            
            for market in markets[:100]:  # Limit to 100 markets
                if not market.get('accepting_orders'):
                    continue
                    
                condition_id = market.get('condition_id', '')
                tokens = market.get('tokens', [])
                
                for token in tokens[:2]:  # Yes/No
                    token_id = token.get('token_id')
                    if not token_id:
                        continue
                    
                    try:
                        # Get orderbook
                        book = clob_client.get_order_book(token_id)
                        
                        if hasattr(book, 'bids'):
                            bids = book.bids if book.bids else []
                            asks = book.asks if book.asks else []
                        else:
                            bids = book.get('bids', [])
                            asks = book.get('asks', [])
                        
                        if not bids or not asks:
                            continue
                        
                        # Extract prices
                        if hasattr(bids[0], 'price'):
                            best_bid = float(bids[0].price)
                            best_ask = float(asks[0].price)
                            bid_depth = sum(float(b.size) for b in bids[:5])
                            ask_depth = sum(float(a.size) for a in asks[:5])
                        else:
                            best_bid = float(bids[0].get('price', 0))
                            best_ask = float(asks[0].get('price', 0))
                            bid_depth = sum(float(b.get('size', 0)) for b in bids[:5])
                            ask_depth = sum(float(a.get('size', 0)) for a in asks[:5])
                        
                        mid_price = (best_bid + best_ask) / 2
                        spread = best_ask - best_bid
                        
                        snapshot = MarketSnapshot(
                            timestamp=timestamp,
                            condition_id=condition_id,
                            token_id=token_id,
                            outcome=token.get('outcome', ''),
                            mid_price=mid_price,
                            best_bid=best_bid,
                            best_ask=best_ask,
                            bid_depth=bid_depth,
                            ask_depth=ask_depth,
                            spread=spread
                        )
                        snapshots.append(snapshot)
                        
                    except Exception as e:
                        logger.debug(f"Token {token_id} snapshot error: {e}")
                        
        except Exception as e:
            logger.error(f"Snapshot fetch error: {e}")
            
        # Bulk insert
        if snapshots:
            self._insert_snapshots(snapshots)
            logger.info(f"Recorded {len(snapshots)} market snapshots")
            
    def _insert_snapshots(self, snapshots: List[MarketSnapshot]):
        """Bulk insert snapshots to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.executemany("""
            INSERT INTO snapshots 
            (timestamp, condition_id, token_id, outcome, mid_price, 
             best_bid, best_ask, bid_depth, ask_depth, spread)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (s.timestamp, s.condition_id, s.token_id, s.outcome,
             s.mid_price, s.best_bid, s.best_ask, s.bid_depth, 
             s.ask_depth, s.spread)
            for s in snapshots
        ])
        
        conn.commit()
        conn.close()
        
    def get_snapshot_count(self) -> int:
        """Get total number of recorded snapshots."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM snapshots")
        count = cursor.fetchone()[0]
        conn.close()
        return count


class BacktestEngine:
    """
    Replay historical data to test strategies.
    """
    
    def __init__(self, db_path: str = "market_data.db"):
        self.db_path = db_path
        self.trades: List[TradeRecord] = []
        self.backtest_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
    def get_historical_data(self,
                           start_time: Optional[str] = None,
                           end_time: Optional[str] = None,
                           token_ids: Optional[List[str]] = None) -> Generator[Dict, None, None]:
        """
        Stream historical snapshots for backtesting.
        
        Args:
            start_time: ISO format start time
            end_time: ISO format end time
            token_ids: Filter to specific tokens
            
        Yields:
            Dict with snapshot data
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM snapshots WHERE 1=1"
        params = []
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
            
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
            
        if token_ids:
            placeholders = ','.join('?' * len(token_ids))
            query += f" AND token_id IN ({placeholders})"
            params.extend(token_ids)
            
        query += " ORDER BY timestamp ASC"
        
        cursor.execute(query, params)
        
        for row in cursor:
            yield dict(row)
            
        conn.close()
        
    def run_backtest(self,
                     strategy_fn: Callable[[Dict], Optional[Dict]],
                     start_time: Optional[str] = None,
                     end_time: Optional[str] = None,
                     initial_capital: float = 1000.0) -> Dict:
        """
        Run a backtest with a given strategy.
        
        Args:
            strategy_fn: Function(snapshot) -> Optional[trade_signal]
                         Returns dict with 'side', 'size', 'price' or None
            start_time: Backtest start
            end_time: Backtest end
            initial_capital: Starting capital
            
        Returns:
            Performance metrics dict
        """
        self.trades = []
        capital = initial_capital
        positions: Dict[str, float] = {}  # token_id -> size
        
        # Group snapshots by timestamp for point-in-time view
        current_time = None
        batch = []
        
        for snapshot in self.get_historical_data(start_time, end_time):
            snap_time = snapshot['timestamp']
            
            if current_time and snap_time != current_time:
                # Process previous batch
                for snap in batch:
                    signal = strategy_fn(snap)
                    if signal:
                        trade = self._execute_backtest_trade(
                            snap, signal, capital, positions
                        )
                        if trade:
                            self.trades.append(trade)
                            capital += trade.pnl
                            
                batch = []
                
            current_time = snap_time
            batch.append(snapshot)
            
        # Calculate metrics
        metrics = self._calculate_metrics(initial_capital, capital)
        
        # Save trades
        self._save_trades()
        
        return metrics
        
    def _execute_backtest_trade(self,
                                snapshot: Dict,
                                signal: Dict,
                                capital: float,
                                positions: Dict) -> Optional[TradeRecord]:
        """Execute a simulated trade."""
        token_id = snapshot['token_id']
        side = signal.get('side', 'buy')
        size = min(signal.get('size', 10), capital * 0.1)  # Max 10% of capital
        
        if side == 'buy':
            price = snapshot['best_ask']  # Pay the ask
            cost = price * size
            if cost > capital:
                return None
            positions[token_id] = positions.get(token_id, 0) + size
            pnl = -cost
        else:
            price = snapshot['best_bid']  # Get the bid
            if positions.get(token_id, 0) < size:
                size = positions.get(token_id, 0)
            if size <= 0:
                return None
            positions[token_id] = positions.get(token_id, 0) - size
            pnl = price * size
            
        return TradeRecord(
            timestamp=snapshot['timestamp'],
            token_id=token_id,
            side=side,
            price=price,
            size=size,
            pnl=pnl,
            strategy=signal.get('strategy', 'unknown')
        )
        
    def _calculate_metrics(self, initial_capital: float, final_capital: float) -> Dict:
        """Calculate backtest performance metrics."""
        total_pnl = final_capital - initial_capital
        n_trades = len(self.trades)
        
        if n_trades == 0:
            return {
                'total_pnl': 0,
                'return_pct': 0,
                'n_trades': 0,
                'win_rate': 0,
                'avg_trade_pnl': 0,
                'sharpe_ratio': 0
            }
        
        winning_trades = [t for t in self.trades if t.pnl > 0]
        win_rate = len(winning_trades) / n_trades if n_trades > 0 else 0
        
        pnls = [t.pnl for t in self.trades]
        avg_pnl = sum(pnls) / len(pnls)
        
        # Simple Sharpe approximation
        import statistics
        if len(pnls) > 1:
            std_pnl = statistics.stdev(pnls)
            sharpe = (avg_pnl / std_pnl) if std_pnl > 0 else 0
        else:
            sharpe = 0
        
        return {
            'total_pnl': total_pnl,
            'return_pct': (total_pnl / initial_capital) * 100,
            'n_trades': n_trades,
            'win_rate': win_rate * 100,
            'avg_trade_pnl': avg_pnl,
            'sharpe_ratio': sharpe,
            'final_capital': final_capital
        }
        
    def _save_trades(self):
        """Save backtest trades to database."""
        if not self.trades:
            return
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.executemany("""
            INSERT INTO trades 
            (timestamp, token_id, side, price, size, pnl, strategy, backtest_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (t.timestamp, t.token_id, t.side, t.price, t.size, 
             t.pnl, t.strategy, self.backtest_id)
            for t in self.trades
        ])
        
        conn.commit()
        conn.close()


def demo_backtest():
    """Demo the backtesting system."""
    print("=" * 70)
    print("BACKTESTING SYSTEM DEMO")
    print("=" * 70)
    
    # Create sample strategy
    def simple_arb_strategy(snapshot: Dict) -> Optional[Dict]:
        """Buy if spread is unusually large."""
        spread = snapshot.get('spread', 0)
        mid = snapshot.get('mid_price', 0.5)
        
        # If spread > 5% of mid, potential arb
        if mid > 0 and spread / mid > 0.05:
            return {
                'side': 'buy',
                'size': 10,
                'strategy': 'spread_arb'
            }
        return None
    
    # Run backtest
    engine = BacktestEngine()
    
    # Check if we have data
    recorder = DataRecorder()
    count = recorder.get_snapshot_count()
    
    if count == 0:
        print("\n    No historical data available.")
        print("    Start recording first with: recorder.start_recording(clob_client)")
        print("\n    Example:")
        print("    >>> from src.data.backtesting import DataRecorder")
        print("    >>> recorder = DataRecorder()")
        print("    >>> recorder.start_recording(clob_client, interval_seconds=60)")
    else:
        print(f"\n    Found {count} snapshots in database")
        
        metrics = engine.run_backtest(
            strategy_fn=simple_arb_strategy,
            initial_capital=1000.0
        )
        
        print("\n    BACKTEST RESULTS:")
        print(f"    Total P&L: ${metrics['total_pnl']:.2f}")
        print(f"    Return: {metrics['return_pct']:.2f}%")
        print(f"    Trades: {metrics['n_trades']}")
        print(f"    Win Rate: {metrics['win_rate']:.1f}%")
        print(f"    Sharpe: {metrics['sharpe_ratio']:.2f}")
    
    print("\n" + "=" * 70)


if __name__ == '__main__':
    demo_backtest()
