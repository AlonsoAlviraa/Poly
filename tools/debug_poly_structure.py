
import os
import sys
import asyncio
import json

# Ensure src is in command path
sys.path.append(os.getcwd())

from src.execution.clob_executor import PolymarketCLOBExecutor

async def inspect_structure():
    print("--- DEBUGGING POLYMARKET RESPONSE ---")
    
    # Initialize without keys (public read)
    host = "https://clob.polymarket.com"
    key = os.getenv("PRIVATE_KEY", "0"*64)
    executor = PolymarketCLOBExecutor(host=host, key=key)
    
    try:
        # Fetch 1 page
        resp = executor.client.get_sampling_simplified_markets(next_cursor="")
        data = resp.get('data', [])
        
        if not data:
            print("❌ No data returned")
            return
            
        print(f"✅ Fetched {len(data)} items")
        
        # Inspect first item
        first = data[0]
        print("\n[KEYS FOUND IN FIRST ITEM]:")
        for k in sorted(first.keys()):
            val = str(first[k])
            if len(val) > 50: val = val[:50] + "..."
            print(f"  - {k}: {val}")
            
        print("\n[TOKENS DETAIL]:")
        tokens = first.get('tokens', [])
        for t in tokens:
            print(f"  - {t}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(inspect_structure())
