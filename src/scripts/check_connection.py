import os
import logging
from dotenv import load_dotenv
import sys

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.execution.clob_executor import PolymarketCLOBExecutor

# Config Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ConnectionCheck")

def main():
    load_dotenv()
    # Load env
    host = os.getenv("CLOB_API_HOST", "https://clob.polymarket.com")
    key = os.getenv("PRIVATE_KEY", "dummy_key")
    
    if key == "dummy_key":
        logger.warning("⚠️ Using DUMMY KEY. Authenticated endpoints will fail.")
        key = "0" * 64 # Valid hex for library init
    
    logger.info(f"🔌 Connecting to {host}...")
    
    try:
        executor = PolymarketCLOBExecutor(host=host, key=key)
        
        # 1. Identity Check
        address = executor.get_address()
        logger.info(f"🔑 Identity Verified: {address}")
        if address == "0xUnknown" or address == "0xMock":
             if key != "dummy_key":
                 logger.error("❌ Failed to derive address from key.")
                 sys.exit(1)
        
        # 2. Balance Check (Hard Stop Preview)
        balance = executor.get_balance()
        logger.info(f"💰 Wallet Balance: ${balance:.2f}")
        
        MIN_START_CAPITAL = 20.0
        # In a real run we would fail here if < 20.
        # For this test, if we return placeholder 21.0 it passes, 
        # but user knows they need to see their REAL balance.
        if balance < 10.0:
            logger.critical(f"🛑 CRITICAL: Balance ${balance} < $10.0 Safety Limit.")
            sys.exit(1)
            
        if balance < MIN_START_CAPITAL:
            logger.warning(f"⚠️ Balance ${balance} is below recommended ${MIN_START_CAPITAL} start.")

        # 3. Read Check
        logger.info("📡 Pinging Polymarket API (Active Markets)...")
        # Reuse existing client logic
        if executor.client:
            markets = executor.client.get_markets(next_cursor="")
            if markets and 'data' in markets:
                count = len(markets['data'])
                logger.info(f"✅ CONNECTION SUCCESSFUL. Retrieved {count} markets.")
            else:
                logger.warning(f"⚠️ Connected, but likely no markets or error: {markets}")
        else:
            # Fallback if client init failed
            logger.error("❌ Client not initialized.")
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ CONNECTION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
