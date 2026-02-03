import os
import asyncio
import sys
import aiohttp
import json
import traceback

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs, ApiCreds

load_dotenv()

async def get_live_token_id():
    """Fetch ONE currently active market and return its YES token ID."""
    url = "https://gamma-api.polymarket.com/events?limit=20&closed=false&tag_slug=sports"
    async with aiohttp.ClientSession() as session:
        print(f"Fetching active markets from {url}...")
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
                        print(f"Target Market: {event['title']} - {m['question']}")
                        return raw_ids[0]
    return None

from eth_account import Account

async def main():
    print('\n🚀 STARTING LIVE ORDER TEST (FINAL)', flush=True)
    
    pk = os.getenv('PRIVATE_KEY')
    addr = Account.from_key(pk).address
    print(f"🔐 Signing with Wallet: {addr}")
    
    token_id = await get_live_token_id()
    if not token_id:
        print("❌ Could not get a valid token ID.")
        return

    print(f"✅ Using Token ID: {token_id}")
    
    pk = os.getenv('PRIVATE_KEY')
    host = "https://clob.polymarket.com"
    chain_id = 137
    
    # Load NEW L2 Creds from .env
    api_key = os.getenv('POLY_KEY')
    api_secret = os.getenv('POLY_SECRET')
    api_passphrase = os.getenv('POLY_PASSPHRASE')
    
    print(f"Using API Key: {api_key}")
    
    creds = ApiCreds(
        api_key=api_key,
        api_secret=api_secret,
        api_passphrase=api_passphrase
    )
    
    print(f"Initializing Client...", flush=True)
    
    # Try all signature types
    for sig_type in [0, 1, 2]:
        print(f"\n--- Testing Signature Type: {sig_type} ---")
        try:
            client = ClobClient(
                host, 
                key=pk, 
                chain_id=chain_id, 
                creds=creds, 
                signature_type=sig_type
            )
            
            # Validate Keys
            print("Validating credentials...", flush=True)
            keys = client.get_api_keys()
            print(f"✅ SUCCESS with Signature Type {sig_type}! Found {len(keys)} keys.")
            
            # If successful, try to place order
            print(f'Attempting to BUY 1.0 USDC of Token {token_id}...')
            args = MarketOrderArgs(
                token_id=token_id,
                amount=1.0, 
                side='BUY'
            )
            print("Creating order...", flush=True)
            resp = client.create_market_order(args)
            print("Posting order...", flush=True)
            res = client.post_order(resp)
            print(f'✅ ACCEPTED! Order Info: {res}')
            return # Exit on success
            
        except Exception as e:
            print(f"❌ Failed with SigType {sig_type}: {e}")
            
    print("\n❌ All Signature Types failed.")

if __name__ == '__main__':
    asyncio.run(main())
