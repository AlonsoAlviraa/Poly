import logging
import numpy as np

logger = logging.getLogger(__name__)

class KellyPositionSizer:
    """
    Calculates optimal trade size using Kelly Criterion.
    f* = (bp - q) / b
    where:
    b = net odds received (b to 1)
    p = probability of winning
    q = probability of losing (1-p)
    """
    
    def __init__(self, fraction: float = 0.25):
        # Full Kelly is aggressive. We use Fractional Kelly (e.g. Quarter Kelly)
        self.kelly_fraction = fraction

    def calculate_size(self, capital: float, win_prob: float, profit_ratio: float, liquidity_limit: float) -> float:
        """
        Args:
            capital: Available trading capital.
            win_prob: Estimated probability of success (0.0 to 1.0).
            profit_ratio: Net profit percent (e.g. 0.05 for 5% return). effectively 'b'.
            liquidity_limit: Max size order book can take.
            
        Returns:
            Amount to wager (USD).
        """
        if profit_ratio <= 0:
            return 0.0
            
        # Kelly Formula
        # f = p - (1-p)/b
        # Let's say we buy YES at 0.60. Return is 1.00. Odds b = (1 - 0.6)/0.6 = 0.666
        # If we think Prob is 0.70.
        # f = 0.70 - (0.30 / 0.666) = 0.7 - 0.45 = 0.25.
        # Bet 25% of bankroll.
        
        # In Arbitrage, p is technically 1.0 (if atomic).
        # If p ~ 1.0, f ~ 1.0. We bet everything!
        # But we use fractional kelly for execution risk (smart contract bug, etc).
        
        b = profit_ratio # Assuming trade returns (1+b) * stake.
        p = win_prob
        q = 1 - p
        
        f_star = (b * p - q) / b
        
        if f_star <= 0:
            return 0.0
            
        # Apply Fraction
        safe_f = f_star * self.kelly_fraction
        
        # Calculate Amount
        wager = capital * safe_f
        
        # Cap at Liquidity
        final_size = min(wager, liquidity_limit)
        
        return final_size
