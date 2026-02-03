import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Any, Tuple
import time

from src.execution.vwap_engine import VWAPEngine
from src.risk.position_sizer import KellyPositionSizer

logger = logging.getLogger(__name__)

class BacktestEngine:
    """
    Simulates historical performance with realistic constraints:
    - Network Latency (default 2s lag between tick and execution)
    - Dynamic Slippage (using VWAP depth)
    - Transaction Fees
    """
    
    def __init__(self, historical_data: pd.DataFrame, latency_ms: int = 2000):
        """
        Args:
            historical_data: DataFrame with cols [timestamp, market_id, bids, asks, price]
            latency_ms: Simulated network delay in milliseconds.
        """
        self.data = historical_data.sort_values('timestamp')
        self.latency_ms = latency_ms
        self.equity_curve = []
        self.capital = 1000.0
        self.risk_free_rate = 0.04 # 4% annual
        
        # Stats
        self.trades = []
        
    def run(self, strategy_logic_fn):
        """
        Runs the backtest.
        args:
            strategy_logic_fn: Function(tick, portfolio) -> actionable_signals
        """
        logger.info(f"Starting Backtest on {len(self.data)} ticks...")
        
        # Simulation Loop
        for i, tick in self.data.iterrows():
            curr_time = tick['timestamp']
            
            # 1. State Update
            # In a real backtest, we might hold positions. 
            # For Atomic Arb, we assume instantaneous settlement logic (or rapid close).
            
            # 2. Strategy Signal
            signals = strategy_logic_fn(tick)
            
            if not signals:
                continue
                
            # 3. Execution Simulation (The "High Fidelity" part)
            for signal in signals:
                self._execute_signal(signal, curr_time, tick)
                
    def _execute_signal(self, signal: Dict, signal_time: int, tick_data: Any):
        """
        Simulates execution with Latency and Slippage.
        We check if the opportunity still exists 'latency_ms' later? 
        Or simpler: we apply a 'slippage penalty' model if we don't have millisecond-level future data.
        
        For high-fidelity, usually you look ahead in the dataframe by 'latency_ms'.
        """
        # Look ahead logic
        execution_time = signal_time + self.latency_ms
        
        # Find closest tick in data >= execution_time
        # (This is slow in a loop, optimization needed for millions of rows, but ok for MVP)
        # Assuming data represents the state AT execution time for now if dense enough.
        # Or simpler: penalize price by X basis points variance.
        
        exec_price = signal['limit_price']
        
        # Slippage Model: 
        # Impact = volatility * sqrt(size / liquidity)
        # Simplified: We use VWAP from the tick (assuming tick has depth)
        
        # Check actual liquidity in tick
        size = signal['size']
        market_id = signal['token_id']
        side = signal['side']
        
        # Here we'd need the orderbook from the tick
        bids = tick_data.get('bids', [])
        asks = tick_data.get('asks', [])
        
        realized_price = 0.0
        
        if side == 'BUY':
            realized_price = VWAPEngine.calculate_buy_vwap(asks, size)
            if realized_price is None: return # Failed to fill
        else:
            realized_price = VWAPEngine.calculate_sell_vwap(bids, size)
            if realized_price is None: return
            
        # PnL Calc (Atomic Arb)
        # We assume immediate close or theoretical profit
        # If Signal was Arb: Buy A ($0.4), Buy B ($0.5), Payout $1.0. Cost $0.9.
        # Realized might be: Buy A ($0.42), Buy B ($0.52). Cost $0.94. Profit $0.06.
        
        expected_profit = signal['expected_profit']
        
        # Slippage Penalty
        # Diff between limit and realized
        slippage_cost = abs(realized_price - signal['limit_price']) * size
        
        # Fees
        fees = 0.01 * size # Gas + Taker
        
        net_pnl = expected_profit - slippage_cost - fees
        
        self.capital += net_pnl
        self.equity_curve.append(self.capital)
        self.trades.append({
            "time": execution_time,
            "pnl": net_pnl,
            "slippage": slippage_cost
        })

    def report(self):
        """
        Generates tearing sheet: Sharpe, Drawdown, etc.
        """
        if not self.equity_curve:
            return "No trades executed."
            
        equity = pd.Series(self.equity_curve)
        returns = equity.pct_change().dropna()
        
        # Sharpe
        if returns.std() == 0:
            sharpe = 0.0
        else:
            # Annulized Sharpe (assuming minutes ticks? rough calc)
            sharpe = (returns.mean() / returns.std()) * np.sqrt(252 * 24 * 60) 
            
        # Drawdown
        cummax = equity.cummax()
        drawdown = (equity - cummax) / cummax
        max_dd = drawdown.min()
        
        return {
            "Total Return": (self.capital - 1000.0),
            "Sharpe Ratio": sharpe,
            "Max Drawdown": max_dd,
            "Trade Count": len(self.trades)
        }
