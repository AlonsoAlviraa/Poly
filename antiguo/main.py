import asyncio
import csv
import os
from datetime import datetime
from src.collectors.bookmakers import BookmakerClient
from src.collectors.polymarket import PolymarketClient
from src.core.matcher import EventMatcher
from src.core.analyzer import ArbitrageAnalyzer
from src.utils.notifier import send_alert

HISTORY_FILE = "opportunities_history.csv"

def save_opportunity(opp):
    file_exists = os.path.exists(HISTORY_FILE)
    with open(HISTORY_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Event", "Bookie Odds", "Poly Price", "Delta", "Liquidity", "Link"])
        
        writer.writerow([
            datetime.now(),
            opp['event'],
            opp['bookie_odds'],
            opp['poly_price'],
            opp['delta'],
            opp['liquidity'],
            opp['poly_link']
        ])

async def process_match(match, poly_client, analyzer):
    b_event, p_event = match
    
    # Extract Token ID (Home Win / Yes)
    markets = p_event.get("markets", [])
    if not markets:
        return None
    
    market = markets[0]
    clob_token_ids = market.get("clobTokenIds", [])
    if not clob_token_ids:
        return None
        
    token_id = clob_token_ids[0] # Assuming first token is "Yes" / Home
    
    # Fetch Depth
    price, size, asks = await poly_client.get_orderbook_depth_async(token_id)
    
    # Analyze
    opp = analyzer.calculate_arbitrage(b_event, p_event, asks)
    return opp

async def main():
    print("Starting Statistical Arbitrage Platform (Sprint Refactor V2)...")
    
    # Init
    bookie_client = BookmakerClient()
    poly_client = PolymarketClient()
    matcher = EventMatcher()
    analyzer = ArbitrageAnalyzer()

    # 1. Fetch Data Concurrently
    print("Fetching data asynchronously...")
    start_time = datetime.now()
    
    results = await asyncio.gather(
        bookie_client.get_all_odds_async(),
        poly_client.get_events_async()
    )
    bookie_events, poly_events = results
    
    print(f"Fetched {len(bookie_events)} Bookmaker events and {len(poly_events)} Polymarket events in {(datetime.now() - start_time).total_seconds():.2f}s.")

    # 2. Match
    print("Matching events...")
    matches = matcher.match_events(bookie_events, poly_events)
    print(f"Found {len(matches)} potential matches.")

    # 3. Analyze (Concurrent Depth Checks)
    print("Analyzing matches...")
    tasks = [process_match(m, poly_client, analyzer) for m in matches]
    opportunities = await asyncio.gather(*tasks)
    
    # Filter None
    opportunities = [o for o in opportunities if o]
    
    print(f"Analysis complete. Found {len(opportunities)} actionable opportunities.")
    
    for opp in opportunities:
        save_opportunity(opp)
        send_alert(opp)

if __name__ == "__main__":
    asyncio.run(main())
