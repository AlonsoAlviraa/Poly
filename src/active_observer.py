"""
Active Observer Mode - Phase 1, 2, 3 implementation.
Handles shadow runs, human validation via Telegram, and latency stress testing.
"""

import asyncio
import logging
import os
import csv
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

# Internal imports
from src.data.gamma_client import GammaClient
from src.data.betfair_client import BetfairClient, BetfairSimulator
from src.arbitrage.cross_platform_mapper import CrossPlatformMapper, ArbOpportunity
from src.utils.latency_monitor import monitor
from src.alerts.telegram_notifier import TelegramNotifier, Alert

logger = logging.getLogger("ObserverBot")

class ActiveObserverBot:
    """
    Implements the 3-phase protocol:
    1. Shadow Run (CSV Logging & 15m price verification)
    2. MiMo Thesis Validation (Telegram human feedback)
    3. Latency Stress-Test (<500ms target)
    """
    
    CSV_FILE = "opportunities_found.csv"
    TRUST_THRESHOLD = 50 # 50 consecutive hits for full automation
    
    def __init__(self, use_simulator: bool = True):
        self.poly = GammaClient()
        self.bf = BetfairSimulator(use_delay=True) if use_simulator else BetfairClient(use_delay=True)
        self.mapper = CrossPlatformMapper(min_ev_threshold=0.5)
        self.telegram = TelegramNotifier()
        
        # Accuracy tracking
        self.consecutive_hits = 0
        self.trust_ai = False
        
        # Opportunity tracking for 15m verification
        self.pending_verification: List[Dict] = []
        
        # Ensure CSV exists
        self._init_csv()

    def _init_csv(self):
        if not os.path.exists(self.CSV_FILE):
            with open(self.CSV_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'event', 'poly_price', 'bf_odds', 
                    'ev_net', 'sentiment_score', 'mapping_confidence', 
                    'verified_profit', 'latency_ms'
                ])

    async def log_to_csv(self, opp: ArbOpportunity, latency_ms: float):
        """Phase 1: Record detection and metadata."""
        sentiment = await self.get_sentiment_score(opp.mapping.polymarket_question)
        
        with open(self.CSV_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                opp.detected_at.isoformat(),
                opp.mapping.betfair_event_name,
                opp.poly_yes_price,
                opp.betfair_back_odds,
                opp.ev_net,
                sentiment,
                opp.mapping.confidence,
                "PENDING",
                f"{latency_ms:.2f}"
            ])
            
        # Add to tracking queue for verification in 15 mins
        self.pending_verification.append({
            'opp': opp,
            'time': datetime.now(),
            'initial_bf_odds': opp.betfair_back_odds
        })

    async def get_sentiment_score(self, question: str) -> float:
        """Mocked Sentiment Engine."""
        import random
        return round(0.5 + random.random() * 0.4, 2) # 0.5 to 0.9

    async def verify_loop(self):
        """Phase 1: Check price movement after 15 minutes."""
        while True:
            try:
                now = datetime.now()
                # Verification logic for shadow runs
                to_verify = [p for p in self.pending_verification if now - p['time'] >= timedelta(minutes=15)]
                
                for item in to_verify:
                    opp = item['opp']
                    # Fetch fresh prices to see if price moved in our direction
                    prices = await self.bf.get_prices([opp.mapping.betfair_market_id])
                    if prices:
                        current_back = max((p.back_price for p in prices), default=0)
                        diff = current_back - item['initial_bf_odds']
                        
                        logger.info(f"🔍 Verified Event: {opp.mapping.betfair_event_name} | Diff: {diff:.2f}")
                        
                        # Update hit counter for Phase 2 trust
                        if diff >= 0:
                            self.consecutive_hits += 1
                            if self.consecutive_hits >= self.TRUST_THRESHOLD:
                                self.trust_ai = True
                                self.telegram.send_message("🔓 <b>AI TRUSTED</b>: 50 consecutive hits. Full automation ready.")
                        else:
                            self.consecutive_hits = 0
                            
                    self.pending_verification.remove(item)
            except Exception as e:
                logger.error(f"Verify loop error: {e}")
            await asyncio.sleep(60)

    async def request_human_validation(self, opp: ArbOpportunity) -> bool:

        """Phase 2: Telegram Human-in-the-loop with Polling."""
        if self.trust_ai:
            return True
            
        mapping_id = opp.mapping.polymarket_id[:6]
        message = (
            f"🧠 <b>MIMO VALIDATION</b>\n\n"
            f"Poly: {opp.mapping.polymarket_question}\n"
            f"BF: {opp.mapping.betfair_event_name}\n"
            f"Confidence: {opp.mapping.confidence:.0%}\n\n"
            f"¿Es correcto el mapeo?\n"
            f"👉 Envía <code>/ok_{mapping_id}</code> para aceptar\n"
            f"👉 Envía <code>/no</code> para rechazar"
        )
        
        self.telegram.send_message(message)
        logger.info(f"Waiting for Telegram validation: /ok_{mapping_id}")

        # Polling for response (Timeout 60s)
        timeout = 60
        start_poll = time.time()
        while time.time() - start_poll < timeout:
            try:
                import httpx
                url = f"https://api.telegram.org/bot{self.telegram.bot_token}/getUpdates"
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, params={'offset': -1})
                    if resp.status_code == 200:
                        updates = resp.json().get('result', [])
                        if updates:
                            text = updates[0].get('message', {}).get('text', '')
                            if f"/ok_{mapping_id}" in text:
                                logger.info(f"✅ Validation ACCEPTED by user for {mapping_id}")
                                return True
                            if "/no" in text:
                                logger.info(f"❌ Validation REJECTED by user")
                                return False
            except Exception as e:
                logger.error(f"Polling error: {e}")
            
            await asyncio.sleep(2)
            
        logger.warning(f"⏰ Validation TIMEOUT for {mapping_id}. Defaulting to REJECT.")
        return False

    async def run_cycle(self):
        """Main execution cycle with Phase 3 Stress-Test."""
        start_ts = time.time()
        
        # 1. Capture Market Data (Signal)
        # Using simulator events for demo
        try:
            await self.bf.login()
            bf_events = await self.bf.list_events(event_type_ids=['1'])
            
            # Simple mock markets for Phase 1 testing
            poly_markets = [
                {
                    'id': f'poly_{int(time.time())}',
                    'question': 'Will Real Madrid win tonight?',
                    'yes_price': 0.65
                }
            ]
            
            for poly in poly_markets:
                # Execution Logic
                mapping = await self.mapper.map_market(
                    poly['question'], poly['id'], bf_events, poly['yes_price']
                )
                
                if mapping:
                    # Get prices
                    bf_prices = await self.bf.get_prices([mapping.betfair_market_id])
                    best_back = max((p.back_price for p in bf_prices), default=0)
                    
                    ev_net, is_profitable = self.bf.calculate_ev_net(
                        poly['yes_price'], best_back
                    )
                    
                    opp = ArbOpportunity(
                        mapping=mapping,
                        poly_yes_price=poly['yes_price'],
                        poly_no_price=1-poly['yes_price'],
                        betfair_back_odds=best_back,
                        betfair_lay_odds=best_back+0.02,
                        ev_net=ev_net,
                        is_profitable=is_profitable,
                        direction='buy_poly_back_bf',
                        detected_at=datetime.now()
                    )
                    
                    end_ts = time.time()
                    latency_ms = (end_ts - start_ts) * 1000
                    
                    # Phase 3: Stress-Test
                    monitor.record('overall_scan', latency_ms)
                    if latency_ms > 500:
                        logger.warning(f"🚨 LATENCY CRITICAL: {latency_ms:.2f}ms")
                    
                    # Phase 1: Shadow Run Log
                    await self.log_to_csv(opp, latency_ms)
                    
                    # Phase 2: Human Validation
                    if await self.request_human_validation(opp):
                        logger.info(f"🚀 Opportunity tracked and validated: {opp.mapping.betfair_event_name}")
                    
        except Exception as e:
            logger.error(f"Cycle error: {e}")

    async def start(self):
        logger.info("📡 Iniciando Active Observer Core...")
        asyncio.create_task(self.verify_loop())
        
        while True:
            await self.run_cycle()
            await asyncio.sleep(30)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot = ActiveObserverBot(use_simulator=True)
    asyncio.run(bot.start())
