
import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Callable, Any
from py_clob_client.client import ClobClient
from src.utils.stealth_config import stealth

logger = logging.getLogger(__name__)

class MarketUpdate:
    """Normalized Market Update Event."""
    def __init__(self, platform: str, market_id: str, best_bid: float, best_ask: float, 
                 bid_size: float, ask_size: float, fee_pct: float = 0.0, raw_data: Any = None):
        self.platform = platform
        self.market_id = market_id
        # Apply fees netos (Task 1)
        # If we BUY (hit ask), we pay fee on top or it's stripped from outcome.
        # Usually 'best_bid' from provider is what we get if we SELL.
        # 'best_ask' is what we pay if we BUY.
        self.best_bid = best_bid * (1 - fee_pct/100)
        self.best_ask = best_ask * (1 + fee_pct/100)
        self.bid_size = bid_size
        self.ask_size = ask_size
        self.fee_pct = fee_pct
        self.timestamp = asyncio.get_event_loop().time()
        self.raw_data = raw_data

class BaseStream:
    def __init__(self):
        self._subscribers = []
        self.is_running = False

    def subscribe(self, callback: Callable):
        self._subscribers.append(callback)

    async def _emit(self, event: MarketUpdate):
        for sub in self._subscribers:
            if asyncio.iscoroutinefunction(sub):
                await sub(event)
            else:
                sub(event)

class PolymarketStream(BaseStream):
    """
    WebSocket connection to Polymarket CLOB.
    Emits normalized MarketUpdate.
    """
    def __init__(self, token_ids: List[str]):
        super().__init__()
        self.token_ids = token_ids
        self.host = os.getenv('POLY_HOST', "https://clob.polymarket.com")
        self.client: Optional[ClobClient] = None
        self._ws_client = None
        self.fee_pct = float(os.getenv("POLY_FEE_PCT", "0.5"))
        
    async def connect(self):
        try:
            # Manual WSS Connection using websockets library
            import websockets
            # Corrected endpoint for CLOB v4/v5 subscriptions
            self._ws_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
            
            async with websockets.connect(self._ws_url) as ws:
                self._ws_client = ws
                self.is_running = True
                
                # Subscription message (Corrected for Task 2)
                sub_msg = {
                    "type": "subscribe",
                    "channel": "orderbook",
                    "market_ids": self.token_ids
                }
                await ws.send(json.dumps(sub_msg))
                
                logger.info(f"[PolymarketStream] Connected and subscribed to {len(self.token_ids)} tokens")
                
                while self.is_running:
                    msg = await ws.recv()
                    self._on_message(msg)
        except Exception as e:
            logger.error(f"[PolymarketStream] Connection error: {e}")
        except Exception as e:
            logger.error(f"[PolymarketStream] Connection error: {e}")

    def _on_message(self, message):
        try:
            data = json.loads(message) if isinstance(message, str) else message
            # NORMALIZATION Logic (Task 1)
            # Assuming Poly WSS message has 'bids' and 'asks' for orderbook updates
            bids = data.get('bids', [])
            asks = data.get('asks', [])
            
            best_bid = float(bids[0][0]) if bids else 0.0
            bid_size = float(bids[0][1]) if bids else 0.0
            best_ask = float(asks[0][0]) if asks else 0.0
            ask_size = float(asks[0][1]) if asks else 0.0
            
            event = MarketUpdate(
                platform="polymarket",
                market_id=data.get("market"),
                best_bid=best_bid,
                best_ask=best_ask,
                bid_size=bid_size,
                ask_size=ask_size,
                fee_pct=self.fee_pct,
                raw_data=data
            )
            asyncio.create_task(self._emit(event))
        except Exception as e:
            logger.error(f"[PolymarketStream] Normalization error: {e}")

    async def disconnect(self):
        if self._ws_client:
            await self._ws_client.disconnect()
            self.is_running = False

class BetfairStream(BaseStream):
    """
    Betfair Stream API connection.
    Emits normalized MarketUpdate.
    """
    def __init__(self, session_token: str, app_key: str):
        super().__init__()
        self.session_token = session_token
        self.app_key = app_key
        self.host = "stream-api.betfair.com"
        self.port = 443
        self.fee_pct = float(os.getenv("BETFAIR_COMMISSION_PCT", "6.5"))
        
    async def connect(self, market_ids: List[str]):
        try:
            import ssl
            context = ssl.create_default_context()
            self._reader, self._writer = await asyncio.open_connection(
                self.host, self.port, ssl=context
            )
            
            auth_msg = {"op": "authentication", "appKey": self.app_key, "session": self.session_token}
            self._writer.write((json.dumps(auth_msg) + "\r\n").encode())
            await self._writer.drain()
            
            sub_msg = {
                "op": "marketSubscription",
                "marketFilter": {"marketIds": market_ids},
                "marketDataFilter": {
                    "fields": ["EX_BEST_OFFERS_DISP", "EX_TRADED_VOL"],
                    "ladderLevels": 3
                }
            }
            self._writer.write((json.dumps(sub_msg) + "\r\n").encode())
            await self._writer.drain()
            
            self.is_running = True
            asyncio.create_task(self._handle_stream())
            logger.info(f"[BetfairStream] Connected and subscribed to {len(market_ids)} markets")
        except Exception as e:
            logger.error(f"[BetfairStream] Connection error: {e}")

    async def _handle_stream(self):
        while self.is_running:
            try:
                line = await self._reader.readline()
                if not line: break
                data = json.loads(line.decode())
                
                if data.get("op") == "mcm":
                    for mc in data.get("mc", []):
                        market_id = mc.get("id")
                        for rc in mc.get("rc", []):
                            # NORMALIZATION Logic (Task 1)
                            # Best available to back (atb) -> Bid for us
                            atb = rc.get("atb", [])
                            # Best available to lay (atl) -> Ask for us
                            atl = rc.get("atl", [])
                            
                            best_bid = atb[0][0] if atb else 0.0
                            bid_size = atb[0][1] if atb else 0.0
                            best_ask = atl[0][0] if atl else 0.0
                            ask_size = atl[0][1] if atl else 0.0
                            
                            event = MarketUpdate(
                                platform="betfair",
                                market_id=market_id,
                                best_bid=best_bid,
                                best_ask=best_ask,
                                bid_size=bid_size,
                                ask_size=ask_size,
                                fee_pct=self.fee_pct,
                                raw_data=data
                            )
                            await self._emit(event)
            except Exception as e:
                logger.error(f"[BetfairStream] Stream error: {e}")
                break
        self.is_running = False

    async def disconnect(self):
        self.is_running = False
        if hasattr(self, '_writer'):
            self._writer.close()
            await self._writer.wait_closed()
