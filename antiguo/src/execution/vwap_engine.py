from typing import List, Optional, Dict

class VWAPEngine:
    """
    Calculates execution prices based on Order Book depth.
    Crucial for determining if an arbitrage opportunity is actually profitable after slippage.
    """
    
    @staticmethod
    def calculate_buy_vwap(asks: List[List[float]], target_shares: float) -> Optional[float]:
        """
        Calculate average price to BUY 'target_shares' by taking from ASKS.
        Asks should be sorted by price ASCENDING (lowest to highest).
        
        Args:
            asks: List of [price, size].
            target_shares: Amoutn of shares to buy.
            
        Returns:
            VWAP per share, or None if insufficient liquidity.
        """
        if not asks or target_shares <= 0:
            return None
            
        total_cost = 0.0
        remaining = target_shares
        
        # Sort asks by price ASC just in case
        sorted_asks = sorted(asks, key=lambda x: float(x[0]))
        
        for level in sorted_asks:
            price = float(level[0])
            size = float(level[1])
            
            take = min(remaining, size)
            total_cost += take * price
            remaining -= take
            
            if remaining <= 1e-9: # Float tolerance
                break
                
        if remaining > 1e-9:
            return None # Insufficient liquidity to fill full size
            
        return total_cost / target_shares

    @staticmethod
    def calculate_sell_vwap(bids: List[List[float]], target_shares: float) -> Optional[float]:
        """
        Calculate average price to SELL 'target_shares' by hitting BIDS.
        Bids should be sorted by price DESCENDING (highest to lowest).
        """
        if not bids or target_shares <= 0:
            return None
            
        total_revenue = 0.0
        remaining = target_shares
        
        # Sort bids by price DESC
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
            
        return total_revenue / target_shares
