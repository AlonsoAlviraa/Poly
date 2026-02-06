
import sys
import os
import asyncio
import logging
from datetime import datetime

# Setup path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DebugMatching")

try:
    from src.arbitrage.cross_platform_mapper import CrossPlatformMapper
except ImportError:
    # Quick fix for running from root
    sys.path.append(os.getcwd())
    from src.arbitrage.cross_platform_mapper import CrossPlatformMapper

async def main():
    print("--- 🕵️ DEBUGGING MATCH LOGIC ---")
    mapper = CrossPlatformMapper()
    
    # Mock Data based on User Logs
    bf_events = [
        {"name": "Charlton v QPR", "event_id": "1", "market_id": "1.1", "openDate": "2025-12-06T15:00:00Z"},
        {"name": "Real Madrid v Barcelona", "event_id": "2", "market_id": "1.2", "openDate": "2026-03-01T20:00:00Z"}
    ]
    
    test_cases = [
        # Case 1: The False Positive (Opponent Mismatch)
        {
            "question": "Will Charlton Athletic FC vs. Portsmouth FC end in a draw?",
            "id": "100",
            "slug": "charlton-vs-portsmouth",
            "startDate": "2025-12-06T15:00:00Z" # Same date as QPR match for tricky test
        },
        # Case 2: Date Mismatch (Assuming QPR match is today, query is next year)
        {
            "question": "Will Charlton Athletic FC win on 2026-12-06?", 
            "id": "101",
            "slug": "charlton-win-2026",
            "startDate": "2026-12-06T15:00:00Z"
        }
    ]

    print(f"\nLoaded {len(mapper.static_map)} aliases.")
    
    # Pre-compute entities like the optimize update did
    for event in bf_events:
        event['_entities'] = mapper._get_standard_entities(event['name'])
        print(f"BF Event '{event['name']}' -> Entities: {event['_entities']}")

    print("\n--- Running Tests ---")
    
    for poly in test_cases:
        print(f"\n🔎 Testing Poly: '{poly['question']}'")
        poly_ents = mapper._get_standard_entities(poly['question'])
        print(f"   Entities found: {poly_ents}")
        
        match = await mapper._attempt_static_match(poly, bf_events)
        
        if match:
            print(f"   ❌ MATCHED: {match.betfair_event_name}")
            print(f"      Reason: {getattr(match, 'reasoning', 'N/A')}")
            if poly['slug'] == "charlton-vs-portsmouth" and match.betfair_event_name == "Charlton v QPR":
                print("      ⚠️ ERROR CONFIRMED: Matched Portsmouth to QPR because of shared 'Charlton'!")
        else:
            print("   ✅ NO MATCH (Correct Behavior)")

if __name__ == "__main__":
    asyncio.run(main())
