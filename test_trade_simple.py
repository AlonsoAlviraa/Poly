import os
import asyncio
import sys
# Add current dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs
from py_clob_client.constants import POLYGON
from src.exchanges.sx_bet_client import SXBetClient

load_dotenv()

async def main():
    print('--- MANUAL TRADE TEST SCOPE ---')
    
    # 1. SX BET TEST
    print('\n[1] Testing SX Bet Order')
    try:
        sx_client = SXBetClient()
        markets = await sx_client.get_active_markets()
        if markets:
             m = markets[0]
             print(f'Found SX Market: {m.get("label")} ({m.get("marketHash")})')
             # Try placing a limit order far away or small size
             print("Skipping actual SX trade execution to avoid stuck funds for now, connectivity validated.")
        else:
             print("No SX markets found.")
        await sx_client.close()
    except Exception as e:
        print(f'SX Test Error: {e}')

    # 2. POLYMARKET TEST
    print('\n[2] Testing Polymarket Order')
    # Using the YES token for "Bill Belichick engaged...?"
    token_hex = '0x80b959a32b7e7ff10dafd72549da982bf046caf8f5fa804f5ab6179945bbd85' 
    
    pk = os.getenv('PRIVATE_KEY')
    print(f"Using PK: {pk[:6]}...{pk[-4:]}")

    try:
        client = ClobClient(
            host='https://clob.polymarket.com', 
            key=pk, 
            chain_id=137
        )
        # Ensure creds
        client.get_or_create_api_key()
        
        print(f'Trying to buy 1 USDC of token {token_hex}...')
        args = MarketOrderArgs(
            token_id=token_hex,
            amount=1.0, 
            side='BUY'
        )
        resp = client.create_market_order(args)
        res = client.post_order(resp)
        print(f'✅ Polymarket Order SUCCESS: {res}')
    except Exception as e:
        print(f'❌ Polymarket Order FAILED: {e}')

if __name__ == '__main__':
    asyncio.run(main())
