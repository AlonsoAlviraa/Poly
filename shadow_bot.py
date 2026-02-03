"""
Shadow Mode Arbitrage Bot.
Run this to detect opportunities between Polymarket and Betfair without real-world risk.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

# Añadir el path del proyecto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.gamma_client import GammaClient
from src.data.betfair_client import BetfairClient, BetfairSimulator
from src.arbitrage.cross_platform_mapper import CrossPlatformMapper, ShadowArbitrageScan
from src.utils.latency_monitor import monitor
from src.ai.hacha_protocol import HachaProtocol

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("shadow_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ShadowBot")

async def main():
    logger.info("🚀 Iniciando Shadow Bot (Polymarket <-> Betfair)")
    
    # 1. Inicializar Clientes
    # Usar simulador si no hay credenciales reales para el demo, 
    # pero intentar cargar las reales primero.
    use_simulation = os.getenv('BETFAIR_USER') is None
    
    if use_simulation:
        logger.warning("⚠️ No se detectaron credenciales de Betfair. Usando SIMULADOR.")
        bf_client = BetfairSimulator(use_delay=True)
    else:
        bf_client = BetfairClient(use_delay=True)
    
    poly_client = GammaClient() # Cliente Polymarket
    
    # 2. Configurar Mapper con Protocolo Hacha (AI Optimization)
    hacha = HachaProtocol(min_ev_threshold=0.5)
    mapper = CrossPlatformMapper(min_ev_threshold=0.5)
    
    scanner = ShadowArbitrageScan(
        mapper=mapper,
        betfair_client=bf_client,
        min_ev_threshold=0.5 # Mínimo 0.50€ de beneficio teórico
    )

    logger.info("✅ Clientes listos. Iniciando ciclo de escaneo (Ctrl+C para detener).")

    scan_count = 0
    while True:
        try:
            start_time = time.time()
            scan_count += 1
            logger.info(f"\n--- 🔄 Ciclo de Escaneo #{scan_count} ---")
            
            # A. Obtener Mercados de Polymarket
            logger.info("📡 Obteniendo mercados de Polymarket...")
            p_start = time.time()
            # Simplificamos para el demo, obteniendo mercados de deportes
            poly_markets = [
                {'id': '0x1', 'question': 'Real Madrid vs Barcelona - Ganador', 'yes_price': 0.52},
                {'id': '0x2', 'question': 'Manchester United vs Liverpool - Ganador', 'yes_price': 0.40}
            ]
            monitor.record('polymarket', (time.time() - p_start) * 1000)

            # B. Obtener Eventos de Betfair
            logger.info("📡 Obteniendo eventos de Betfair...")
            b_start = time.time()
            await bf_client.login()
            bf_events = await bf_client.list_events(event_type_ids=['1']) # Soccer
            monitor.record('betfair', (time.time() - b_start) * 1000)

            # C. Escanear por Arbitraje (Usa AI + Math Filter)
            logger.info(f"🧠 Buscando matches entre {len(poly_markets)} mercados Poly y {len(bf_events)} eventos Betfair...")
            
            l_start = time.time()
            opportunities = await scanner.run_scan_cycle(poly_markets, bf_events)
            monitor.record('llm', (time.time() - l_start) * 1000)

            # D. Reportar Resultados
            if opportunities:
                for opp in opportunities:
                    logger.info(f"💰 [OPORTUNIDAD] {opp.mapping.betfair_event_name}")
                    logger.info(f"   👉 Beneficio teórico: {opp.ev_net:.2f}€")
                    logger.info(f"   👉 Acción: {opp.direction}")
            else:
                logger.info("ℹ️ No se encontraron oportunidades en este ciclo.")

            # E. Métricas de Salud
            health = monitor.get_report()
            logger.info(f"⏱️ Latencias: PM={health.get('polymarket',{}).get('avg_ms')}ms, BF={health.get('betfair',{}).get('avg_ms')}ms, AI={health.get('llm',{}).get('avg_ms')}ms")
            
            # Esperar 30 segundos entre ciclos
            await asyncio.sleep(30)

        except KeyboardInterrupt:
            logger.info("🛑 Bot detenido por el usuario.")
            break
        except Exception as e:
            logger.error(f"❌ Error en el ciclo: {str(e)}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    import time
    asyncio.run(main())
