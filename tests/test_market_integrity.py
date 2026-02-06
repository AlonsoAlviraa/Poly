
import pytest
from src.arbitrage.market_normalizer import MarketStandardizer
from src.arbitrage.entity_resolver_logic import static_matcher
from src.utils.price_converter import convert_poly_to_decimal, calculate_ev

def test_draw_matching():
    # Poly Draw question
    poly_q = "Will the match end in a draw?"
    poly_o = "Yes"
    
    # Betfair Match Odds Runner
    bf_runner = "The Draw"
    
    assert MarketStandardizer.is_compatible(poly_q, poly_o, bf_runner) is True
    
    # Should NOT match with a team
    assert MarketStandardizer.is_compatible(poly_q, poly_o, "Manchester City") is False

def test_over_under_granularity():
    # Case: Poly Over 2.5 vs BF Over 2.5 (MATCH)
    assert MarketStandardizer.is_compatible(
        "Over 2.5 goals?", "Yes", "Over 2.5 Goals"
    ) is True
    
    # Case: Poly Over 2.5 vs BF Over 1.5 (FAIL) - DIFFERENT LINES
    assert MarketStandardizer.is_compatible(
        "Over 2.5 goals?", "Yes", "Over 1.5 Goals"
    ) is False
    
    # Case: Poly Under 178.5 (NBA) vs BF Under 178.5
    assert MarketStandardizer.is_compatible(
        "Under 178.5 points?", "Yes", "Under 178.5"
    ) is True

def test_player_prop_resolution():
    # "C. Alcaraz" vs "Carlos Alcaraz Garfia"
    # The new normalize_player_name removes "C. "
    # and static_matcher uses token set ratio.
    assert static_matcher("C. Alcaraz", "Carlos Alcaraz Garfia", "tennis") == "MATCH"
    
    # "Sinner, Jannik" vs "Jannik Sinner"
    assert static_matcher("Sinner, Jannik", "Jannik Sinner", "tennis") == "MATCH"

def test_math_integrity():
    # Poly 0.60 should be ~1.666 decimal
    price = 0.60
    decimal = convert_poly_to_decimal(price)
    assert 1.66 <= decimal <= 1.67
    
    # EV Calculation with 2% commission
    # Poly 0.60 vs BF 1.75
    # Adjusted BF Odds = 1 + (0.75 * 0.98) = 1 + 0.735 = 1.735
    # EV = (0.6 * 1.735) - 1 = 1.041 - 1 = 0.041 (4.1% profit)
    ev = calculate_ev(0.60, 1.75, commission=0.02)
    assert ev > 0.04
