
"""
Shadow Mode Arbitrage Bot.
Run this to detect opportunities between Polymarket, Betfair, and SX Bet (Real Data Only).

Usage:
    python shadow_bot.py            # Run in Verbose Mode (Logs)
    python shadow_bot.py --tui      # Run in TUI Dashboard Mode
"""

import asyncio
import logging
import os
import sys
import time
import warnings
import json
import argparse
from datetime import datetime

# FORCE UTF-8 for Windows Console (Stdout & Stderr)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Suppress annoying libraries
warnings.filterwarnings("ignore")
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# Añadir el path del proyecto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.gamma_client import GammaClient
from src.data.betfair_client import BetfairClient
from src.data.sx_bet_client import SXBetClient, SXBetCategory, PolySXArbitrageScanner
from src.data.wss_manager import PolymarketStream, BetfairStream, MarketUpdate
from src.arbitrage.cross_platform_mapper import CrossPlatformMapper, ShadowArbitrageScan
from src.utils.latency_monitor import monitor
from src.ai.hacha_protocol import HachaProtocol

# Conditional Import for TUI
try:
    from src.ui.dashboard import ArbitrageDashboard
    from rich.live import Live
except ImportError:
    pass

logger = logging.getLogger("ShadowBot")

def setup_logging(use_tui: bool):
    """Configure logging based on mode."""
    handlers = [logging.FileHandler("bot.log", encoding='utf-8')]
    
    if not use_tui:
        # In Verbose mode, we want logs in stdout
        handlers.append(logging.StreamHandler(sys.stdout))
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=handlers,
        force=True # Override previous config
    )
    
    # Silence noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)


def print_audit_report(opp, platform="Betfair", to_logger_only=False):
    """
    Imprime un informe detallado de auditoría para la oportunidad detectada.
    """
    # Adaptador para normalizar objetos de oportunidad de BF y SX
    if platform == "Betfair":
        poly_price = opp.poly_yes_price
        other_price = opp.betfair_back_odds # Odds decimal
        other_lay = opp.betfair_lay_odds
        ev_net = opp.ev_net
        direction = opp.direction
        event_name = opp.mapping.betfair_event_name
        poly_slug = getattr(opp.mapping, 'polymarket_slug', None)
        poly_id = opp.mapping.polymarket_id
        bf_id = opp.mapping.betfair_event_id
        
        # Calcular ROI
        poly_implied = 1/poly_price if poly_price > 0 else 0
        roi_pct = (ev_net / 10.0) * 100
        
        link_line = f"   • BF:   https://www.betfair.es/exchange/plus/football/event/{bf_id}"
        math_line = f"   • Betfair    (Back):    {other_price:.2f}   (Lay: {other_lay:.2f})"
        
    else: # SX Bet
        # SX Opp is a dict
        poly_price = opp.get('poly_yes_price', 0)
        ev_net = opp.get('expected_profit_pct', 0) 
        direction = opp.get('direction')
        event_name = f"{opp.get('sx_label')} (SX)"
        poly_id = opp.get('poly_id')
        poly_slug = None
        sx_hash = opp.get('sx_hash')
        
        poly_implied = 1/poly_price if poly_price > 0 else 0
        roi_pct = ev_net # SX scanner returns % already
        ev_net_eur = (roi_pct / 100) * 10.0 # Approx on 10€
        
        link_line = f"   • SX:   https://sx.bet/market/{sx_hash}"
        math_line = f"   • SX Bet     (Bid/Ask): {opp.get('sx_best_bid'):.3f} / {opp.get('sx_best_ask'):.3f}"

    # Links
    poly_link = "https://polymarket.com"
    if poly_slug:
         poly_link = f"https://polymarket.com/event/{poly_slug}"
    else:
         poly_link = f"https://polymarket.com/market/{poly_id}"

    log_msg = (
        f"\n{'═'*76}\n"
        f"🚨 ARBITRAJE DETECTADO ({platform}): {event_name}\n"
        f"═"*76 + "\n"
        f"📊 LA MATEMÁTICA:\n"
        f"   • Polymarket (Buy YES): ${poly_price:.3f}  (Implied Odds: {poly_implied:.2f})\n"
        f"{math_line}\n"
        f"   • EV Neto (Stake 10€):  €{ev_net:.2f}\n" if platform == "Betfair" else f"   • Spread Estimado:      {roi_pct:.2f}%\n"
        f"   ----------------------------------------------------\n"
        f"   • Inversión Simulada:   €100.00\n"
        f"   • Retorno Proyectado:   €{100 + ((ev_net/10.0)*100 if platform=='Betfair' else roi_pct):.2f}\n"
        f"\n🔗 VERIFICACIÓN MANUAL (Deep Links):\n"
        f"   • Poly: {poly_link}\n"
        f"{link_line}\n"
        f"\n⚡ EJECUCIÓN:\n"
        f"   • Acción Recomendada: {direction}\n"
        f"{'═'*76}\n"
    )
    
    logger.info(log_msg)


