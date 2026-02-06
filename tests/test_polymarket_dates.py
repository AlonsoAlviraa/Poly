
import asyncio
import sys
import os
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.gamma_client import GammaAPIClient

async def test_dates():
    client = GammaAPIClient()
    print("Fetching Game Bets from Polymarket...")
    markets = client.get_all_match_markets(limit=20)
    
    now = datetime.now(timezone.utc)
    print(f"Current Time (UTC): {now}")
    print("-" * 60)
    
    if not markets:
        print("No markets found. Check API or TAG_GAME_BET.")
        return

    for m in markets:
        parsed_date = m.get('_event_date_parsed')
        root_start = m.get('startDate') # Should be standardized now
        question = m.get('question', 'N/A')
        
        print(f"Question: {question}")
        print(f"  Standardized startDate: {root_start}")
        print(f"  Internal Parsed Date:    {parsed_date}")
        
        if parsed_date:
            diff = (parsed_date - now).total_seconds() / 3600
            print(f"  Hours until start:       {diff:.2f}h")
            
            if parsed_date < now:
                print("  [WARNING] Event is in the PAST (but within 2h grace if shown)")
        else:
            print("  [ERROR] No parsed date found!")
        print("-" * 60)

if __name__ == "__main__":
    asyncio.run(test_dates())
