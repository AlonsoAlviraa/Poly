import asyncio
import unittest
from datetime import datetime, timedelta

# Import logic to test
from src.arbitrage.cross_platform_mapper import CrossPlatformMapper
from src.arbitrage.entity_resolver_logic import get_resolver

# Mock data
SX_EVENT_REAL = {
    'id': '0xbc4058a20a28061077de648d3d6aadcc89c75e31bc7ba6c1d70735ff465e7e03',
    'name': 'Carabobo FC vs Huachipato',
    'open_date': '2026-02-17T22:00:00+00:00',
    'exchange': 'sx',
    '_start_date_parsed': datetime.fromisoformat('2026-02-17T22:00:00+00:00'),
    'market_type': 'MATCH_ODDS',
    'runners': [{'selectionId': 1, 'runnerName': 'Carabobo FC'}, {'selectionId': 2, 'runnerName': 'Huachipato'}]
}

POLY_MARKET_SIMULATED = {
    'id': 'poly_123',
    'question': 'Will Carabobo FC win against Huachipato?',
    'startDate': '2026-02-17T22:00:00Z',
    '_event_date_parsed': datetime.fromisoformat('2026-02-17T22:00:00+00:00'),
    'slug': 'carabobo-huachipato-match-winner',
    'category': 'Soccer'
}

POLY_MARKET_HARD = {
    'id': 'poly_456',
    'question': 'Will Carabobo win their next match?', # Hard case
    'startDate': '2026-02-17T22:00:00Z',
    '_event_date_parsed': datetime.fromisoformat('2026-02-17T22:00:00+00:00'),
    'slug': 'carabobo-match-winner',
    'category': 'Soccer'
}

class TestSXMatchingLogic(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mapper = CrossPlatformMapper()
        # Ensure resolver is fresh
        get_resolver().mappings = {} 

    async def test_sx_split_and_match(self):
        print("\n>> TESTING: SX Splitter Logic & Fuzzy Match...")
        
        # Scenario 1: Exact Team Names in Question
        print(f"   [CASE 1] Poly: '{POLY_MARKET_SIMULATED['question']}' vs SX: '{SX_EVENT_REAL['name']}'")
        
        candidates = [SX_EVENT_REAL]
        buckets = {
            SX_EVENT_REAL['_start_date_parsed'].date(): [SX_EVENT_REAL]
        }

        mapping = await self.mapper.map_market(
            poly_market=POLY_MARKET_SIMULATED,
            betfair_events=candidates,
            bf_buckets=buckets,
            sport_category='soccer'
        )

        if mapping:
            print(f"   ✅ MATCH FOUND! Confidence: {mapping.confidence}")
            print(f"      Mapped to: {mapping.betfair_event_name}")
            self.assertEqual(mapping.exchange, 'sx')
        else:
            print("   ❌ MATCH FAILED.")
            self.fail("Failed to match clear SX event.")

    async def test_sx_hard_case(self):
        print("\n>> TESTING: Hard Case (Partial Name)...")
        print(f"   [CASE 2] Poly: '{POLY_MARKET_HARD['question']}' vs SX: '{SX_EVENT_REAL['name']}'")
        
        candidates = [SX_EVENT_REAL]
        buckets = {
            SX_EVENT_REAL['_start_date_parsed'].date(): [SX_EVENT_REAL]
        }

        mapping = await self.mapper.map_market(
            poly_market=POLY_MARKET_HARD,
            betfair_events=candidates,
            bf_buckets=buckets,
            sport_category='soccer'
        )
        
        if mapping:
             print(f"   ✅ MATCH FOUND! Confidence: {mapping.confidence}")
        else:
             print("   ⚠️  No match (Expected for hard case without vector/AI).")

if __name__ == '__main__':
    unittest.main()
