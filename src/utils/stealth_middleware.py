
import logging
import asyncio
from typing import Dict, Any, Optional, Union
from src.utils.stealth_config import stealth

logger = logging.getLogger(__name__)

try:
    from curl_cffi.requests import AsyncSession
    CURL_CFFI_AVAILABLE = True
except ImportError:
    import httpx
    CURL_CFFI_AVAILABLE = False
    logger.warning("curl_cffi not found. TLS Fingerprinting disabled. Falling back to httpx.")

class StealthClient:
    """
    HTTP Client with Stealth capabilities.
    Uses curl_cffi for TLS Fingerprinting and Proxy Rotation.
    """
    
    def __init__(self, host: str = "www.betfair.es"):
        self.host = host
        self._session = None
        
    async def _get_session(self):
        if self._session is None:
            if CURL_CFFI_AVAILABLE:
                self._session = AsyncSession(
                    impersonate=stealth.get_impersonate(),
                    proxies=stealth.get_proxy_dict()
                )
            else:
                self._session = httpx.AsyncClient(
                    proxies=stealth.get_proxy_dict()
                )
        return self._session

    async def request(self, method: str, url: str, **kwargs) -> Any:
        """Perform a stealth request."""
        session = await self._get_session()
        
        # Apply stealth headers if not provided
        if "headers" not in kwargs:
            kwargs["headers"] = stealth.get_headers(self.host)
            
        # Rotate UA for every few requests or on specific triggers
        # For simplicity, we stick to the current one or rotate here
        
        try:
            if CURL_CFFI_AVAILABLE:
                # curl_cffi handles proxies at session level, but we can override
                response = await session.request(method, url, **kwargs)
                return response
            else:
                response = await session.request(method, url, **kwargs)
                return response
        except Exception as e:
            logger.error(f"Stealth request failed: {e}")
            raise

    async def get(self, url: str, **kwargs):
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs):
        return await self.request("POST", url, **kwargs)

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

async def test_stealth():
    client = StealthClient()
    logger.info("Testing Stealth Client...")
    try:
        # Test with a site that shows fingerprints or IP
        resp = await client.get("https://httpbin.org/ip")
        print(f"IP Trace: {resp.json()}")
        
        resp = await client.get("https://httpbin.org/user-agent")
        print(f"UA Trace: {resp.json()}")
        
    finally:
        await client.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_stealth())
