import logging
from decimal import Decimal, InvalidOperation

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
        try:
            capital_d = Decimal(str(capital))
            win_prob_d = Decimal(str(win_prob))
            profit_ratio_d = Decimal(str(profit_ratio))
            liquidity_limit_d = Decimal(str(liquidity_limit))
        except (InvalidOperation, ValueError):
            logger.warning("Invalid input for Kelly sizing; returning 0.")
            return 0.0

        if win_prob_d <= 0 or win_prob_d >= 1:
            logger.warning("win_prob out of bounds for Kelly sizing; returning 0.")
            return 0.0

        if profit_ratio_d <= 0:
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
        
        b = profit_ratio_d  # Assuming trade returns (1+b) * stake.
        p = win_prob_d
        q = Decimal("1") - p
        
        f_star = (b * p - q) / b
        
        if f_star <= 0:
            return 0.0
            
        # Apply Fraction
        safe_f = f_star * Decimal(str(self.kelly_fraction))
        
        # Calculate Amount
        wager = capital_d * safe_f
        
        # Cap at Liquidity
        final_size = min(wager, liquidity_limit_d)

        return float(final_size)
