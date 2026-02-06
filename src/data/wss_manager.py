
import asyncio
import json
import logging
import os
import ssl
from typing import Dict, List, Optional, Callable, Any
from src.utils.async_patterns import RobustConnection
from src.utils.stealth_config import stealth

logger = logging.getLogger(__name__)

class MarketUpdate:
    """Normalized Market Update Event."""
    def __init__(self, platform: str, market_id: str, best_bid: float, best_ask: float, 
                 bid_size: float, ask_size: float, fee_pct: float = 0.0, raw_data: Any = None):
        self.platform = platform
        self.market_id = market_id
        # Apply fees netos (Task 1)
        self.best_bid = best_bid * (1 - fee_pct/100)
        self.best_ask = best_ask * (1 + fee_pct/100)
        self.bid_size = bid_size
        self.ask_size = ask_size
        self.fee_pct = fee_pct
        self.timestamp = asyncio.get_event_loop().time()
        self.raw_data = raw_data

class BaseStream:
    def __init__(self, name: str):
        self.name = name
        self._subscribers = []
        self.is_running = False
        self.robust_conn = RobustConnection(name)

    def subscribe(self, callback: Callable):
        self._subscribers.append(callback)

    async def _emit(self, event: MarketUpdate):
        tasks = []
        for sub in self._subscribers:
            if asyncio.iscoroutinefunction(sub):
                tasks.append(asyncio.create_task(sub(event)))
            else:
                sub(event)
        # We don't await tasks here to keep the read loop hot. 
        # The scanner should ideally use a queue to handle these.

class PolymarketStream(BaseStream):
    def __init__(self, token_ids: List[str]):
        super().__init__("PolymarketStream")
        self.token_ids = token_ids
        self._ws_client = None
        self.fee_pct = float(os.getenv("POLY_FEE_PCT", "0.5"))
        
    async def connect(self):
        import websockets
        self.is_running = True
        
        while self.is_running:
            try:
                ws_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
                    self._ws_client = ws
                    self.robust_conn.reset()
                    
                    sub_msg = {
                        "type": "subscribe",
                        "channel": "orderbook",
                        "market_ids": self.token_ids
                    }
                    await ws.send(json.dumps(sub_msg))
                    logger.info(f"[{self.name}] Connected and subscribed to {len(self.token_ids)} tokens")
                    
                    async for msg in ws:
                        if not self.is_running: break
                        self._on_message(msg)
                        
            except Exception as e:
                if self.is_running:
                    logger.error(f"[{self.name}] Connection lost: {e}")
                    await self.robust_conn.sleep()
                else:
                    break

    def _on_message(self, message):
        try:
            data = json.loads(message)
            if data.get('event_type') != 'book': return # Poly specific filter
            
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
            logger.debug(f"[{self.name}] Parse error: {e}")

    async def disconnect(self):
        self.is_running = False
        if self._ws_client: await self._ws_client.close()

class BetfairStream(BaseStream):
    def __init__(self, session_token: str, app_key: str):
        super().__init__("BetfairStream")
        self.session_token = session_token
        self.app_key = app_key
        self.host = "stream-api.betfair.com"
        self.port = 443
        self.fee_pct = float(os.getenv("BETFAIR_COMMISSION_PCT", "6.5"))
        self._writer = None
        
    async def connect(self, market_ids: Optional[List[str]] = None):
        self.is_running = True
        while self.is_running:
            try:
                context = ssl.create_default_context()
                self._reader, self._writer = await asyncio.open_connection(
                    self.host, self.port, ssl=context
                )
                
                # Auth
                auth_msg = {"op": "authentication", "appKey": self.app_key, "session": self.session_token}
                self._writer.write((json.dumps(auth_msg) + "\r\n").encode())
                await self._writer.drain()
                
                self.robust_conn.reset()
                logger.info(f"[{self.name}] Authenticated.")
                
                if market_ids:
                    await self.subscribe_to_markets(market_ids)
                
                # Start Heartbeat & Read Loop
                await asyncio.gather(
                    self._handle_stream(),
                    self._heartbeat(),
                    return_exceptions=True
                )
            except Exception as e:
                if self.is_running:
                    logger.error(f"[{self.name}] Error: {e}")
                    await self.robust_conn.sleep()
                else: break

    async def _heartbeat(self):
        """Keep connection alive."""
        while self.is_running:
            try:
                await asyncio.sleep(60) # Increased to 60s
                if self._writer:
                    self._writer.write(json.dumps({"op": "heartbeat"}) + "\r\n")
                    await self._writer.drain()
                    logger.debug(f"[{self.name}] KeepAlive sent (Heartbeat)")
            except: break

    async def subscribe_to_markets(self, market_ids: List[str]):
        if not self._writer: return
        sub_msg = {
            "op": "marketSubscription",
            "marketFilter": {"marketIds": market_ids},
            "marketDataFilter": {"fields": ["EX_BEST_OFFERS_DISP"], "ladderLevels": 1}
        }
        self._writer.write((json.dumps(sub_msg) + "\r\n").encode())
        await self._writer.drain()

    async def _handle_stream(self):
        while self.is_running:
            line = await self._reader.readline()
            if not line: break
            data = json.loads(line.decode())
            if data.get("op") == "mcm":
                for mc in data.get("mc", []):
                    market_id = mc.get("id")
                    for rc in mc.get("rc", []):
                        atb = rc.get("atb", [])
                        atl = rc.get("atl", [])
                        best_bid = atb[0][0] if atb else 0.0
                        best_ask = atl[0][0] if atl else 0.0
                        
                        event = MarketUpdate("betfair", market_id, best_bid, best_ask, 0, 0, self.fee_pct, data)
                        asyncio.create_task(self._emit(event))
        self._writer.close()

    async def disconnect(self):
        self.is_running = False
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception: pass

class SXBetPoller(BaseStream):
    def __init__(self, sx_client: Any, market_ids: List[str], interval: float = 2.0):
        super().__init__("SXBetPoller")
        self.sx_client = sx_client
        self.market_ids = market_ids
        self.interval = interval
        
    async def connect(self):
        self.is_running = True
        while self.is_running:
            try:
                if self.market_ids:
                    markets = await self.sx_client.fetch_markets(self.market_ids)
                    self.robust_conn.reset()
                    logger.debug(f"[{self.name}] Heartbeat - Synced {len(markets)} markets")
                    for m in markets:
                        event = MarketUpdate("sx", m.get('marketHash'), m.get('highestBid', 0.0), m.get('lowestAsk', 0.0), 0, 0, 0.0, m)
                        asyncio.create_task(self._emit(event))
                await asyncio.sleep(self.interval)
            except Exception as e:
                logger.error(f"[{self.name}] Error: {e}")
                await self.robust_conn.sleep()

    async def disconnect(self):
        self.is_running = False
