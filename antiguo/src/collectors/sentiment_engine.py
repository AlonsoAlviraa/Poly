import random
import asyncio
from typing import Dict, Optional

class SentimentCollector:
    """Base class for social sentiment collection."""
    async def get_sentiment(self, token_slug: str) -> Dict[str, float]:
        """Return {'sentiment': -1.0 to 1.0, 'buzz': 0.0 to 1.0}"""
        raise NotImplementedError

class MockSentimentCollector(SentimentCollector):
    """Simulates social bursts and sentiment shits for testing."""
    
    def __init__(self):
        self._cache = {}
    
    async def get_sentiment(self, token_slug: str) -> Dict[str, float]:
        # Simulate a random walk with occasional "Bursts"
        prev = self._cache.get(token_slug, {"sentiment": 0.0, "buzz": 0.1})
        
        # 5% chance of a "Viral Moment" (Buzz spike)
        if random.random() < 0.05:
             new_buzz = min(1.0, prev["buzz"] + 0.4)
             # Viral moments usually have strong sentiment (bullish or bearish)
             new_sent = prev["sentiment"] + random.uniform(-0.5, 0.5)
        else:
             # Decay buzz
             new_buzz = max(0.0, prev["buzz"] * 0.95)
             # Drift sentiment
             new_sent = prev["sentiment"] * 0.98 + random.uniform(-0.05, 0.05)
             
        new_sent = max(-1.0, min(1.0, new_sent))
        
        result = {"sentiment": new_sent, "buzz": new_buzz}
        self._cache[token_slug] = result
        return result

# Singleton for easy import
sentiment_engine = MockSentimentCollector()
