import os
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs
from py_clob_client.constants import POLYGON

load_dotenv('/home/ubuntu/arbitrage_platform/.env')

pk = os.getenv('PRIVATE_KEY')
host = os.getenv('POLY_HOST')
chain_id = int(os.getenv('POLY_CHAIN_ID', 137))

try:
    # Mimic bot: Only PK provided
    print(f"Initializing client with PK: {pk[:6]}...")
    client = ClobClient(host, key=pk, chain_id=chain_id)
    # Force creds derivation/creation explicitly to ensure we can post?
    # Usually handled automatically, but maybe we need to create api key first?
    # If the bot fails 401 silently, it might be that.
    # But checking if we can post.
    if client.get_api_creds() is None:
        print("Creating new API Key...")
        try:
             client.create_api_key()
             print("Key created.")
        except Exception as e:
             print(f"Key creation error (might already exist?): {e}")

except Exception as e:
    print(f"Client init failed: {e}")
    exit(1)

# Known token from debug
decimal_id = '3638970623757421090502630508893477892849798151626925402397477702830934179205'
hex_id_0x = '0x80b959a32b7e7ff10dafd72549da982bf046caf8f5fa804f5ab6179945bbd85'
hex_id_no0x = '80b959a32b7e7ff10dafd72549da982bf046caf8f5fa804f5ab6179945bbd85'

formats = {
    'Decimal String': decimal_id,
    'Hex with 0x': hex_id_0x,
    'Hex without 0x': hex_id_no0x
}

def try_order(name, tid):
    print(f'\n--- Testing {name} ---')
    print(f'Token ID: {tid}')
    try:
        args = MarketOrderArgs(
            token_id=tid,
            amount=1.0, 
            side='BUY'
        )
        print('Creating order object...')
        order = client.create_market_order(args)
        
        print('Posting order...')
        res = client.post_order(order)
        print(f'SUCCESS! Response: {res}')
    except Exception as e:
        print(f'FAILED: {e}')

for name, tid in formats.items():
    try_order(name, tid)