def adapt_gamma_events(events):
    """Adapt Gamma API events to flat markets list for Mapper."""
    markets = []
    for e in events:
        slug = e.get('slug')
        title = e.get('title')
        
        for m in e.get('markets', []):
            # Try to get YES price
            yes_price = 0.5
            try:
                # outcomePrices is often JSON string '["0.5", "0.5"]'
                prices = json.loads(m.get('outcomePrices', '[]'))
                if prices:
                    yes_price = float(prices[0])
            except:
                pass
            
            markets.append({
                'id': m.get('id'),
                'condition_id': m.get('condition_id') or m.get('id'), # SX/Gamma compat
                'question': m.get('question') or title,
                'slug': slug,
                'yes_price': yes_price,
                'startDate': e.get('startDate'), # Essential for Time Window Validation
                'tokens': [{'price': yes_price}, {'price': 1-yes_price}] # For SX scanner
            })
    return markets

# === HYBRID ARCHITECTURE ===

class HybridBot:
    def __init__(self, poly_client, bf_client, sx_client, bf_scanner, sx_scanner, dashboard=None):
        self.poly_client = poly_client
        self.bf_client = bf_client
        self.sx_client = sx_client
        self.bf_scanner = bf_scanner
        self.sx_scanner = sx_scanner
        self.dashboard = dashboard
        
        # State
        self.active_mappings = {} # {poly_id: {bf_market_id, ...}}
        self.ws_poly = None
        self.ws_bf = None
        
    async def start_streams(self):
        """Initialize WebSocket Streams"""
        # Polymarket Stream (CLOB) - Requires IDs
        # We start it empty or with found IDs later
        # self.ws_poly = PolymarketStream(token_ids=[...])
        
        if self.bf_client._session:
             # Need App Key
             self.ws_bf = BetfairStream(
                 session_token=self.bf_client._session.ssoid, 
                 app_key=self.bf_client.app_key
             )
             await self.ws_bf.connect() # Initial Connect
             
        else:
            logger.warning("⚠️ No WS Betfair: Missing Session Token")

    async def handle_bf_update(self, update: MarketUpdate):
        """Handle Real-Time Price Update from Betfair"""
        # Logic: Find which Poly market maps to this BF market
        if update.market_id in self.active_mappings:
            opp = self.active_mappings[update.market_id] # This is the ArbOpportunity object
            
            # Recalculate EV with new BF prices
            # Update object state
            opp.betfair_back_odds = update.best_bid # Start seeing 'bid' as 'back' for us if we are makers, but here update.best_bid is what is available to BACK.
            # update.best_bid from normalized stream usually means "Best Move available".
            # Let's map normalized fields:
            # best_bid (BF Stream ATB) -> Available to Back -> We can BUY at this price.
            # best_ask (BF Stream ATL) -> Available to Lay -> We can SELL at this price.
            
            opp.betfair_back_odds = update.best_bid
            opp.betfair_lay_odds = update.best_ask
            
            # Re-Calculate EV
            # Simplified EV calc (assuming Poly price static for this tick)
            # EV = (stake/poly_price) - stake (if lost) ... logic from scanner
            # reusing scanner logic would be best but let's do quick approx
            if opp.poly_yes_price > 0:
                imp_prob = 1 / update.best_bid if update.best_bid > 0 else 0
                fw_profit = (10 / opp.poly_yes_price) * 0.98 # Poly win 
                # Hedge cost = 10 * (1/bf_odds)? No, manual ARB math:
                # We Buy YES @ Poly. We Lay YES @ BF.
                # Profit = (Stake/Poly_Price) - Stake_BF_Risk
                # ... avoiding full math implementation here.
                # Just update the "Info" and log "Tick"
                pass 

            if self.dashboard:
                 # Re-Add to dashboard to show activity (Scrolling Matrix style)
                 # Only if price changed significantly?
                 self.dashboard.add_opportunity({
                        'event': f"{opp.mapping.betfair_event_name} (⏱️)",
                        'market': 'Live Update',
                        'poly_price': opp.poly_yes_price,
                        'bf_back': update.best_bid,
                        'bf_lay': update.best_ask,
                        'ev': opp.ev_net, # Keeping old EV for now or would need re-compute
                        'roi': (opp.ev_net / 10.0) * 100,
                        'source': 'BF_WS'
                    })
                 self.dashboard.update_latency('betfair', 5.0) # Mock fast latency for WS push

    async def run_discovery_cycle(self, scan_count: int):
        """Standard Polling Cycle (Discovery)"""
        start_time = time.time()
        
        if self.dashboard:
             self.dashboard.update_cycle(scan_count, 0, 0)
        else:
             logger.info(f"\n--- 🔄 Ciclo de Escaneo #{scan_count} (Hybrid) ---")
        
        # A. Poly Discovery
        p_start = time.time()
        raw_events = self.poly_client.get_match_events(limit=500) 
        poly_markets = adapt_gamma_events(raw_events)
        p_lat = (time.time() - p_start) * 1000
        monitor.record('polymarket', p_lat)
        if self.dashboard: self.dashboard.update_latency('polymarket', p_lat)

        # B. Betfair Discovery
        b_start = time.time()
        bf_events = await self.bf_client.list_events(event_type_ids=['1', '2', '7522']) 
        b_lat = (time.time() - b_start) * 1000
        monitor.record('betfair', b_lat)
        if self.dashboard: self.dashboard.update_latency('betfair', b_lat)
        
        if self.dashboard:
            self.dashboard.update_cycle(scan_count, len(poly_markets), len(bf_events))
            
        # D. Analysis (Populates Active Mappings)
        if not self.dashboard: logger.info(f"🧠 [AI] Analizando Poly vs Betfair...")
        bf_opps = await self.bf_scanner.run_scan_cycle(poly_markets, bf_events)
        
        # Populate new WS subscriptions
        new_market_ids = []
        
        # Process Opps
        found_any = False
        if bf_opps:
            found_any = True
            for opp in bf_opps:
                # Add to WS Subscription
                mid = opp.mapping.betfair_market_id
                if mid:
                    if mid not in self.active_mappings:
                        new_market_ids.append(mid)
                        self.active_mappings[mid] = opp # Track active arbs
                    
                print_audit_report(opp, platform="Betfair")
                # ... (Dashboard Updates) ...
        
        # Send WS Subscriptions
        if new_market_ids and self.ws_bf:
            await self.ws_bf.subscribe_to_markets(new_market_ids)
            
        if not found_any and not self.dashboard:
            logger.info("ℹ️ No se detectaron oportunidades > umbral.")
            
        await asyncio.sleep(60) # Discovery every 60s

    async def run_loop(self, live_ctx=None):
        scan_count = 0
        await self.start_streams()
        
        while True:
            try:
                scan_count += 1
                await self.run_discovery_cycle(scan_count)
                if live_ctx and self.dashboard:
                    live_ctx.update(self.dashboard.render())
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"❌ Error CRÍTICO en ciclo: {str(e)}")
                await asyncio.sleep(5)
        
        # Cleanup
        if self.ws_poly: await self.ws_poly.disconnect()
        if self.ws_bf: await self.ws_bf.disconnect()


