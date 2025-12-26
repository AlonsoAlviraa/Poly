import asyncio
import csv
from datetime import datetime
from src.collectors.bookmakers import BookmakerClient
from src.collectors.polymarket import PolymarketClient
from src.core.player_matcher import PlayerMatcher

PROPS_FILE = "props_qa.csv"

# Keywords to find props in Polymarket
PROP_KEYWORDS = [
    "Points", "Assists", "Rebounds",  # NBA
    "Touchdown", "Passing Yards", "Rushing Yards", "Receptions"  # NFL
]

async def main():
    print("Starting Props QA Sweep...")
    
    bookie_client = BookmakerClient()
    poly_client = PolymarketClient()
    matcher = PlayerMatcher()

    # 1. Fetch Data
    print("Fetching data (including 2-step prop fetch for Bookies)...")
    start_time = datetime.now()
    
    # Run concurrently
    print("  -> Dispatching Bookmaker and Polymarket tasks...")
    results = await asyncio.gather(
        bookie_client.get_all_odds_async(),
        poly_client.search_events_async(keywords=PROP_KEYWORDS)
    )
    bookie_events, poly_events = results
    
    print(f"  -> Done. Fetched {len(bookie_events)} Bookmaker events (total) and {len(poly_events)} Poly events.")
    
    # Debug: Check if any props in Bookmaker events
    prop_count = sum(1 for e in bookie_events if any(m.get('key').startswith('player_') for b in e.get('bookmakers', []) for m in b.get('markets', [])))
    print(f"  -> Found {prop_count} Bookmaker events with Player Props.")

    # 2. Extract Bookie Props
    print("Extracting Bookie Props...")
    all_bookie_props = []
    for event in bookie_events:
        props = matcher.parse_bookmaker_props(event)
        all_bookie_props.extend(props)
        
    print(f"Computed {len(all_bookie_props)} individual Bookmaker prop lines.")
    
    # 3. Match against Poly Events
    print("Matching against Polymarket...")
    matches = []
    
    with open(PROPS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Player", "Stat", "Line", "Side", "Bookie", "B_Price", "Poly Title", "Score"])
        
        for b_prop in all_bookie_props:
            for p_event in poly_events:
                match = matcher.match_player_prop(b_prop, p_event)
                if match:
                    matches.append(match)
                    writer.writerow([
                        b_prop["player_raw"],
                        b_prop["market_key"],
                        b_prop["line"],
                        b_prop["side"],
                        b_prop["bookie"],
                        b_prop["price"],
                        match["poly_prop"]["title"],
                        match["match_score"]
                    ])
                    # Optimization: Break if exact match found? 
                    # No, match against multiple markets potentially.

    print(f"Props Sweep Complete. Found {len(matches)} potential matches. Saved to {PROPS_FILE}.")
    if matches:
        print("Sample Matches:")
        for m in matches[:5]:
            print(f" - {m['bookie_prop']['player_raw']} {m['bookie_prop']['side']} {m['bookie_prop']['line']} vs {m['poly_prop']['title']}")

if __name__ == "__main__":
    asyncio.run(main())
