
"""
Interactive Audit Bot.
Runs the arbitrage scanner cycle-by-cycle, pausing for user review.
Clean Mode: Suppresses noise, shows only relevant Matches.
"""

import os
import sys

# Silence Progress Bars for HF/TQDM immediately
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1" 
os.environ["TQDM_DISABLE"] = "1"

import asyncio
import logging
import time
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.gamma_client import GammaClient
from src.data.betfair_client import BetfairClient
from src.data.sx_bet_client import SXBetClient
from src.arbitrage.cross_platform_mapper import CrossPlatformMapper, ShadowArbitrageScan
from src.utils.latency_monitor import monitor

# Configure logging to stdout Only - FILTERED
# We want to BLOCK everything except "AuditBot" and specific "MATCH" logs
class MatchFilter(logging.Filter):
    def filter(self, record):
        # Allow AuditBot (our summary)
        if record.name == "AuditBot":
            return True
        # Allow Matches (from CrossPlatformMapper or others)
        if "MATCH!" in record.getMessage() or "MATCH" in record.getMessage():
            return True
        return False

# Setup Handler
handler = logging.StreamHandler(sys.stdout)
handler.addFilter(MatchFilter())

# Configure Basic Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(message)s', # Simplified format
    handlers=[handler],
    force=True
)

# Silence noisy libraries explicitly
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("CrossPlatformMapper").setLevel(logging.INFO) # Keep INFO but Filtered by handler
logging.getLogger("VectorMatcher").setLevel(logging.WARNING) # Silence vector stats

logger = logging.getLogger("AuditBot")


async def main():
    print("🚀 STARTING INTERACTIVE AUDIT BOT (Clean Mode)")
    print("   Press Ctrl+C to exit at any time.\n")
    
    # Init Clients
    bf_client = BetfairClient(use_delay=True)
    if not await bf_client.login():
        print("❌ BF Login Failed. Proceeding with limited functionality...")
        
    poly_client = GammaClient()
    mapper = CrossPlatformMapper(min_ev_threshold=-999) # Show ALL matches even bad EV
    bf_scanner = ShadowArbitrageScan(mapper=mapper, betfair_client=bf_client, min_ev_threshold=-999)
    
    cycle = 0
    while True:
        cycle += 1
        print(f"\n{'='*60}")
        print(f"🔄 CYCLE #{cycle}")
        print(f"{'='*60}")
        
        # 1. Fetch (Polymarket - Switching to robust /markets discovery)
        p_mkts = poly_client.get_all_match_markets(limit=250)
        
        bf_evs = await bf_client.list_events(event_type_ids=['1', '2', '7522'])
        
        print(f"📡 Scanning {len(p_mkts)} Poly vs {len(bf_evs)} Betfair...")
        
        # 2. Analyze
        # This will emit the [Static] MATCH logs to stdout automatically via logger (Filtered)
        opportunities = await bf_scanner.run_scan_cycle(p_mkts, bf_evs)
        
        # 3. Summary
        print(f"\n📊 RESULTADOS CICLO #{cycle}")
        print(f"   contador matches: {len(opportunities)}")
        
        if opportunities:
            print("\n   📜 LISTA DE MATCHES:")
            for opp in opportunities:
                # Reconstruct the log line format user liked
                if hasattr(opp, 'mapping'):
                    print(f"   • {opp.mapping.polymarket_question} == {opp.mapping.betfair_event_name}")
                
        # 5. Pause
        try:
            user_input = input("\n⏯️  [ENTER] Siguiente | [q] Salir: ")
            if user_input.lower() == 'q':
                break
        except KeyboardInterrupt:
            break
            
    print("\n👋 Exiting Audit Mode.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
