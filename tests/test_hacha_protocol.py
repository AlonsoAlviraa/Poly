"""
Tests for the Hacha Protocol - Optimized AI Integration.
Tests mathematical filter, cache, and model cascade.
"""

import pytest
import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

from dotenv import load_dotenv
load_dotenv()

from src.ai.hacha_protocol import (
    HachaProtocol,
    HybridSemanticCache,
    MathematicalFilter,
    ModelCascade,
    MarketOpportunity,
    CacheMetrics
)


class TestMathematicalFilter:
    """Tests for the Mathematical Pre-Filter."""
    
    def test_ev_positive_passes(self):
        """Test that positive EV opportunities pass."""
        filter = MathematicalFilter(min_ev_threshold=0.5)
        
        # Sum = 0.95, gross = 5.26%, net after fees ~4.5%
        ev, passed = filter.calculate_ev_net([0.45, 0.50], 1.0)
        assert passed == True
        assert ev > 0.5
    
    def test_ev_negative_fails(self):
        """Test that negative EV opportunities fail."""
        filter = MathematicalFilter(min_ev_threshold=0.5)
        
        # Sum = 1.02, negative EV
        ev, passed = filter.calculate_ev_net([0.50, 0.52], 1.0)
        assert passed == False
        assert ev < 0
    
    def test_ev_marginally_positive_fails(self):
        """Test that marginally positive but below threshold fails."""
        filter = MathematicalFilter(min_ev_threshold=0.5)
        
        # Sum = 0.99, gross = 1%, net ~ 0.2% after fees/slippage
        ev, passed = filter.calculate_ev_net([0.50, 0.49], 1.0)
        assert passed == False
        assert ev > -1 and ev < 0.5
    
    def test_filter_stats(self):
        """Test filter statistics are tracked."""
        filter = MathematicalFilter(min_ev_threshold=0.5)
        
        filter.calculate_ev_net([0.45, 0.50], 1.0)  # Pass
        filter.calculate_ev_net([0.50, 0.52], 1.0)  # Fail
        
        stats = filter.get_stats()
        assert stats['total_checked'] == 2
        assert stats['passed'] == 1
        assert stats['filtered_out'] == 1
    
    def test_kelly_sizing_zero_ev(self):
        """Test Kelly returns 0 for zero or negative EV."""
        filter = MathematicalFilter()
        
        size = filter.kelly_size(ev_pct=0.0, win_prob=0.9, bankroll=1000)
        assert size == 0.0
        
        size = filter.kelly_size(ev_pct=-1.0, win_prob=0.9, bankroll=1000)
        assert size == 0.0
    
    def test_kelly_sizing_positive_ev(self):
        """Test Kelly returns positive size for positive EV."""
        filter = MathematicalFilter()
        
        # High EV should return positive size
        size = filter.kelly_size(ev_pct=10.0, win_prob=0.95, bankroll=1000)
        assert size > 0
        assert size <= 50  # Max 5% of bankroll


class TestHybridSemanticCache:
    """Tests for the Hybrid Semantic Cache."""
    
    def test_cache_set_and_get_exact(self):
        """Test exact match cache."""
        cache = HybridSemanticCache()
        
        test_data = {"is_arb": True, "confidence": 0.8}
        cache.set("test query", test_data)
        
        result = cache.get("test query")
        assert result is not None
        assert result["is_arb"] == True
    
    def test_cache_miss(self):
        """Test cache miss for non-existent key."""
        cache = HybridSemanticCache()
        
        result = cache.get("non-existent query")
        assert result is None
    
    def test_cache_metrics(self):
        """Test cache metrics are tracked."""
        cache = HybridSemanticCache()
        
        cache.set("query1", {"data": 1})
        cache.get("query1")  # Hit
        cache.get("query2")  # Miss
        
        stats = cache.get_stats()
        assert stats['total_requests'] == 2
        assert stats['exact_hits'] == 1
        assert stats['misses'] == 1
    
    def test_cache_expiry(self):
        """Test cache respects TTL."""
        cache = HybridSemanticCache(default_ttl_seconds=1)
        
        cache.set("expiry test", {"data": 1})
        
        # Should hit immediately
        result = cache.get("expiry test")
        assert result is not None
        
        # Wait for expiry
        time.sleep(1.1)
        
        # Should miss after expiry
        result = cache.get("expiry test")
        assert result is None


