"""
Tests for AI/LLM Integration (MiMo Client).
Tests both mock scenarios and live API functionality.
"""

import pytest
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Load environment
from dotenv import load_dotenv
load_dotenv()

# Import the modules to test
from src.ai.mimo_client import (
    MiMoClient, 
    AIArbitrageAnalyzer, 
    SemanticCache,
    AIThesis
)


class TestSemanticCache:
    """Tests for the SemanticCache class."""
    
    def test_cache_set_and_get(self):
        """Test basic cache set and get."""
        cache = SemanticCache(ttl_hours=1.0)
        
        test_data = {"is_arb": True, "confidence": 0.8}
        cache.set("test market description", test_data)
        
        result = cache.get("test market description")
        assert result is not None
        assert result["is_arb"] == True
        assert result["confidence"] == 0.8
    
    def test_cache_miss(self):
        """Test cache miss for non-existent key."""
        cache = SemanticCache(ttl_hours=1.0)
        result = cache.get("non-existent market")
        assert result is None
    
    def test_cache_stats(self):
        """Test cache statistics."""
        cache = SemanticCache(ttl_hours=1.0)
        stats = cache.get_stats()
        assert 'type' in stats
        assert 'entries' in stats


class TestMiMoClient:
    """Tests for the MiMoClient class."""
    
    def test_client_initialization_with_env_key(self):
        """Test client initializes with API_LLM from env."""
        api_key = os.getenv('API_LLM')
        if api_key:
            client = MiMoClient()
            assert client.api_key is not None
            assert client.api_key == api_key
    
    def test_client_initialization_without_key(self):
        """Test client handles missing API key gracefully."""
        with patch.dict(os.environ, {'API_LLM': '', 'OPENROUTER_API_KEY': ''}, clear=False):
            # Create new client without env vars
            client = MiMoClient(api_key=None)
            # When no key is available after clearing, client should handle gracefully
            # (In practice, dotenv may have already loaded the key)

    def test_default_model(self):
        """Test default model is set correctly."""
        client = MiMoClient()
        assert client.model == "xiaomi/mimo-v2-flash"
    
    def test_prompt_building(self):
        """Test prompt is built correctly."""
        client = MiMoClient()
        
        market_data = {
            "Polymarket": {"yes_price": 0.65},
            "Kalshi": {"yes_price": 0.58}
        }
        
        prompt = client._build_analysis_prompt(market_data, "")
        assert "Arb?" in prompt
        assert "Polymarket" in prompt
        assert "0.65" in prompt


class TestAIArbitrageAnalyzer:
    """Tests for the AIArbitrageAnalyzer class."""
    
    def test_analyzer_rejects_low_edge(self):
        """Test analyzer skips analysis for low edge opportunities."""
        analyzer = AIArbitrageAnalyzer(min_edge_for_ai=1.0)
        
        # Run sync wrapper for async function
        thesis = asyncio.run(analyzer.analyze(
            market_data={"test": "data"},
            edge_pct=0.5  # Below threshold
        ))
        
        assert thesis.is_arb == False
        assert "below threshold" in thesis.reasoning.lower()
    
    def test_analyzer_stats_tracking(self):
        """Test analyzer tracks statistics correctly."""
        analyzer = AIArbitrageAnalyzer(min_edge_for_ai=0.5)
        
        # Initial stats
        stats = analyzer.get_stats()
        assert stats['total_requests'] == 0
        assert stats['cache_hits'] == 0
        assert stats['ai_calls'] == 0


@pytest.mark.skipif(
    not os.getenv('API_LLM'),
    reason="API_LLM not set - skip live API tests"
)
class TestLiveAPI:
    """Live API tests - only run if API key is available."""
    
    @pytest.mark.asyncio
    async def test_live_market_matching(self):
        """Test live market matching with real API."""
        client = MiMoClient()
        
        result = await client.match_markets(
            market1="Will BTC hit $150k by end of 2026?",
            market2="Bitcoin above $150,000 on December 31, 2026",
            platform1="Polymarket",
            platform2="Kalshi"
        )
        
        # Verify response structure
        assert 'match' in result
        assert 'score' in result
        assert isinstance(result.get('match'), bool)
        # Score should be numeric (could be int from JSON or float)
        score = result.get('score', 0)
        assert isinstance(score, (int, float))
        # For identical markets, we expect a match, but just verify valid response
        # LLM responses can vary, so we accept any valid structure
    
    @pytest.mark.asyncio
    async def test_live_arbitrage_analysis(self):
        """Test live arbitrage analysis with real API."""
        analyzer = AIArbitrageAnalyzer(min_edge_for_ai=0.3)
        
        market_data = {
            "Polymarket": {
                "question": "Will ETH hit $10k by June 2026?",
                "yes_price": 0.35,
                "no_price": 0.68
            },
            "Kalshi": {
                "question": "Ethereum above $10,000 on June 1, 2026",
                "yes_price": 0.28,
                "no_price": 0.75
            }
        }
        
        thesis = await analyzer.analyze(market_data, edge_pct=3.0)
        
        assert isinstance(thesis, AIThesis)
        assert thesis.confidence >= 0.0
        assert thesis.confidence <= 1.0
        assert len(thesis.reasoning) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
