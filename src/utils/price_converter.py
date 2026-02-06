
import logging
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

def convert_poly_to_decimal(poly_price: float) -> float:
    """
    Converts Polymarket probability (0.0 - 1.0) to Betfair Decimal Odds.
    Formula: Odds = 1 / Probability
    """
    if poly_price <= 0:
        return 1000.0 # Cap at 1000
    if poly_price >= 1:
        return 1.01 # Floor at 1.01
        
    odds = 1.0 / poly_price
    # Round to 2 decimal places for standard display, 
    # but for math integrity we might keep more or use Betfair ticks.
    return round(odds, 3)

def apply_betfair_commission(odds: float, commission_rate: float = 0.02) -> float:
    """
    Adjusts BACK odds for Betfair commission on NET winnings.
    Net Odds = 1 + (Odds - 1) * (1 - Commission)
    """
    if odds <= 1.0:
        return odds
    return 1 + (odds - 1) * (1 - commission_rate)

def calculate_ev(poly_prob: float, bf_odds: float, commission: float = 0.02) -> float:
    """
    Calculates Expected Value (EV) comparing Poly probability vs Betfair odds.
    """
    adjusted_bf_odds = apply_betfair_commission(bf_odds, commission)
    # EV = (Prob * Odds) - 1
    ev = (poly_prob * adjusted_bf_odds) - 1
    return ev
