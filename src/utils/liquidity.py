
from typing import List, Dict

def select_best_market(markets: List[Dict]) -> Dict:
    """
    Selects the best market based on liquidity depth.
    """
    if not markets:
        return None
        
    # Sort by 'volume' or 'liquidity' if available, else first
    sorted_markets = sorted(markets, key=lambda m: m.get('volume', 0), reverse=True)
    return sorted_markets[0]
