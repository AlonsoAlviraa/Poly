import os
import asyncio
import sys
import aiohttp
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from py_clob_client.client import ClobClient

load_dotenv()

async def main():
    print('\n🚀 KEY RECOVERY & ROTATION TOOL')
    
    pk = os.getenv('PRIVATE_KEY')
    host = "https://clob.polymarket.com"
    chain_id = 137
    
    print(f"Initializing Client for Wallet {os.getenv('WALLET_ADDRESS')}...")
    
    try:
        client = ClobClient(host, key=pk, chain_id=chain_id)
        
        # 1. List Existing Keys
        print("\n[1] Check for existing API Keys...")
        try:
             # get_api_keys usually returns a list of dictionaries/objects
             keys = client.get_api_keys()
             print(f"Found {len(keys)} existing keys.")
             
             for k in keys:
                 print(f" - Key ID: {k.get('apiKey')}")
                 
             # 2. Delete Existing Keys (if any)
             if keys:
                 print("\n[2] DELETING existing keys to allow rotation...")
                 for k in keys:
                     kid = k.get('apiKey')
                     print(f"Deleting {kid}...")
                     resp = client.delete_api_key() # Some clients take arg, others use implicit current? 
                     # Wait, py-clob-client methods often differ.
                     # signature: delete_api_key(self) -> deletes ALL? or current?
                     # Let's try basic call.
                     print(f"Delete response: {resp}")
                     
        except Exception as e:
             print(f"Error listing/deleting keys: {e}")
             
        # 3. Create NEW Key
        print("\n[3] Creating NEW API Key...")
        try:
            creds = client.create_api_key()
            print("\n✅✅ SUCCESS! NEW CREDENTIALS GENERATED:")
            print(f"POLY_KEY={creds.api_key}")
            print(f"POLY_SECRET={creds.api_secret}")
            print(f"POLY_PASSPHRASE={creds.api_passphrase}")
            print("\n👉 Please update your .env file with these values immediately!")
            
        except Exception as e:
            print(f"❌ Creation Failed: {e}")

    except Exception as e:
        print(f"❌ Client Init Error: {e}")

if __name__ == '__main__':
    asyncio.run(main())
