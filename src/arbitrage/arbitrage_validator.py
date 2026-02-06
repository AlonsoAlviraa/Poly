
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class ArbResult:
    is_opportunity: bool
    roi_percent: float
    direction: str
    poly_price: float
    exchange_price: float
    reason: str = ""

class ArbitrageValidator:
    """
    Centralized validation engine for Arbitrage opportunities.
    Enforces Strict Semantic Matching, Fee-Adjusted ROI, and Liquidity thresholds.
    """

    # --- 1. SEMANTIC STRUCTURAL PARSER (Deep Architecture) ---
    @dataclass
    class MarketStructure:
        scope: str       # 'full', 'h1', 'h2', 'q1', 'set1'
        market_type: str # 'moneyline', 'spread', 'total', 'player_prop'
        subtype: str     # 'anytime_td', 'first_td', 'assists', 'points'
        entity: str      # 'player', 'team', 'match'

    @staticmethod
    def parse_market_structure(text: str) -> 'ArbitrageValidator.MarketStructure':
        t = text.lower()
        
        # 1. Detect Scope
        scope = 'full'
        if '1h' in t or '1st half' in t or 'first half' in t: scope = 'h1'
        elif '2h' in t or '2nd half' in t: scope = 'h2'
        elif 'q1' in t or '1st quarter' in t: scope = 'q1'
        elif 'set 1' in t: scope = 'set1'
        
        # 2. Detect Type & Subtype
        m_type = 'moneyline' # default
        subtype = 'main'
        entity = 'match'
        
        # Props
        if 'touchdown' in t or 'td' in t:
            m_type = 'player_prop'
            entity = 'player'
            if 'first' in t: subtype = 'first_td'
            elif 'anytime' in t: subtype = 'anytime_td'
            else: subtype = 'anytime_td' # Default assumption
        elif 'rebound' in t: 
            m_type = 'player_prop'; subtype = 'rebounds'; entity='player'
        elif 'assist' in t: 
            m_type = 'player_prop'; subtype = 'assists'; entity='player'
        elif 'point' in t: 
            m_type = 'player_prop'; subtype = 'points'; entity='player'
            
        # Lines
        elif 'spread' in t or 'handicap' in t: m_type = 'spread'
        elif 'total' in t or 'over' in t or 'under' in t: m_type = 'total'
        
        return ArbitrageValidator.MarketStructure(scope, m_type, subtype, entity)

    @staticmethod
    def is_semantically_compatible(poly_title: str, exch_market_name: str, exch_category: str = "") -> bool:
        """
        Deep Semantic Validation using Structural Parsing.
        """
        # 1. Parse Structures
        p_struct = ArbitrageValidator.parse_market_structure(poly_title)
        e_struct = ArbitrageValidator.parse_market_structure(exch_market_name)
        
        # 2. Strict Scope Matching (e.g. H1 vs Full Game)
        if p_struct.scope != e_struct.scope:
            return False
            
        # 3. Strict Type Matching (e.g. Prop vs Moneyline)
        if p_struct.market_type != e_struct.market_type:
            # Exception: 'MATCH_ODDS' (Exch) vs 'Winner' (Poly) -> handled by m_type 'moneyline' defaults
            # But if one is 'player_prop' and other is 'moneyline', FAIL.
            return False
            
        # 4. Strict Subtype for Props (First TD vs Anytime TD)
        if p_struct.market_type == 'player_prop':
            if p_struct.subtype != e_struct.subtype:
                return False
                
        # 5. Fallback to Keyword Checks (Legacy Safety)
        # ... (Keep existing lightweight checks if needed, or fully trust parser)
        # For now, trust parser for major mismatches.
        
        return True

    # --- 1.5 STRUCTURAL VALIDATION (Sport-Aware) ---
    @staticmethod
    def check_time_window(poly_time: datetime, exch_time: datetime, max_hours: float = 12.0) -> bool:
        """
        Ensure events happen roughly at the same time (blocks 'Tournament Winner' vs 'Match Winner').
        """
        if not poly_time or not exch_time:
            return True # Cannot validate, soft pass
            
        diff_hours = abs((poly_time - exch_time).total_seconds()) / 3600
        return diff_hours <= max_hours

    @staticmethod
    def validate_market_structure(poly_type: str, exch_runners: int, sport_id: str) -> bool:
        """
        Verify Runner Count based on Sport ID to distinguish DNB vs Winner.
        
        Args:
            poly_type: 'WINNER', 'TOTAL', 'HANDICAP' (simplified)
            exch_runners: Number of runners in Exchange market
            sport_id: Betfair Sport ID ('1'=Soccer, '2'=Tennis, '7522'=Basket)
        """
        # Normalize Sport ID
        sid = str(sport_id)
        
        if poly_type == 'WINNER':
            # SOCCER (ID 1)
            # Winner = 1X2 (3 runners)
            # DNB = 2 runners -> If we want Winner, we reject DNB
            if sid == '1':
                if exch_runners == 2:
                    return False # Reject DNB when looking for Match Winner (1x2)
                if exch_runners == 3:
                    return True
                    
            # TENNIS (ID 2) / BASKETBALL (ID 7522)
            # Winner = Moneyline (2 runners)
            # No Draw usually.
            elif sid in ['2', '7522']:
                if exch_runners == 2:
                    return True # Valid Moneyline
                # If 3 (Euro Basket 1X2), it might be valid comparison but usually Poly NBA is 2-way (Moneyline).
                # Allowing 2 is the critical fix requested.
                
        # For other types (Handicap/Total), usually 2 runners (Over/Under).
        if poly_type in ['TOTAL', 'HANDICAP']:
            if exch_runners == 2:
                return True
                
        return True # Default pass if unsure

    # --- 2. FINANCIAL CALCULATOR ---
    @staticmethod
    def calculate_roi(poly_ask: float, exch_odds: float, fee_rate: float = 0.0) -> ArbResult:
        """
        Calculate Fee-Adjusted ROI.
        Formula: ROI = (1.0 - (PolyAsk + 1/(ExchOdds * (1-Fee)))) * 100
        """
        if poly_ask <= 0 or exch_odds <= 1.0:
            return ArbResult(False, 0.0, "", 0, 0, "Invalid Prices")

        # 1. Effective Pricing Policy
        # To hedge A (Poly Back) we must either Back "Not A" or Lay A on BF.
        # Implied Price of a Lay position at Odds O with Commission C:
        # Price_Net = 1 / (1 + (exch_odds - 1) * (1 - fee_rate))
        
        net_odds = 1 + (exch_odds - 1) * (1 - fee_rate)
        if net_odds <= 1.0:
             return ArbResult(False, 0.0, "", 0, 0, "Odds too low for arb")
             
        implied_prob_exch = 1 / net_odds
        
        total_cost = poly_ask + implied_prob_exch
        roi = (1.0 / total_cost - 1.0) * 100
        
        if roi > 0:
            return ArbResult(True, roi, "Buy Poly / Lay Exch", poly_ask, exch_odds)
        else:
            return ArbResult(False, roi, "No Arb", poly_ask, exch_odds)
        
        # NOTE: This ROI is 'Arbitrage ROI' (profit per unit of capital required to cover both outcomes).

    # --- 3. LIQUIDITY CHECK ---
    @staticmethod
    def check_liquidity(poly_liquidity: float, exch_liquidity: float, min_threshold: float = 10.0) -> bool:
        """
        Ensure executable volume meets threshold.
        """
        max_executable = min(poly_liquidity, exch_liquidity)
        return max_executable >= min_threshold

    # --- 4. QUALITY GUARDIANS (Circuit Breakers) ---
    @staticmethod
    def check_price_consistency(poly_price: float, exch_price_implied: float, max_diff: float = 0.20) -> bool:
        """
        Guard against matching unrelated markets by checking implied probability divergence.
        
        Args:
            poly_price: Implied Prob of Outcome on Poly (0.0 - 1.0)
            exch_price_implied: Implied Prob of Equivalent on Exchange (e.g. 1/DecimalOdds)
            max_diff: Absolute difference allowed (default 20%).
            
        Returns:
            True if prices are reasonably consistent. False if divergent (SUSPICIOUS).
            
        Example:
            Poly 'Win' = 0.50 (Even)
            SX 'Touchdown' = 0.25 (Odds 4.0)
            Diff = 0.25 (> 0.20) -> FALSE. Likely bad match.
        """
        diff = abs(poly_price - exch_price_implied)
        if diff > max_diff:
            # logger.warning(f"[Guard] High Price Divergence: {diff:.2f} (Poly: {poly_price:.2f}, Exch: {exch_price_implied:.2f})")
            return False
        return True
