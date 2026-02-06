
import logging
import sys
import os
import asyncio
sys.path.append(os.getcwd())
from src.data.betfair_client import BetfairClient

# Force unbuffered stdout
sys.stdout.reconfigure(line_buffering=True)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_login():
    print("--- STARTING AUTH DEBUG ---")
    client = BetfairClient()
    print(f"Endpoint: {client.endpoint}")
    print(f"Certs: {client.cert_path}, {client.key_path}")
    
    success = await client.login()
    print(f"--- LOGIN RESULT: {success} ---")
    
    if success:
        print("Session Valid:", client._session.is_valid)

if __name__ == "__main__":
    asyncio.run(test_login())
