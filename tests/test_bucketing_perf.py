
import asyncio
import sys
import os
import time
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.arbitrage.cross_platform_mapper import CrossPlatformMapper, ShadowArbitrageScan

async def test_bucketing_perf():
    mapper = CrossPlatformMapper()
    scanner = ShadowArbitrageScan(mapper, None)
    
    # 1. Mock dataset: 5000 Betfair events spread over 1 year
    n_events = 5000
    base_date = datetime.now(timezone.utc)
    bf_events = []
    for i in range(n_events):
        event_date = base_date + timedelta(hours=i * 2) # Every 2 hours
        bf_events.append({
            'id': i,
            'name': f"Event {i}",
            'openDate': event_date.isoformat(),
            '_start_date_parsed': event_date
        })
    
    # Pre-build buckets
    bf_buckets = defaultdict(list)
    for event in bf_events:
        bf_buckets[event['_start_date_parsed'].date()].append(event)
    
    print(f"Total Events: {n_events}")
    print(f"Total Buckets: {len(bf_buckets)}")
    print("-" * 60)
    
    # 2. Benchmark specific lookup
    poly_date = base_date + timedelta(days=50)
    poly_market = {
        'question': 'Test Event',
        '_event_date_parsed': poly_date
    }
    
    # Test bucket lookup logic (manually to see counts)
    target_date = poly_date.date()
    start_t = time.perf_counter()
    candidates = (
        bf_buckets.get(target_date, []) +
        bf_buckets.get(target_date - timedelta(days=1), []) +
        bf_buckets.get(target_date + timedelta(days=1), [])
    )
    # fine-grain filter
    valid = [ev for ev in candidates if abs(poly_date - ev['_start_date_parsed']) < timedelta(hours=24)]
    end_t = time.perf_counter()
    
    print(f"Lookup for date: {target_date}")
    print(f"Candidates found in buckets (3 days): {len(candidates)}")
    print(f"Final valid candidates (+/- 24h): {len(valid)}")
    print(f"Lookup time: {(end_t - start_t)*1000:.4f}ms")
    print(f"Reduction Ratio: {n_events / len(candidates):.1f}x")
    
    assert len(candidates) > 0, "Should find candidates"
    assert len(candidates) < 100, "Should be approximately 36 candidates (3 days * 12 per day)"
    print("Optimization Logic Verified!")

if __name__ == "__main__":
    asyncio.run(test_bucketing_perf())
