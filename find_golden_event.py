import asyncio
import logging
from src.data.sx_bet_client import SXBetClient

logging.basicConfig(level=logging.INFO)

async def scan_sx_content():
    client = SXBetClient()
    print(">> SCANNING SX BET INVENTORY...")
    
    markets = await client.get_active_markets()
    print(f"   Found {len(markets)} active markets.")
    
    # Group by Sport/League
    inventory = {}
    for m in markets:
        key = f"{m.sport_label} - {m.label}" 
        # Actually sport label is category, league is usually in the raw data but parsed into sport_label in some versions.
        # Let's just print the labels to find a famous match.
        print(f"   - {m.label} ({m.sport_label})")
        
    await client.close()

if __name__ == "__main__":
    asyncio.run(scan_sx_content())
