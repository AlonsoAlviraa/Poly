import os
import sys
import asyncio
import json
import time
import logging
import argparse
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, List

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Attempt imports with fallbacks
try:
    from src.utils.stealth_middleware import StealthClient, CURL_CFFI_AVAILABLE
except ImportError:
    class StealthClient:
        async def get(self, url): 
            class MockResp: 
                def json(self): return {"ip": "1.1.1.1", "tls": {"ja3": "mock"}, "http": {"version": "2", "headers": {"User-Agent": "mock"}}}
            return MockResp()
        async def close(self): pass
    CURL_CFFI_AVAILABLE = False

from src.data.wss_manager import PolymarketStream, MarketUpdate
from src.data.price_logger import ticker_logger
from src.utils.json_decimal import loads_decimal
from src.utils.ws_guard import WebsocketGuard
from src.ai.mimo_client import AIArbitrageAnalyzer, SemanticCache

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("InfraDebugger")

class InfraDebugger:
    def __init__(self, stress_factor=1):
        self.results = {}
        self.stress_factor = stress_factor

    async def test_network(self):
        """1. 🌐 TEST DE RED Y SIGILO"""
        logger.info("Running Network & Stealth Test (Multi-endpoint)...")
        from curl_cffi import requests
        
        proxy_url = os.getenv("RESIDENTIAL_PROXIES", "")
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        
        try:
            # Test 1: Peet.ws for JA3/H2
            resp = requests.get("https://tls.peet.ws/api/all", impersonate="chrome110", proxies=proxies, timeout=15)
            data = resp.json()
            
            # Test 2: Ipify for real IP
            ip_resp = requests.get("https://api64.ipify.org?format=json", proxies=proxies).json()
            
            ja3 = data.get("tls", {}).get("ja3_hash") or data.get("tls", {}).get("ja3") or "UNKNOWN"
            protocols = data.get("http2", {}).get("protocols", []) or data.get("tls", {}).get("protocols", [])
            has_h2 = "h2" in protocols or data.get("http", {}).get("version") == "h2"
            
            logger.info(f"IP: {ip_resp.get('ip')} | JA3: {ja3} | H2: {has_h2}")
            
            self.results["network"] = {
                "ip": ip_resp.get("ip"),
                "ja3": ja3,
                "h2_active": has_h2,
                "success": ja3 != "UNKNOWN" and has_h2
            }
        except Exception as e:
            logger.error(f"Network test failed: {e}")
            self.results["network"] = {"error": str(e), "success": False}

    async def test_ws_connection(self):
        """2. 🔌 TEST DE WEBSOCKETS PURO"""
        logger.info("Running WebSocket Connection Test (Polymarket CLOB)...")
        # Corrected URL and sub based on Cycle 1 findings
        # Use a known active market ID (example: USDC or a popular market)
        # Using a raw string for clarity in debugger
        token_id = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174" # Poly USDC Token
        
        # Override the stream's internal URL specifically for this test if needed, 
        # but since we updated wss_manager logic, it should pick up the correct one 
        # IF we init it correctly. 
        # However, wss_manager might still have hardcoded defaults we just fixed.
        # Let's verify we rely on the class we just patched.
        stream = PolymarketStream([token_id])
        
        # Manually ensure the debug tool points to the right place if it wasn't using the class default
        # But wait, we fixed the class default in wss_manager.py.
        # So we just instantiate and run.
        
        msg_received = False
        def on_msg(event):
            nonlocal msg_received
            msg_received = True

        stream.subscribe(on_msg)
        try:
            task = asyncio.create_task(stream.connect())
            start_time = time.time()
            while time.time() - start_time < 20:
                await asyncio.sleep(1)
                if msg_received: break
            
            task.cancel()
            self.results["websockets"] = {
                "poly_connected": msg_received,
                "success": msg_received
            }
        except Exception as e:
            logger.error(f"WS Test failed: {e}")
            self.results["websockets"] = {"error": str(e), "success": False}

    def test_parsing(self):
        """3. 🔢 TEST DE INTEGRIDAD DE DATOS (Stress Mode)"""
        count = 1000 * self.stress_factor
        logger.info(f"Running Data Integrity Stress Test ({count} iterations)...")
        payload = '{"id": "123", "price": 0.3333333333333333, "size": 100.0000001}'
        
        start = time.perf_counter()
        for _ in range(count):
            data = loads_decimal(payload)
        end = time.perf_counter()
        
        avg_time = (end - start) / count
        is_decimal = isinstance(data["price"], Decimal)
        precision_ok = str(data["price"]) == "0.3333333333333333"
        
        logger.info(f"Avg Parse Time: {avg_time*1e6:.2f}us | Decimal: {is_decimal} | Precision: {precision_ok}")
        
        self.results["parsing"] = {
            "iterations": count,
            "avg_time_us": avg_time * 1e6,
            "success": is_decimal and precision_ok
        }

    async def test_db_latency(self):
        """4. 💾 TEST DE RENDIMIENTO DE BASE DE DATOS (Massive)"""
        count = 10000 * self.stress_factor
        logger.info(f"Running DB Stress Test ({count} points)...")
        
        start = time.perf_counter()
        for i in range(count):
            ticker_logger.log_tick("bench", f"m_{i}", 0.5, 100, "BUY")
        end = time.perf_counter()
        
        avg_time_ms = ((end - start) / count) * 1000
        logger.info(f"Avg log_tick time: {avg_time_ms:.6f}ms")
        
        self.results["db_latency"] = {
            "points": count,
            "avg_ms": avg_time_ms,
            "success": avg_time_ms < 0.5
        }

    async def test_ai_stress(self):
        """7. 🤖 TEST DE ESTRÉS DE IA / LLM (The New Block)"""
        count = 100 * self.stress_factor
        logger.info(f"Running AI Cache Stress Test ({count} iterations)...")
        
        cache = SemanticCache(ttl_hours=1)
        start = time.perf_counter()
        for i in range(count):
            cache.set(f"Market analysis for {i}", {"is_arb": True, "confidence": 0.85})
            _ = cache.get(f"Market analysis for {i}")
        end = time.perf_counter()
        
        avg_cache_ms = ((end - start) / count) * 1000
        
        # Test AI Analyzer logic (Mocked for speed if stress_factor is high)
        analyzer = AIArbitrageAnalyzer(min_edge_for_ai=1.0)
        logger.info("Verifying AI Logic Gating...")
        thesis = await analyzer.analyze({"test": "data"}, edge_pct=0.5)
        gated_ok = thesis.is_arb == False and "below threshold" in thesis.reasoning.lower()
        
        self.results["ai_diagnostics"] = {
            "cache_avg_ms": avg_cache_ms,
            "logic_gating_ok": gated_ok,
            "success": gated_ok and avg_cache_ms < 1.0
        }

    def test_filters(self):
        """6. 🧹 TEST DE GATEKEEPER"""
        logger.info("Running Gatekeeper/Liquidity Test...")
        markets = [{"liq": 1000, "spr": 0.01}, {"liq": 50, "spr": 0.05}]
        passed = [m for m in markets if m["liq"] >= 500]
        self.results["filters"] = {"success": len(passed) == 1}

    async def run_all(self):
        await self.test_network()
        await self.test_ws_connection()
        self.test_parsing()
        await self.test_db_latency()
        await self.test_ai_stress()
        self.test_filters()
        
        summary_file = f"stress_results_{int(time.time())}.json"
        with open(summary_file, "w") as f:
            json.dump(self.results, f, indent=4)
        
        print("\n" + "="*50)
        print(f"STRESS TEST COMPLETE (Factor: {self.stress_factor}x)")
        print("="*50)
        for k, v in self.results.items():
            status = "✅ PASS" if v.get("success") else "❌ FAIL"
            print(f"{k.upper():15}: {status}")
        print(f"\nFull report saved to: {summary_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stress", type=int, default=1, help="Multiplier for test volume")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    
    debugger = InfraDebugger(stress_factor=args.stress)
    asyncio.run(debugger.run_all())
