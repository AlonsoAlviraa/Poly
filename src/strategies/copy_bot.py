
import asyncio
import logging
from typing import List, Dict, Optional
from src.exchanges.polymarket_clob import PolymarketOrderExecutor
from src.strategies.spy_network import PolygonSpy
from src.utils.notifier import send_telegram_alert

logger = logging.getLogger(__name__)

class CopyBot:
    """
    KOPY KAT v1: Follows 'Whale' wallets via direct On-Chain/PolygonScan polling.
    """

    def __init__(self, target_wallets: List[str], executor: PolymarketOrderExecutor, scale_factor: float = 0.1, max_bet: float = 50.0):
        self.target_wallets = target_wallets
        self.executor = executor
        self.scale_factor = scale_factor
        self.max_bet = max_bet
        self.active = False
        
        # Initialize Spy
        self.spy = PolygonSpy(self.target_wallets, self.on_trade_event)
    
    async def start(self):
        self.active = True
        logger.info(f"[COPY] Started CopyBot observing {len(self.target_wallets)} whales.")
        asyncio.create_task(self.spy.start())
        
    async def stop(self):
        self.active = False
        await self.spy.stop()
        
    async def on_trade_event(self, trade: Dict):
        """
        Called when Spy detects a trade.
        trade = {wallet, type, side, token_id, amount, tx_hash}
        """
        if not self.active: return
        
        wallet = trade['wallet']
        side = trade['side'] # BUY/SELL
        token_id = trade['token_id']
        amount = trade['amount']
        
        # Log and Alert
        logger.info(f"[COPY] 🎯 MATCH: {wallet[:6]} {side} {token_id} (Amt: {amount})")
        
        msg = (
            f"🐋 **WHALE ALERT**\n"
            f"Target: `{wallet[:6]}...`\n"
            f"Action: **{side}**\n"
            f"Asset: `{token_id}`\n"
            f"Size: {amount:.2f} shares\n"
            f"🔗 [View TX](https://polygonscan.com/tx/{trade['tx_hash']})"
        )
        send_telegram_alert(msg)
        
        # Execute Copy
        # We need PRICE to place a LIMIT order. Spy doesn't give price easily (just value/amount).
        # Strategy: Market Order (Fill IO) or Fetch Book first.
        # For Alpha MVP: We ALERT. Auto-execution requires fetching current book to price limit.
        
        # Calculate size.
        # my_size = min(amount * self.scale_factor, self.max_bet) 
        # await self.executor.place_order(...) 
        # IMPLEMENTATION DEFERRED pending user approval on auto-trade.
