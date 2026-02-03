from typing import List, Optional
import logging
import os

logger = logging.getLogger(__name__)

class VWAPEngine:
    """
    Calculates execution prices based on Order Book depth.
    Includes 'Aggressive Mode' slippage penalty to ensure execution certainty.
    """
    
    # Aggressive Penalty (Default 0.5% if not set)
    # This acts as a 'buffer' against the infinite liquidity bias.
    SLIPPAGE_PENALTY = float(os.getenv("SLIPPAGE_PROTECTION", 0.005))
    
    @classmethod
    def calculate_buy_vwap(cls, asks: List[List[float]], target_shares: float) -> Optional[float]:
        """
        Calculate average price to BUY 'target_shares' + Penalty.
        """
        if not asks or target_shares <= 0:
            return None
            
        total_cost = 0.0
        remaining = target_shares
        
        # Sort asks by price ASC just in case (cheapest first)
        sorted_asks = sorted(asks, key=lambda x: float(x[0]))
        
        for level in sorted_asks:
            price = float(level[0])
            size = float(level[1])
            
            take = min(remaining, size)
            total_cost += take * price
            remaining -= take
            
            if remaining <= 1e-9:
                break
                
        if remaining > 1e-9:
            return None # Insufficient liquidity
            
        raw_vwap = total_cost / target_shares
        
        # Apply Aggressive Penalty (Higher Buy Price)
        final_price = raw_vwap * (1.0 + cls.SLIPPAGE_PENALTY)
        return final_price

    @classmethod
    def calculate_sell_vwap(cls, bids: List[List[float]], target_shares: float) -> Optional[float]:
        """
        Calculate average price to SELL 'target_shares' - Penalty.
        """
        if not bids or target_shares <= 0:
            return None
            
        total_revenue = 0.0
        remaining = target_shares
        
        # Sort bids by price DESC (highest first)
        sorted_bids = sorted(bids, key=lambda x: float(x[0]), reverse=True)
        
        for level in sorted_bids:
            price = float(level[0])
            size = float(level[1])
            
            take = min(remaining, size)
            total_revenue += take * price
            remaining -= take
            
            if remaining <= 1e-9:
                break
                
        if remaining > 1e-9:
            return None
            
        raw_vwap = total_revenue / target_shares
        
        # Apply Aggressive Penalty (Lower Sell Price)
        final_price = raw_vwap * (1.0 - cls.SLIPPAGE_PENALTY)
        return final_price
