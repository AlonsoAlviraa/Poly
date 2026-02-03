
import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Callable
from py_clob_client.client import ClobClient
from src.utils.stealth_config import stealth

logger = logging.getLogger(__name__)

class PolyWSSManager:
    """
    Manages WebSocket connections to Polymarket CLOB.
    Listen for real-time orderbook updates.
    """
    
    def __init__(self, token_ids: List[str], callback: Callable):
        self.token_ids = token_ids
        self.callback = callback
        self.host = "https://clob.polymarket.com"
        self.client: Optional[ClobClient] = None
        self._ws_client = None
        self.is_running = False
        
    async def connect(self):
        """Establish WSS connection and subscribe to orderbooks."""
        try:
            from py_clob_client.client import ClobClient
            
            # Use real keys from env if available, otherwise dummy for public data
            pk = os.getenv('PRIVATE_KEY', '0x' + '0'*64)
            self.client = ClobClient(host=self.host, key=pk, chain_id=137)
            
            self._ws_client = self.client.create_websocket_client()
            
            logger.info(f"[PolyWSS] Connecting to CLOB WSS for {len(self.token_ids)} tokens...")
            
            self.is_running = True
            await self._ws_client.connect()
            
            # Subscribe to orderbook updates
            for token_id in self.token_ids:
                await self._ws_client.subscribe(
                    channel="orderbook",
                    market=token_id,
                    on_message=self._on_message
                )
            
            logger.info(f"[PolyWSS] Subscribed to {len(self.token_ids)} tokens")
            
        except Exception as e:
            logger.error(f"[PolyWSS] Connection error: {e}")

    def _on_message(self, message):
        """Handle incoming WSS messages."""
        try:
            data = json.loads(message) if isinstance(message, str) else message
            # Wrap in asyncio task to handle callback
            asyncio.create_task(self.callback("polymarket", data))
        except Exception as e:
            logger.error(f"[PolyWSS] Sync message error: {e}")

    async def disconnect(self):
        if self._ws_client:
            await self._ws_client.disconnect()
            self.is_running = False

            
class BetfairStreamManager:
    """
    Manages Betfair Stream API connection.
    Uses push-events for speed.
    """
    
    def __init__(self, session_token: str, app_key: str, callback: Callable):
        self.session_token = session_token
        self.app_key = app_key
        self.callback = callback
        self.host = "stream-api.betfair.com"
        self.port = 443
        self.is_running = False
        
    async def connect(self, market_ids: Optional[List[str]] = None):
        """Connect and subscribe to Betfair Stream."""
        try:
            import ssl
            context = ssl.create_default_context()
            
            # Betfair Stream API requires TLS
            self._reader, self._writer = await asyncio.open_connection(
                self.host, self.port, ssl=context
            )
            
            # 1. Authentication
            auth_msg = {
                "op": "authentication",
                "appKey": self.app_key,
                "session": self.session_token
            }
            self._writer.write((json.dumps(auth_msg) + "\r\n").encode())
            await self._writer.drain()
            
            # 2. Subscription (if market_ids provided)
            if market_ids:
                sub_msg = {
                    "op": "marketSubscription",
                    "marketFilter": {"marketIds": market_ids},
                    "marketDataFilter": {
                        "fields": ["EX_BEST_OFFERS_DISP", "EX_TRADED_VOL", "EX_MARKET_DEF"],
                        "ladderLevels": 3
                    }
                }
                self._writer.write((json.dumps(sub_msg) + "\r\n").encode())
                await self._writer.drain()
                logger.info(f"[BetfairStream] Subscribed to {len(market_ids)} markets")
            
            self.is_running = True
            asyncio.create_task(self._handle_stream(self._reader))
            logger.info("[BetfairStream] Connected and handling stream")
            
        except Exception as e:
            logger.error(f"[BetfairStream] Connection error: {e}")

    async def _handle_stream(self, reader):
        """Handle incoming stream messages."""
        while self.is_running:
            try:
                line = await reader.readline()
                if not line:
                    logger.warning("[BetfairStream] connection closed by host")
                    break
                
                data = json.loads(line.decode())
                
                # Check for heartbeat or other ops
                op = data.get("op")
                if op == "mcm": # Market Change Message
                    await self.callback("betfair", data)
                elif op == "status":
                    logger.debug(f"[BetfairStream] Status: {data.get('statusCode')}")
                
            except Exception as e:
                logger.error(f"[BetfairStream] Error: {e}")
                break
        self.is_running = False

    async def disconnect(self):
        self.is_running = False
        if hasattr(self, '_writer'):
            self._writer.close()
            await self._writer.wait_closed()
