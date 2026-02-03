#!/usr/bin/env python3
"""
Full Integration Test for LLM with Arbitrage System.
Tests the complete pipeline: Market Discovery -> AI Analysis -> Alert Generation
"""

import asyncio
import os
import sys
import logging

# Load .env file FIRST
from dotenv import load_dotenv
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai.mimo_client import MiMoClient, AIArbitrageAnalyzer
from src.arbitrage.combinatorial_scanner import LLMDependencyDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)
logger = logging.getLogger(__name__)


async def test_mimo_client():
    """Test basic MiMo client functionality."""
    print("\n" + "=" * 70)
    print("TEST 1: MiMo Client Basic Functionality")
    print("=" * 70)
    
    client = MiMoClient()
    
    if not client.api_key:
        print("❌ API key not found (API_LLM)")
        return False
    
    print(f"✅ API Key loaded: {client.api_key[:15]}...")
    print(f"✅ Model: {client.model}")
    print(f"✅ Base URL: {client.base_url}")
    
    # Test market matching
    result = await client.match_markets(
        market1="Will the Fed raise rates in March 2026?",
        market2="Federal Reserve interest rate increase by end of Q1 2026",
        platform1="Polymarket",
        platform2="Kalshi"
    )
    
    print(f"\nMarket Matching Result:")
    print(f"  Match: {result.get('match')}")
    print(f"  Score: {result.get('score', 0):.0%}")
    print(f"  Reason: {result.get('reason', 'N/A')}")
    
    return True


async def test_ai_analyzer():
    """Test AI Arbitrage Analyzer with caching."""
    print("\n" + "=" * 70)
    print("TEST 2: AI Arbitrage Analyzer with Cache")
    print("=" * 70)
    
    analyzer = AIArbitrageAnalyzer(min_edge_for_ai=0.5, cache_ttl_hours=1.0)
    
    # Test data - simulated cross-platform arb
    market_data = {
        "Polymarket": {
            "question": "Will SpaceX launch Starship to Mars by 2028?",
            "yes_price": 0.25,
            "no_price": 0.78
        },
        "Kalshi": {
            "question": "SpaceX Mars mission before January 1, 2029",
            "yes_price": 0.18,
            "no_price": 0.85
        }
    }
    
    # First call - should hit AI
    print("\n[First Call] Analyzing opportunity...")
    thesis1 = await analyzer.analyze(market_data, edge_pct=7.0)
    
    print(f"  Is Arb: {thesis1.is_arb}")
    print(f"  Confidence: {thesis1.confidence:.0%}")
    print(f"  Action: {thesis1.suggested_action}")
    print(f"  Reasoning: {thesis1.reasoning}")
    print(f"  Cached: {thesis1.cached}")
    print(f"  Tokens Used: {thesis1.tokens_used}")
    
    # Second call - should hit cache
    print("\n[Second Call] Same query (should be cached)...")
    thesis2 = await analyzer.analyze(market_data, edge_pct=7.0)
    print(f"  Cached: {thesis2.cached}")
    
    # Stats
    stats = analyzer.get_stats()
    print(f"\n[Stats]")
    print(f"  Total Requests: {stats['total_requests']}")
    print(f"  Cache Hits: {stats['cache_hits']}")
    print(f"  AI Calls: {stats['ai_calls']}")
    print(f"  Tokens Used: {stats['tokens_used']}")
    print(f"  Cache Hit Rate: {stats['cache_hit_rate']:.0f}%")
    
    return True


def test_llm_dependency_detector():
    """Test LLM Dependency Detector (sync with keyword fallback)."""
    print("\n" + "=" * 70)
    print("TEST 3: LLM Dependency Detector")
    print("=" * 70)
    
    detector = LLMDependencyDetector()
    
    if detector.api_key:
        print(f"✅ API Key loaded: {detector.api_key[:15]}...")
    else:
        print("⚠️ No API key - using keyword fallback")
    
    # Test with related markets
    related1 = "Will the US inflation rate exceed 5% in 2026?"
    related2 = "Will the Federal Reserve raise rates in 2026?"
    
    is_dep, conf = detector.are_markets_dependent(related1, related2)
    print(f"\nRelated Markets Test:")
    print(f"  Market A: {related1[:50]}...")
    print(f"  Market B: {related2[:50]}...")
    print(f"  Dependent: {is_dep}")
    print(f"  Confidence: {conf:.0%}")
    
    # Test with unrelated markets
    unrelated1 = "Will SpaceX reach Mars by 2030?"
    unrelated2 = "Will Barcelona win the Champions League?"
    
    is_dep2, conf2 = detector.are_markets_dependent(unrelated1, unrelated2)
    print(f"\nUnrelated Markets Test:")
    print(f"  Market A: {unrelated1}")
    print(f"  Market B: {unrelated2}")
    print(f"  Dependent: {is_dep2}")
    print(f"  Confidence: {conf2:.0%}")
    
    return True


async def run_all_tests():
    """Run all integration tests."""
    print("\n" + "╔" + "═" * 68 + "╗")
    print("║" + " FULL LLM INTEGRATION TEST ".center(68) + "║")
    print("╚" + "═" * 68 + "╝")
    
    # Check API Key
    api_key = os.getenv('API_LLM')
    if not api_key:
        print("\n❌ ERROR: API_LLM not found in .env")
        print("   Please add: API_LLM=sk-or-v1-your_key_here")
        return
    
    print(f"\n✅ API_LLM found: {api_key[:15]}...")
    
    results = []
    
    # Test 1: MiMo Client
    try:
        results.append(("MiMo Client", await test_mimo_client()))
    except Exception as e:
        print(f"❌ MiMo Client Test Failed: {e}")
        results.append(("MiMo Client", False))
    
    # Test 2: AI Analyzer
    try:
        results.append(("AI Analyzer", await test_ai_analyzer()))
    except Exception as e:
        print(f"❌ AI Analyzer Test Failed: {e}")
        results.append(("AI Analyzer", False))
    
    # Test 3: LLM Dependency Detector
    try:
        results.append(("Dependency Detector", test_llm_dependency_detector()))
    except Exception as e:
        print(f"❌ Dependency Detector Test Failed: {e}")
        results.append(("Dependency Detector", False))
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print("\n⚠️ SOME TESTS FAILED")
    
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
