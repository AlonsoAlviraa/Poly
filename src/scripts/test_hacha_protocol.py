#!/usr/bin/env python3
"""
Test de integración completo del Protocolo Hacha.
Simula oportunidades de arbitraje reales y mide ahorros.
"""

import asyncio
import os
import sys
import time

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.ai.hacha_protocol import (
    HachaProtocol, 
    HybridSemanticCache,
    MathematicalFilter, 
    ModelCascade
)


async def test_hacha_protocol():
    """Test completo del Protocolo Hacha."""
    print("\n╔" + "═" * 68 + "╗")
    print("║" + " PROTOCOL 'HACHA' - FULL TEST ".center(68) + "║")
    print("╚" + "═" * 68 + "╝")
    
    api_key = os.getenv('API_LLM')
    if not api_key:
        print("\n❌ API_LLM not found in .env")
        return
    
    print(f"\n✅ API Key: {api_key[:15]}...")
    
    # ============== TEST 1: Mathematical Filter ==============
    print("\n" + "=" * 60)
    print("TEST 1: Mathematical Pre-Filter")
    print("=" * 60)
    
    math_filter = MathematicalFilter(
        min_ev_threshold=0.5,  # 0.5% minimum
        fee_estimate=0.5,
        slippage_buffer=0.3
    )
    
    # Test cases
    test_cases = [
        # (buy_prices, guaranteed_payout, expected_pass)
        ([0.45, 0.50], 1.0, True),    # 5.3% gross = 4.5% net -> PASS
        ([0.48, 0.48], 1.0, True),    # 4.2% gross = 3.4% net -> PASS
        ([0.50, 0.49], 1.0, False),   # 1.0% gross = 0.2% net -> FAIL
        ([0.52, 0.50], 1.0, False),   # -2% gross -> FAIL
    ]
    
    for i, (prices, payout, expected) in enumerate(test_cases):
        ev_net, passed = math_filter.calculate_ev_net(prices, payout)
        status = "✅ PASS" if passed == expected else "❌ FAIL"
        print(f"  Case {i+1}: prices={prices}, EV={ev_net:.2f}%, pass={passed} {status}")
    
    # Kelly sizing test
    print("\n  Kelly Sizing Tests:")
    kelly_size = math_filter.kelly_size(ev_pct=3.0, win_prob=0.9, bankroll=1000)
    print(f"    3% EV, 90% win prob, $1000 bankroll -> Size: ${kelly_size:.2f}")
    
    kelly_size = math_filter.kelly_size(ev_pct=10.0, win_prob=0.95, bankroll=5000)
    print(f"    10% EV, 95% win prob, $5000 bankroll -> Size: ${kelly_size:.2f}")
    
    print(f"\n  Filter Stats: {math_filter.get_stats()}")
    
    # ============== TEST 2: Hybrid Cache ==============
    print("\n" + "=" * 60)
    print("TEST 2: Hybrid Semantic Cache")
    print("=" * 60)
    
    cache = HybridSemanticCache(
        semantic_threshold=0.90,
        default_ttl_seconds=3600
    )
    
    # Test exact match
    test_data = {"is_arb": True, "confidence": 0.85, "reason": "Test arb"}
    cache.set("Will BTC hit $100k by end of 2026?", test_data)
    
    # Exact match
    result = cache.get("Will BTC hit $100k by end of 2026?")
    print(f"\n  Exact match test:")
    print(f"    Query: 'Will BTC hit $100k by end of 2026?'")
    print(f"    Result: {result}")
    print(f"    Status: {'✅ HIT' if result else '❌ MISS'}")
    
    # Semantic match (similar query) - requires sentence-transformers
    result2 = cache.get("Bitcoin to $100,000 before January 2027")
    print(f"\n  Semantic match test:")
    print(f"    Query: 'Bitcoin to $100,000 before January 2027'")
    print(f"    Result: {result2}")
    print(f"    Status: {'✅ HIT' if result2 else '⚠️ MISS (needs sentence-transformers)'}")
    
    # Cache miss
    result3 = cache.get("Will ETH flip BTC?")
    print(f"\n  Cache miss test:")
    print(f"    Query: 'Will ETH flip BTC?'")
    print(f"    Result: {result3}")
    print(f"    Status: {'✅ MISS (expected)' if not result3 else '❌ Unexpected HIT'}")
    
    print(f"\n  Cache Stats: {cache.get_stats()}")
    
    # ============== TEST 3: Model Cascade ==============
    print("\n" + "=" * 60)
    print("TEST 3: Model Cascade (Cheap -> Primary)")
    print("=" * 60)
    
    cascade = ModelCascade(
        primary_model="xiaomi/mimo-v2-flash",
        cheap_model="nousresearch/nous-capybara-7b:free"
    )
    
    print(f"\n  Primary Model: {cascade.primary_model}")
    print(f"  Cheap Model: {cascade.cheap_model}")
    
    # Test quick check
    print("\n  Quick Check Test:")
    start = time.time()
    worth_it, confidence = await cascade.quick_check(
        "Market: BTC $100k, Polymarket YES=0.65, Kalshi YES=0.58, spread=7%"
    )
    latency = (time.time() - start) * 1000
    print(f"    Worth investigating: {worth_it}")
    print(f"    Confidence: {confidence:.0%}")
    print(f"    Latency: {latency:.0f}ms")
    
    # Test deep analysis
    print("\n  Deep Analysis Test:")
    start = time.time()
    result = await cascade.deep_analysis({
        "question": "Will SpaceX land on Mars by 2028?",
        "polymarket_yes": 0.25,
        "kalshi_yes": 0.18,
        "spread_pct": 7.0
    })
    latency = (time.time() - start) * 1000
    print(f"    Result: {result}")
    print(f"    Latency: {latency:.0f}ms")
    
    print(f"\n  Cascade Stats: {cascade.get_stats()}")
    
    # ============== TEST 4: Full Hacha Protocol ==============
    print("\n" + "=" * 60)
    print("TEST 4: Full Hacha Protocol Integration")
    print("=" * 60)
    
    hacha = HachaProtocol(
        min_ev_threshold=0.3,  # Lower for testing
        semantic_threshold=0.90,
        cache_ttl=3600,
        use_cascade=True
    )
    
    # Real arbitrage opportunities (prices sum < 1.0)
    opportunities = [
        {
            'id': 'real_arb_1',
            'market_data': {
                'question': 'Will the Fed cut rates in Q1 2026?',
                'polymarket_yes': 0.40,
                'polymarket_no': 0.55,
                'kalshi_yes': 0.35
            },
            'buy_prices': [0.40, 0.55],  # Sum = 0.95, margin = 5%
            'guaranteed_payout': 1.0
        },
        {
            'id': 'real_arb_2',
            'market_data': {
                'question': 'Will Tesla hit $500 by March 2026?',
                'polymarket_yes': 0.30,
                'polymarket_no': 0.65,
            },
            'buy_prices': [0.30, 0.65],  # Sum = 0.95, margin = 5%
            'guaranteed_payout': 1.0
        },
        {
            'id': 'no_arb',
            'market_data': {
                'question': 'Random market with no arb',
                'polymarket_yes': 0.50,
                'polymarket_no': 0.52,
            },
            'buy_prices': [0.50, 0.52],  # Sum = 1.02, no arb
            'guaranteed_payout': 1.0
        }
    ]
    
    print(f"\n  Testing {len(opportunities)} opportunities:")
    print()
    
    for opp in opportunities:
        result = await hacha.analyze_opportunity(
            opp['market_data'],
            opp['buy_prices'],
            opp['guaranteed_payout']
        )
        
        print(f"  📊 {opp['id']}")
        print(f"     Prices: {opp['buy_prices']} (sum={sum(opp['buy_prices']):.2f})")
        print(f"     EV Net: {result.ev_net:.2f}%")
        print(f"     Is Opportunity: {result.is_opportunity}")
        print(f"     Source: {result.source}")
        print(f"     Latency: {result.latency_ms:.1f}ms")
        print()
    
    # Test cache hit
    print("  📊 Cache Test (repeat first query)")
    result2 = await hacha.analyze_opportunity(
        opportunities[0]['market_data'],
        opportunities[0]['buy_prices']
    )
    print(f"     Source: {result2.source}")
    print(f"     Latency: {result2.latency_ms:.1f}ms")
    print()
    
    # Final stats
    print("\n" + "=" * 60)
    print("FINAL STATISTICS")
    print("=" * 60)
    
    stats = hacha.get_full_stats()
    print(f"\n  Total Analyzed: {stats['total_analyzed']}")
    print(f"  Opportunities Found: {stats['opportunities_found']}")
    print(f"\n  Math Filter:")
    print(f"    Checked: {stats['math_filter']['total_checked']}")
    print(f"    Filtered: {stats['math_filter']['filtered_out']}")
    print(f"    Passed: {stats['math_filter']['passed']}")
    print(f"    Filter Rate: {stats['math_filter']['filter_rate']}")
    print(f"\n  Cache:")
    print(f"    Exact Hits: {stats['cache']['exact_hits']}")
    print(f"    Semantic Hits: {stats['cache']['semantic_hits']}")
    print(f"    Misses: {stats['cache']['misses']}")
    print(f"    Hit Rate: {stats['cache']['hit_rate']}")
    if stats['cascade']:
        print(f"\n  Model Cascade:")
        print(f"    Cheap Calls: {stats['cascade']['cheap_calls']}")
        print(f"    Primary Calls: {stats['cascade']['primary_calls']}")
        print(f"    Total Tokens: {stats['cascade']['total_tokens']}")
        print(f"    Estimated Savings: {stats['cascade']['estimated_savings']}")
    
    print("\n╔" + "═" * 68 + "╗")
    print("║" + " TEST COMPLETE ✅ ".center(68) + "║")
    print("╚" + "═" * 68 + "╝")


if __name__ == "__main__":
    asyncio.run(test_hacha_protocol())
