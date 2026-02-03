
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class MarketMappingResult:
    """Result of mapping a Polymarket outcome to a Betfair instruction."""
    success: bool
    side: str = ""           # 'BACK' or 'LAY'
    selection_name: str = "" # Canonical entity name
    market_type: str = ""    # 'MATCH_ODDS', 'OVER_UNDER', etc.
    explanation: str = ""

class OutcomeMapper:
    """
    Translates Polymarket question semantics into Betfair market structures.
    
    Example:
    Poly: "Will Alcaraz win?" + Outcome: "Yes" -> BF: Match Odds, Side: BACK, Runner: Alcaraz
    Poly: "Will Alcaraz win?" + Outcome: "No"  -> BF: Match Odds, Side: LAY, Runner: Alcaraz
    """
    
    def __init__(self):
        # Keywords that indicate a "Winner" market
        self.winner_indicators = ["win", "winner", "to beat", "victory", "champion"]
        
    def map_outcome(self, 
                    poly_question: str, 
                    poly_outcome: str, 
                    canonical_entity: str) -> MarketMappingResult:
        """
        Maps a Polymarket outcome to a Betfair instruction.
        
        Args:
            poly_question: The question text (e.g. "Will Alcaraz win the French Open?")
            poly_outcome: "Yes" or "No"
            canonical_entity: The resolved entity name (e.g. "Carlos Alcaraz")
        """
        q_lower = poly_question.lower()
        outcome_lower = poly_outcome.lower()
        
        # 1. Detect Intent: Match Winner
        is_winner_market = any(ind in q_lower for ind in self.winner_indicators)
        
        if is_winner_market:
            # Polymarket: "Will [X] win?"
            # Outcome: "Yes" -> BACK [X] on Betfair Match Odds
            # Outcome: "No"  -> LAY [X] on Betfair Match Odds
            
            if outcome_lower == "yes":
                return MarketMappingResult(
                    success=True,
                    side="BACK",
                    selection_name=canonical_entity,
                    market_type="MATCH_ODDS",
                    explanation=f"Mapped 'Yes' to BACK {canonical_entity}"
                )
            elif outcome_lower == "no":
                return MarketMappingResult(
                    success=True,
                    side="LAY",
                    selection_name=canonical_entity,
                    market_type="MATCH_ODDS",
                    explanation=f"Mapped 'No' to LAY {canonical_entity}"
                )
        
        # 2. Prevent False Mappings for unknown structures
        return MarketMappingResult(
            success=False,
            explanation=f"Unknown market intent for question: {poly_question}"
        )

    def validate_sport_viability(self, category: str, poly_tags: list) -> bool:
        """
        Whitelist for Betfair Spain viable sports.
        """
        # Allow 'teams' (generic category) and 'unknown' (to let tags decide)
        viable_categories = [
            "soccer", "tennis", "basketball", "american_football", 
            "ice_hockey", "esports", "teams", "unknown", "ncaa", "baseball"
        ]
        
        if category.lower() not in viable_categories:
            return False
            
        # Reject non-sports niche even if they have sport-like names (e.g. Politics/Pop Culture)
        blacklist_tags = ["politics", "pop-culture", "crypto", "science", "entertainment"]
        for tag in poly_tags:
            if tag.lower() in blacklist_tags:
                return False
                
        return True
