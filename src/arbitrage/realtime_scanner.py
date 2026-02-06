
import asyncio
import logging
import time
from typing import Dict, List, Optional, Set, Callable
from collections import defaultdict
from datetime import datetime

from src.data.wss_manager import MarketUpdate, PolymarketStream, BetfairStream, BaseStream
from src.arbitrage.models import MarketMapping, ArbOpportunity
from src.arbitrage.arbitrage_validator import ArbitrageValidator
from src.data.cache_manager import CacheManager
from src.utils.async_patterns import AsyncQueueProcessor
from src.utils.audit_logger import AuditLogger
from src.utils.price_converter import convert_poly_to_decimal, calculate_ev

logger = logging.getLogger("RealTimeScanner")

class RealTimeScanner:
    """
    Event-Driven Scanner for Millisecond Latency Arbitrage.
    Uses AsyncQueueProcessor to decouple ingestion from analysis.
    """
    def __init__(self, poly_stream: PolymarketStream, bf_stream: BetfairStream, sx_stream: Optional[BaseStream] = None, order_manager: Any = None):
        self.poly_stream = poly_stream
        self.bf_stream = bf_stream
        self.sx_stream = sx_stream
        self.order_manager = order_manager
        self.cache_mgr = CacheManager()
        self.audit_logger = AuditLogger()
        
        # Fast Lookups
        self.price_cache: Dict[str, MarketUpdate] = {}
        self.poly_to_bf_map: Dict[str, List[MarketMapping]] = defaultdict(list)
        self.poly_to_sx_map: Dict[str, List[MarketMapping]] = defaultdict(list)
        self.bf_to_poly_map: Dict[str, List[MarketMapping]] = defaultdict(list)
        self.sx_to_poly_map: Dict[str, List[MarketMapping]] = defaultdict(list)
        
        self.callbacks: List[Callable[[ArbOpportunity], None]] = []
        self.running = False
        self._tick_count = 0 
        
        # Core Optimization: Decoupled Queue
        self.processor = AsyncQueueProcessor(self._process_update, num_workers=2)

    def load_mappings(self, mappings: List[MarketMapping] = None):
        if mappings is None:
            mappings = self.cache_mgr.get_all_mappings()
            
        self.poly_to_bf_map.clear()
        self.bf_to_poly_map.clear()
        self.poly_to_sx_map.clear()
        self.sx_to_poly_map.clear()
        
        for m in mappings:
            if m.polymarket_id and m.betfair_market_id:
                self.poly_to_bf_map[m.polymarket_id].append(m)
                self.bf_to_poly_map[m.betfair_market_id].append(m)
            
            sx_id = getattr(m, 'sx_market_id', None)
            if m.polymarket_id and sx_id:
                self.poly_to_sx_map[m.polymarket_id].append(m)
                self.sx_to_poly_map[sx_id].append(m)
        
        logger.info(f"Loaded {len(mappings)} mappings into RealTime Engine.")

    def add_callback(self, cb: Callable):
        self.callbacks.append(cb)

    async def start(self):
        """Start streams and processor."""
        self.running = True
        
        # 1. Subscribe to Streams (Non-blocking)
        self.poly_stream.subscribe(self._on_market_update)
        self.bf_stream.subscribe(self._on_market_update)
        if self.sx_stream:
            self.sx_stream.subscribe(self._on_market_update)
        
        # 2. Start Queue Processor
        await self.processor.start()

        # 3. Connect Streams (Subscription parameters)
        bf_ids = list(self.bf_to_poly_map.keys())
        if bf_ids:
             await self.bf_stream.subscribe_to_markets(bf_ids)

        logger.info("RealTimeScanner Engine Active.")
        
        while self.running:
             await asyncio.sleep(1)

    def _on_market_update(self, update: MarketUpdate):
        """Producer: Pushes to queue."""
        self.processor.put(update)

    async def _process_update(self, update: MarketUpdate):
        """Consumer: Analyzes market update."""
        start_time = asyncio.get_event_loop().time()
        self._tick_count += 1
        self.price_cache[update.market_id] = update
        
        # Latency check (Ingestion)
        ingestion_ms = (start_time - update.timestamp) * 1000
        
        if update.platform == 'polymarket':
            # Check against BF
            for m in self.poly_to_bf_map.get(update.market_id, []):
                bf_update = self.price_cache.get(m.betfair_market_id)
                if bf_update: await self._check_arb(update, bf_update, m)
            # Check against SX
            for m in self.poly_to_sx_map.get(update.market_id, []):
                sx_update = self.price_cache.get(m.sx_market_id)
                if sx_update: await self._check_arb(update, sx_update, m)
                    
        elif update.platform == 'betfair':
            for m in self.bf_to_poly_map.get(update.market_id, []):
                poly_update = self.price_cache.get(m.polymarket_id)
                if poly_update: await self._check_arb(poly_update, update, m)

        elif update.platform == 'sx':
            for m in self.sx_to_poly_map.get(update.market_id, []):
                poly_update = self.price_cache.get(m.polymarket_id)
                if poly_update: await self._check_arb(poly_update, update, m)

        # Performance Monitoring
        process_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        if self._tick_count % 1000 == 0 or ingestion_ms > 100:
            logger.info(f"📊 [METRICS] Ticks: {self._tick_count} | Ingest: {ingestion_ms:.1f}ms | Process: {process_ms:.1f}ms")

    async def _check_arb(self, poly: MarketUpdate, exch: MarketUpdate, mapping: MarketMapping):
        """Professional Arb Calculation and Execution with Mega Debugger."""
        
        # 🛡️ MEGA DEBUGGER: Start Trace
        event = self.audit_logger.get_event(poly.market_id, mapping.betfair_event_name, sport=mapping.sport)
        
        # 1. Price Calculation (Audit Step)
        bf_odds = exch.best_ask
        poly_odds = convert_poly_to_decimal(poly.best_ask)
        
        calc_details = f"Poly Prob: {poly.best_ask:.4f} -> Poly Odds: {poly_odds:.3f} | BF Ask: {bf_odds:.3f}"
        event.add_step("ODDS_CALC", "PASS", calc_details)
        
        # 2. ROI Calculation
        res = ArbitrageValidator.calculate_roi(
            poly_ask = poly.best_ask,
            exch_odds = exch.best_ask,
            fee_rate = 0.02 # BF Commission
        )
        
        win_loss = "SCENARIO WIN (profitable)" if res.is_opportunity else "SCENARIO LOSS/SMALL (no arb)"
        roi_details = f"ROI: {res.roi_percent:.2f}% | {win_loss} | Reason: {res.reason}"
        event.add_step("ROI_CHECK", "PASS" if res.is_opportunity else "SKIP", roi_details)
        
        # Log to Console (User Request: Mega Debugger Visibility)
        logger.info(f"🔍 [MEGA-DEBUGGER] | {mapping.sport.upper()} | {mapping.betfair_event_name}")
        logger.info(f"   ∟ MATH: Poly {poly.best_ask:.2f} ($) -> {poly_odds:.2f} (Odds) vs BF {bf_odds:.2f}")
        logger.info(f"   ∟ RESULT: {res.roi_percent:+.2f}% ROI | {win_loss}")
        
        if res.is_opportunity and res.roi_percent > 0.0:
            event.final_status = "PASS"
            self.audit_logger.log_arb_found(mapping.betfair_event_name, res.roi_percent, mapping.sport)
            
            opp = ArbOpportunity(
                mapping=mapping,
                poly_yes_price=poly.best_ask,
                poly_no_price=0,
                betfair_back_odds=exch.best_bid,
                betfair_lay_odds=exch.best_ask,
                ev_net=res.roi_percent,
                is_profitable=True,
                direction='buy_poly_lay_bf' if exch.platform == 'betfair' else 'buy_poly_lay_sx',
                detected_at=datetime.now(),
                betfair_delayed=False
            )
            
            # Emit to callbacks
            for cb in self.callbacks:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        await cb(opp)
                    else: cb(opp)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

            # 🚀 EXECUTE IF ARBITRAGE IS GOOD
            if self.order_manager:
                await self.order_manager.execute_arbitrage(opp)
        else:
            event.final_status = "NO_ARB"
