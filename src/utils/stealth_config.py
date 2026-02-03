
import os
import random
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Real-world User-Agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/118.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0"
]

class StealthConfig:
    """
    Manages stealth headers, proxy rotation, and browser fingerprints.
    Ensures that our requests look like legitimate browser traffic.
    """
    
    def __init__(self, proxy_urls: Optional[List[str]] = None):
        # Load proxies from env or arg
        env_proxies = os.getenv('RESIDENTIAL_PROXIES', '').split(',')
        self.proxies = [p.strip() for p in env_proxies if p.strip()]
        if proxy_urls:
            self.proxies.extend(proxy_urls)
            
        self.current_ua = random.choice(USER_AGENTS)
        self.current_proxy_idx = 0
        if self.proxies:
            random.shuffle(self.proxies)
        
        # TLS Impersonation targets for curl_cffi
        self.impersonates = ["chrome110", "chrome116", "safari15_5", "firefox107"]
        
    def get_headers(self, host: str = "www.betfair.es") -> Dict[str, str]:
        """Generate browser-like headers for a specific host."""
        return {
            "User-Agent": self.current_ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "Host": host
        }
    
    def get_proxy(self) -> Optional[str]:
        """Get the next proxy in the rotation."""
        if not self.proxies:
            return None
        proxy = self.proxies[self.current_proxy_idx]
        self.current_proxy_idx = (self.current_proxy_idx + 1) % len(self.proxies)
        return proxy

    def get_proxy_dict(self) -> Optional[Dict[str, str]]:
        """Return proxy configuration for HTTP clients."""
        proxy = self.get_proxy()
        if not proxy:
            return None
        return {
            "http://": proxy,
            "https://": proxy
        }

    def get_impersonate(self) -> str:
        """Get a random TLS impersonation target."""
        return random.choice(self.impersonates)

# Singleton instance
stealth = StealthConfig()
