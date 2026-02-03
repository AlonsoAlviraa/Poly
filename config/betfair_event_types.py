"""
Betfair Event Type IDs Configuration.

This file defines which event types (categories) to fetch from Betfair
for cross-platform arbitrage with Polymarket.

KEY INSIGHT: Polymarket trades on Politics, Crypto, Finance, and Current Affairs.
Betfair has these categories too, but we must explicitly request them.

⚠️  IMPORTANT JURISDICTIONAL NOTE:
    - Betfair GLOBAL (.com): Has Politics, Special Bets, Financial Bets
    - Betfair SPAIN (.es): ONLY has Sports (Soccer, Basketball, etc.)
    - Betfair ITALY (.it): Similar to Spain, sports-focused
    
    For Polymarket arbitrage, you NEED Betfair Global (requires UK/intl account).
    Spanish/Italian accounts are LEGALLY RESTRICTED to sports only.
    
    If you only have a Spanish account, cross-platform arbitrage with
    Polymarket (Politics/Crypto) is NOT POSSIBLE via Betfair.
    Alternative: Use other prediction market platforms (Kalshi, PredictIt).

Event Type IDs (Source: listEventTypes API):
- 1: Soccer (Football)
- 2: Tennis  
- 4: Cricket
- 6: Boxing
- 7: Horse Racing
- 10: Special Bets (*) - ONLY on Betfair.com (Global)
- 2378961: Politics (*) - ONLY on Betfair.com (Global)
- 3988: Athletics / Current Affairs (*) - ONLY on Betfair.com (Global)
- 6231: Financial Bets (*) - ONLY on Betfair.com (Global)
- 7522: Basketball
- 7511: Baseball
- 6422: Snooker
- 4339: Greyhound Racing
- 6423: American Football
- 27454571: eSports

(*) = Critical for Polymarket arbitrage matching, but ONLY available on Global endpoint
"""

from typing import List

# ============================================================================
# POLYMARKET-COMPATIBLE EVENT TYPES
# These are the event types that are most likely to match Polymarket markets
# ============================================================================

# Primary event types for arbitrage matching (ordered by relevance)
POLYMARKET_COMPATIBLE_EVENT_TYPES: List[str] = [
    "2378961",  # Politics - ¡El más importante! (Elections, Leaders, etc.)
    "10",       # Special Bets (Miscellaneous, Entertainment, Awards)
    "6231",     # Financial Bets (Bitcoin, Crypto, Stock Markets)
    "3988",     # Athletics / Current Affairs
]

# Sports event types (for Betfair España - these ARE available)
# Use these for Polymarket Sports vs Betfair España arbitrage
SPORTS_EVENT_TYPES: List[str] = [
    "1",        # Soccer (⭐ Highest volume on Betfair.es)
    "2",        # Tennis
    "4",        # Cricket
    "7522",     # Basketball (NBA, EuroLeague)
    "6423",     # American Football (NFL, Super Bowl)
    "7511",     # Baseball (MLB)
    "7524",     # Ice Hockey (NHL)
    "26420387", # Mixed Martial Arts (UFC)
    "27454571", # E-Sports
    "7",        # Horse Racing
]

# Sports keywords for Polymarket matching (Spanish/English)
# Expanded to catch individual match markets
SPORTS_KEYWORDS: List[str] = [
    # General sports
    "soccer", "football", "futbol", "fútbol",
    "nba", "basketball", "baloncesto",
    "nfl", "super bowl", "american football",
    "tennis", "tenis", "wimbledon", "us open", "french open", "australian open",
    "champions league", "la liga", "premier league", "bundesliga", "serie a", "ligue 1",
    "world cup", "mundial", "euro 2026", "euro 2028",
    "mlb", "baseball",
    "nhl", "hockey",
    "ufc", "mma", "boxing",
    "f1", "formula 1", "formula one",
    "olympics", "olympic",
    "golf", "pga", "masters",
    
    # Match patterns (individual games)
    "win on", "vs", "v.", "o/u", "over/under",
    
    # Awards/MVP
    "mvp", "coach of the year", "rookie", "opoy", "dpoy",
    
    # Teams (European Soccer)
    "real madrid", "barcelona", "atletico", "sevilla", "valencia",
    "manchester united", "manchester city", "liverpool", "chelsea", "arsenal", "tottenham",
    "bayern", "dortmund", "leipzig",
    "juventus", "inter", "milan", "napoli", "roma", "lazio",
    "psg", "marseille", "lyon",
    "ajax", "psv", "feyenoord", "utrecht",
    "osasuna", "athletic", "betis", "villarreal",
    "fulham", "burnley", "brighton", "newcastle", "aston villa",
    
    # Teams (American Sports)
    "lakers", "celtics", "warriors", "knicks", "bulls",
    "chiefs", "eagles", "49ers", "cowboys", "bills",
    "yankees", "dodgers", "red sox",
    
    # Countries
    "brazil", "argentina", "germany", "france", "england", "spain", "italy",
    
    # Other keywords
    "playoff", "finals", "championship", "tournament", "league",
    "score", "points", "goals",
]

# All available event types for discovery
ALL_EVENT_TYPES: List[str] = POLYMARKET_COMPATIBLE_EVENT_TYPES + SPORTS_EVENT_TYPES

# ============================================================================
# ENDPOINT CONFIGURATION
# ============================================================================

# Which Betfair endpoint to use:
# - "GLOBAL": betfair.com (UK/International) - Has Politics, Specials, Finance
# - "SPAIN": betfair.es (Spanish regulated) - ONLY Sports
# - "ITALY": betfair.it (Italian regulated) - ONLY Sports
#
# Set this in .env as BETFAIR_ENDPOINT=GLOBAL for Polymarket arbitrage
BETFAIR_ENDPOINT: str = "GLOBAL"  # Default to Global for Polymarket arbitrage

# ============================================================================
# DEFAULT CONFIGURATION
# ============================================================================

# Default event types to use when scanning Betfair for Polymarket arbitrage
# Change this to SPORTS_EVENT_TYPES if you want to test with sports
DEFAULT_EVENT_TYPES: List[str] = POLYMARKET_COMPATIBLE_EVENT_TYPES

# Fallback to all types if specific categories return empty
FALLBACK_TO_ALL: bool = True

# Whether to show warning when no Politics/Specials are found
WARN_ON_MISSING_POLYMARKET_TYPES: bool = True

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_event_type_name(event_type_id: str) -> str:
    """Get human-readable name for event type ID."""
    names = {
        "1": "Soccer",
        "2": "Tennis",
        "4": "Cricket",
        "7": "Horse Racing",
        "10": "Special Bets",
        "2378961": "Politics",
        "3988": "Current Affairs",
        "6231": "Financial Bets",
        "7522": "Basketball",
        "6423": "American Football",
    }
    return names.get(event_type_id, f"Unknown ({event_type_id})")


def get_event_types_for_polymarket() -> List[str]:
    """
    Get the event types to query for Polymarket matching.
    
    Returns:
        List of event type IDs optimized for Polymarket arbitrage
    """
    return POLYMARKET_COMPATIBLE_EVENT_TYPES.copy()


def get_all_event_types() -> List[str]:
    """Get all available event types."""
    return ALL_EVENT_TYPES.copy()
