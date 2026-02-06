
import re
import logging
from typing import Optional, Tuple, Dict

logger = logging.getLogger(__name__)

class MarketStandardizer:
    """
    Ensures market granularity. Prevents matching different lines (2.5 vs 3.5)
    and strictly identifies Draw markets.
    """
    
    # Regex for Totals (Over/Under)
    # Matches "Over 2.5", "Under 178.5", "O/U 3.5"
    TOTALS_REGEX = re.compile(r"(?i)(over|under|o/u)\s*(\d+(?:\.\d+)?)")
    
    # Regex for Draw
    DRAW_REGEX = re.compile(r"(?i)\b(draw|tie|empate)\b")

    @classmethod
    def get_market_type(cls, question: str) -> str:
        """Categorizes market: MATCH_WINNER, TOTALS, DRAW, or UNKNOWN."""
        q_low = question.lower()
        
        if cls.DRAW_REGEX.search(q_low):
            return "DRAW"
        
        if cls.TOTALS_REGEX.search(q_low):
            return "TOTALS"
            
        # Common winner patterns
        if any(w in q_low for w in ["win", "victory", "to beat", "champion"]):
            return "MATCH_WINNER"
            
        return "UNKNOWN"

    @classmethod
    def extract_totals_spec(cls, text: str) -> Optional[Tuple[str, float]]:
        """
        Extracts (Side, Line) from text.
        Example: "Over 2.5 goals" -> ("OVER", 2.5)
        """
        match = cls.TOTALS_REGEX.search(text)
        if not match:
            return None
            
        side_raw = match.group(1).upper()
        line = float(match.group(2).replace(",", "."))
        
        side = "OVER" if "OVER" in side_raw or "O" == side_raw else "UNDER"
        return side, line

    @classmethod
    def is_compatible(cls, poly_q: str, poly_o: str, bf_market_name: str) -> bool:
        """
        Strict validation between Poly and Betfair target names.
        """
        poly_type = cls.get_market_type(poly_q)
        
        # 1. TOTALS ENFORCEMENT
        if poly_type == "TOTALS" or "over" in bf_market_name.lower() or "under" in bf_market_name.lower():
            poly_spec = cls.extract_totals_spec(poly_q) or cls.extract_totals_spec(poly_o)
            bf_spec = cls.extract_totals_spec(bf_market_name)
            
            if not poly_spec or not bf_spec:
                return False
                
            # Lines must match EXACTLY (e.g., 2.5 goals vs 2.5 goals)
            return poly_spec[1] == bf_spec[1]

        # 2. DRAW ENFORCEMENT
        if poly_type == "DRAW":
            # If Poly is asking about the Draw, it ONLY matches "The Draw" runner in Match Odds
            # or a specific Draw market.
            return "draw" in bf_market_name.lower() or "tie" in bf_market_name.lower()

        return True
