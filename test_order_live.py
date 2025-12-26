import os
import asyncio
import sys
import aiohttp
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs

load_dotenv()

async def get_live_token_id():
    url = "https://gamma-api.polymarket.com/events?limit=5&closed=false&tag_slug=sports"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            for event in data:
                markets = event.get('markets', [])
                for m in markets:
                    raw_ids = m.get('clobTokenIds')
                    if isinstance(raw_ids, str):
                        try:
                            raw_ids = json.loads(raw_ids)
                        except:
                            continue
                    if raw_ids and isinstance(raw_ids, list) and len(raw_ids) >= 2:
                        return raw_ids[0]
    return None

async def main():
    print('\n🚀 STARTING LIVE ORDER TEST (DERIVE CREDS for 0x1AE...)')
    
    token_id = await get_live_token_id()
    if not token_id:
        print("❌ Could not get a valid token ID.")
        return

    pk = os.getenv('PRIVATE_KEY') # 0x1AE...
    host = "https://clob.polymarket.com"
    chain_id = 137
    
    print("Initializing Client...")
    try:
        # Init without creds first (uses PK)
        client = ClobClient(host, key=pk, chain_id=chain_id)
        
        # Derive
        print("Attempting to DERIVE API Credentials from Private Key...")
        try:
             creds = client.derive_api_credentials()
             print(f"✅ DERIVED CREDENTIALS SUCCESS!")
             print(f"Key: {creds.api_key}")
             print(f"Secret: {creds.api_secret[:10]}...")
             print(f"Passphrase: {creds.api_passphrase[:10]}...")
             
             # Re-init with derived creds
             client = ClobClient(host, key=pk, chain_id=chain_id, creds=creds)
             
        except Exception as e:
             print(f"⚠️ Derivation failed: {e}")
             print("Falling back to .env creds (which imply 0x3a79... mismatch potentially)")
        
        print(f'Attempting to BUY 1.0 USDC of Token {token_id}...')
        args = MarketOrderArgs(
            token_id=token_id,
            amount=1.0, 
            side='BUY'
        )
        print("Creating order...")
        resp = client.create_market_order(args)
        print("Posting order...")
        res = client.post_order(resp)
        print(f'✅ ACCEPTED! Order Info: {res}')
        
    except Exception as e:
        print(f'❌ TEST FAILED: {e}')
        if hasattr(e, 'response'):
             print(f"Response: {e.response}")

if __name__ == '__main__':
    asyncio.run(main())
