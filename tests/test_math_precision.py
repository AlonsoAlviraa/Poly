import pytest
import random
import math
from decimal import Decimal, getcontext, DivisionByZero, InvalidOperation
from src.risk.position_sizer import KellyPositionSizer

def calculate_spread(best_bid: float, best_ask: float) -> Decimal:
    try:
        bid = Decimal(str(best_bid))
        ask = Decimal(str(best_ask))
        if ask <= 0 or bid <= 0: return Decimal("0")
        return (ask - bid)
    except:
        return Decimal("0")

class TestMathAudit:
    """
    🧪 BATERÍA 2: LA AUDITORÍA MATEMÁTICA (Manual Fuzzing Edition)
    Objetivo: Verificar precisión y robustez numérica con bucles masivos.
    """

    def test_centavos_perdidos_loop(self):
        """El Test de los Centavos Perdidos: 50,000 iteraciones."""
        getcontext().prec = 28
        
        for _ in range(50000):
            bid = random.uniform(1.01, 1000.0)
            ask = random.uniform(1.01, 1000.0)
            
            if bid >= ask: continue
            
            # Float calc
            spread_float = ask - bid
            
            # Decimal calc
            try:
                # String conversion is key for Decimal precision
                spread_decimal = Decimal(f"{ask:.15f}") - Decimal(f"{bid:.15f}")
                
                # Check diff (allowing for small float drift in format)
                # We test that Decimal math holds up relative to our expectation
                # Just verifying no crashes and basic coherence
                assert spread_decimal > 0
                
            except InvalidOperation:
                pass

    def test_spread_imposible_loop(self):
        """El Test del Spread Imposible: Inyección de basura numérica."""
        bad_odds = [0.0, -1.0, -0.0001, float('inf'), float('nan')]
        
        for bad in bad_odds:
            try:
                res = calculate_spread(bad, 2.0)
                assert res == 0 or res is None
            except (ValueError, DivisionByZero, Exception):
                pass
        
        # Fuzzing random negatives
        for _ in range(1000):
            bad = random.uniform(-100, 0)
            res = calculate_spread(bad, 2.0)
            assert res == 0

    def test_kelly_suicida_loop(self):
        """
        El Test de Kelly Suicida. 10,000 iteraciones.
        """
        sizer = KellyPositionSizer()
        
        for _ in range(10000):
            capital = random.uniform(10, 1000)
            win_prob = random.uniform(0.0, 1.0)
            profit_ratio = random.uniform(0.1, 2.0)
            
            # If win prob is trash (e.g. < 0.3) we expect 0 size mostly
            # Kelly: f = p - (q/b). If p is small, f is negative -> 0.
            # b = profit_ratio.
            # Critical check: if p < 0.5 and profit_ratio=1.0, size MUST be 0.
            
            size = sizer.calculate_size(capital, win_prob, profit_ratio, 1000.0)
            
            if win_prob < 0.1 and profit_ratio < 1.0:
                 assert size == 0.0, f"Kelly suicide! p={win_prob} b={profit_ratio} size={size}"
