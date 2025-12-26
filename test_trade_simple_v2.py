import os
import asyncio
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs

load_dotenv()

async def main():
    print('\n[2] Testing Polymarket Order V2 (creds derivation)')
    token_hex = '0x80b959a32b7e7ff10dafd72549da982bf046caf8f5fa804f5ab6179945bbd85' 
    pk = os.getenv('PRIVATE_KEY')
    
    try:
        # 1. Init without creds
        client = ClobClient('https://clob.polymarket.com', key=pk, chain_id=137)
        
        # 2. Check/Derive Creds
        try:
            # Try to force API key creation/retrieval if needed
            print('Attempting to create/get API key...')
            try:
                # This method exists in newer versions to ensure L2 keys exist
                key = client.create_api_key()
                print(f'API Key created: {key}')
            except:
                print('create_api_key failed or key exists')
                
        except Exception as e:
            print(f"Creds setup warning: {e}")

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
