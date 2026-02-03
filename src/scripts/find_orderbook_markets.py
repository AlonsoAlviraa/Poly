#!/usr/bin/env python3
"""
Find markets that actually HAVE orderbooks.
Strategy: Use Gamma API to find high-volume markets, then cross-check with CLOB.
"""

import httpx
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.execution.clob_executor import PolymarketCLOBExecutor

print("=" * 70)
print("FINDING MARKETS WITH REAL ORDERBOOKS")
print("=" * 70)

executor = PolymarketCLOBExecutor(
    host='https://clob.polymarket.com',
    key='0x' + '1' * 64,
    chain_id=137
)

# Use Gamma API for high-volume markets
print("\n[1] Querying Gamma API for high-volume OPEN markets...")
gamma_resp = httpx.get(
    'https://gamma-api.polymarket.com/markets',
    params={
        'closed': 'false',
        'limit': 100,
        'order': 'volume',
        'ascending': 'false'
    },
    timeout=15
)

gamma_markets = gamma_resp.json()
print(f"    Retrieved: {len(gamma_markets)} markets from Gamma")

# Now for each, try to find the CLOB token IDs
print("\n[2] Cross-referencing with CLOB API for orderbooks...")

found_with_orderbook = []

for m in gamma_markets[:30]:  # Check top 30 by volume
    condition_id = m.get('conditionId', '')
    question = m.get('question', 'N/A')[:50]
    volume = float(m.get('volume', 0) or 0)
    
    if not condition_id:
        continue
    
    print(f"\n    Checking: {question}...")
    print(f"      Volume: ${volume:,.0f}")
    
    # Try to get from sampling markets (which have token IDs)
    # Search by condition_id
    try:
        # Need to find this condition_id in CLOB simplified markets
        # Use REST endpoint directly
        clob_resp = httpx.get(
            'https://clob.polymarket.com/sampling-markets',
            params={'condition_id': condition_id},
            timeout=10
        )
        
        if clob_resp.status_code == 200:
            clob_data = clob_resp.json()
            if clob_data:
                tokens = clob_data[0].get('tokens', []) if isinstance(clob_data, list) else clob_data.get('tokens', [])
                if tokens:
                    token_id = tokens[0].get('token_id')
                    print(f"      Found token_id: {token_id[:30]}...")
                    
                    # Try orderbook
                    try:
                        book = executor.client.get_order_book(token_id)
                        if hasattr(book, 'bids'):
                            bids = book.bids if book.bids else []
                            asks = book.asks if book.asks else []
                        else:
                            bids = book.get('bids', [])
                            asks = book.get('asks', [])
                        
                        if bids and asks:
                            print(f"      ORDERBOOK: {len(bids)} bids, {len(asks)} asks")
                            found_with_orderbook.append({
                                'question': question,
                                'token_id': token_id,
                                'bids': len(bids),
                                'asks': len(asks),
                                'volume': volume
                            })
                        else:
                            print(f"      Empty orderbook")
                    except Exception as e:
                        if '404' in str(e):
                            print(f"      No orderbook for this token")
                        else:
                            print(f"      Orderbook error: {e}")
        else:
            print(f"      CLOB lookup failed: {clob_resp.status_code}")
            
    except Exception as e:
        print(f"      Error: {e}")

# Summary
print("\n" + "=" * 70)
print("[3] MARKETS WITH ACTIVE ORDERBOOKS")
print("=" * 70)

if found_with_orderbook:
    print(f"\n    FOUND: {len(found_with_orderbook)} markets with orderbooks!\n")
    for m in found_with_orderbook[:5]:
        print(f"    - {m['question']}...")
        print(f"      Volume: ${m['volume']:,.0f}")
        print(f"      Orderbook: {m['bids']} bids / {m['asks']} asks")
        print(f"      Token: {m['token_id'][:40]}...")
        print()
else:
    print("""
    NO MARKETS WITH ORDERBOOKS FOUND
    
    Possible reasons:
    1. Time of day - low activity period
    2. Market makers withdrew liquidity
    3. Need to check specific popular markets manually
    """)

print("=" * 70)