class TestModelCascade:
    """Tests for Model Cascade."""
    
    def test_cascade_initialization(self):
        """Test cascade initializes with correct models."""
        cascade = ModelCascade(
            primary_model="xiaomi/mimo-v2-flash",
            cheap_model="nousresearch/nous-capybara-7b:free"
        )
        
        assert cascade.primary_model == "xiaomi/mimo-v2-flash"
        assert cascade.cheap_model == "nousresearch/nous-capybara-7b:free"
    
    def test_cascade_stats_initial(self):
        """Test cascade stats are zero initially."""
        cascade = ModelCascade()
        
        stats = cascade.get_stats()
        assert stats['cheap_calls'] == 0
        assert stats['primary_calls'] == 0
        assert stats['total_tokens'] == 0


class TestHachaProtocol:
    """Tests for the full Hacha Protocol."""
    
    def test_protocol_initialization(self):
        """Test protocol initializes correctly."""
        hacha = HachaProtocol(
            min_ev_threshold=0.5,
            semantic_threshold=0.90,
            cache_ttl=3600
        )
        
        assert hacha.math_filter is not None
        assert hacha.cache is not None
        assert hacha.cascade is not None
    
    def test_protocol_filters_low_ev(self):
        """Test protocol filters out low EV opportunities."""
        hacha = HachaProtocol(min_ev_threshold=0.5)
        
        result = asyncio.run(hacha.analyze_opportunity(
            market_data={"question": "Test market"},
            buy_prices=[0.50, 0.52],  # Negative EV
            guaranteed_payout=1.0
        ))
        
        assert result.is_opportunity == False
        assert result.source == 'math_filter'
        assert result.latency_ms < 10  # Should be very fast
    
    def test_protocol_stats(self):
        """Test protocol tracks statistics."""
        hacha = HachaProtocol()
        
        asyncio.run(hacha.analyze_opportunity(
            market_data={"question": "Test"},
            buy_prices=[0.50, 0.55]
        ))
        
        stats = hacha.get_full_stats()
        assert stats['total_analyzed'] >= 1
        assert 'math_filter' in stats
        assert 'cache' in stats
    
    def test_dynamic_ttl_stable_market(self):
        """Test dynamic TTL for stable markets."""
        hacha = HachaProtocol()
        
        ttl = hacha.get_dynamic_ttl(volatility=0.0)  # Stable
        assert ttl == 3600  # Max TTL
    
    def test_dynamic_ttl_volatile_market(self):
        """Test dynamic TTL for volatile markets."""
        hacha = HachaProtocol()
        
        ttl = hacha.get_dynamic_ttl(volatility=1.0)  # Very volatile
        assert ttl == 300  # Min TTL (5 minutes)


@pytest.mark.skipif(
    not os.getenv('API_LLM'),
    reason="API_LLM not set - skip live API tests"
)
class TestHachaProtocolLive:
    """Live API tests for Hacha Protocol."""
    
    @pytest.mark.asyncio
    async def test_live_opportunity_analysis(self):
        """Test live opportunity analysis with real API."""
        hacha = HachaProtocol(min_ev_threshold=0.3)
        
        result = await hacha.analyze_opportunity(
            market_data={
                "question": "Will BTC hit $150k by 2027?",
                "polymarket_yes": 0.35,
                "kalshi_yes": 0.30
            },
            buy_prices=[0.35, 0.60],  # Sum = 0.95, positive EV
            guaranteed_payout=1.0
        )
        
        assert isinstance(result, MarketOpportunity)
        assert result.ev_net > 0
        assert result.source in ['llm', 'cache_exact', 'cache_semantic']
    
    @pytest.mark.asyncio
    async def test_live_cache_hit(self):
        """Test cache works with live API."""
        hacha = HachaProtocol()
        
        market_data = {
            "question": "Cache test market",
            "price": 0.5
        }
        
        # First call
        result1 = await hacha.analyze_opportunity(
            market_data=market_data,
            buy_prices=[0.45, 0.50]
        )
        
        # Second call - should be cached
        result2 = await hacha.analyze_opportunity(
            market_data=market_data,
            buy_prices=[0.45, 0.50]
        )
        
        # Second should be faster (cache hit)
        assert result2.source in ['cache_exact', 'cache_semantic']
        assert result2.latency_ms < result1.latency_ms


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
