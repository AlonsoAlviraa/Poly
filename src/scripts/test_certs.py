
import os
import sys
import logging
import asyncio

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.data.betfair_client import BetfairClient
from dotenv import load_dotenv

# Load env immediately
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("CertTester")

async def test_login():
    logger.info("🔐 Testing Betfair Certificates...")
    
    client = BetfairClient()
    
    # Check if cert files exist
    cert_file = os.getenv("BETFAIR_CERT_PATH")
    key_file = os.getenv("BETFAIR_KEY_PATH")
    
    if not cert_file or not key_file:
        logger.error(f"❌ Certificate paths not found in environment variables. (Looking for BETFAIR_CERT_PATH/KEY_PATH)")
        return False
        
    if not os.path.exists(cert_file):
        logger.error(f"❌ Certificate file not found at: {cert_file}")
        return False
        
    if not os.path.exists(key_file):
        logger.error(f"❌ Key file not found at: {key_file}")
        return False
        
    logger.info(f"✅ Files found: {cert_file}, {key_file}")
    
    try:
        start_time = asyncio.get_event_loop().time()
        success = await client.login()
        duration = asyncio.get_event_loop().time() - start_time
        
        if success and client._session:
            logger.info(f"✅ LOGIN SUCCESSFUL! (Time: {duration:.2f}s)")
            logger.info(f"🔑 Session Token: {client._session.ssoid[:10]}...")
            return True
        else:
            logger.error("❌ Login Failed (API returned failure). Check credentials.")
            return False
            
    except Exception as e:
        logger.error(f"❌ Login Exception: {e}")
        return False

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        success = asyncio.run(test_login())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        pass