async def main():
    parser = argparse.ArgumentParser(description='Shadow Bot')
    parser.add_argument('--tui', action='store_true', help='Use TUI Dashboard')
    args = parser.parse_args()
    
    use_tui = args.tui
    setup_logging(use_tui)
    
    logger.info("🚀 Iniciando Shadow Bot")
    
    # Init Clients
    logger.info("📡 Conectando a APIs...")
    bf_client = BetfairClient(use_delay=True)
    try:
        logged_in = await bf_client.login()
        if not logged_in:
             logger.critical("⛔ FATAL: Betfair Login Failed.")
             sys.exit(1)
    except Exception as e:
        logger.critical(f"⛔ FATAL: Betfair Connection Error: {e}")
        sys.exit(1)
        
    poly_client = GammaClient()
    sx_client = SXBetClient()
    mapper = CrossPlatformMapper(min_ev_threshold=0.01)
    
    bf_scanner = ShadowArbitrageScan(mapper=mapper, betfair_client=bf_client, min_ev_threshold=0.01)
    sx_scanner = PolySXArbitrageScanner(sx_client=sx_client, min_spread_pct=0.5)

    # Hybrid Bot
    dashboard = ArbitrageDashboard() if use_tui else None
    bot = HybridBot(poly_client, bf_client, sx_client, bf_scanner, sx_scanner, dashboard)

    try:
        if use_tui:
            with Live(dashboard.render(), refresh_per_second=4, screen=True) as live:
                await bot.run_loop(live_ctx=live)
        else:
            await bot.run_loop()
            
    except KeyboardInterrupt:
        pass 
    finally:
        print("\n🛑 Apagando sistemas...")
        await sx_client.close()
        print("✅ Shutdown Completo.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
