import asyncio
from src.collectors.bookmakers import BookmakerClient
from src.collectors.polymarket import PolymarketClient
from src.core.player_matcher import PlayerMatcher

async def main():
    bookie_client = BookmakerClient()
    poly_client = PolymarketClient()
    matcher = PlayerMatcher()

    # Fetch limited data
    print("Fetching limited data...")
    bookie_events = await bookie_client.get_all_odds_async()
    poly_events = await poly_client.search_events_async(keywords=None)
    
    # Extract props
    all_props = []
    for event in bookie_events:
        props = matcher.parse_bookmaker_props(event)
        all_props.extend(props)
    
    print(f"\n=== BOOKMAKER PROPS SAMPLE ===")
    if all_props:
        for i, p in enumerate(all_props[:5]):
            print(f"{i+1}. Player: {p['player_raw']}")
            print(f"   Market: {p['market_key']}, Side: {p['side']}, Line: {p['line']}, Price: {p['price']}")
            print(f"   Normalized: {p['player_norm']}\n")
    
    print(f"\n=== POLYMARKET TITLES SAMPLE ===")
    for i, e in enumerate(poly_events[:20]):
        title = e.get("title", "")
        if any(keyword in title.lower() for keyword in ["points", "assists", "rebounds", "lebron", "curry", "durant"]):
            print(f"{i+1}. {title}")
            parsed = matcher.parse_polymarket_prop(e)
            if parsed:
                print(f"   -> Parsed: Stat={parsed['stat_type']}, Line={parsed['line']}")
    
    # Test one match manually
    if all_props and poly_events:
        print(f"\n=== TESTING MATCH ===")
        test_prop = all_props[0]
        for p_event in poly_events[:100]:
            match = matcher.match_player_prop(test_prop, p_event)
            if match:
                print(f"MATCH FOUND!")
                print(f"Bookie: {test_prop}")
                print(f"Poly: {match['poly_prop']}")
                print(f"Score: {match['match_score']}")
                break

if __name__ == "__main__":
    asyncio.run(main())
