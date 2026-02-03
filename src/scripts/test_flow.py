#!/usr/bin/env python3
"""Test complete flow: Gamma API -> CLOB API."""

import httpx
import json

# Gamma API - get a market
gamma_resp = httpx.get('https://gamma-api.polymarket.com/markets', params={
    'closed': 'false',
    'limit': 3,
    'order': 'volume'
})
markets = gamma_resp.json()

print("=" * 70)
print("COMPLETE FLOW TEST: GAMMA -> CLOB")
print("=" * 70)

for i, market in enumerate(markets[:3]):
    condition_id = market.get('conditionId')
    question = market.get('question', 'N/A')[:55]
    
    print(f"\n[{i+1}] {question}...")
    print(f"    Condition ID: {condition_id}")
    print(f"    Outcomes: {market.get('outcomes')}")
    print(f"    Prices: {market.get('outcomePrices')}")
    
    # Try to get from CLOB API
    print(f"    Fetching from CLOB API...")
    
    try:
        # Try market endpoint
        clob_resp = httpx.get(
            f'https://clob.polymarket.com/markets/{condition_id}',
            timeout=10.0
        )
        
        if clob_resp.status_code == 200:
            clob_data = clob_resp.json()
            print(f"    CLOB Status: 200 OK")
            
            tokens = clob_data.get('tokens', [])
            if tokens:
                print(f"    Tokens found: {len(tokens)}")
                for t in tokens[:2]:
                    token_id = t.get('token_id')
                    outcome = t.get('outcome')
                    print(f"      - {outcome}: {token_id[:40]}...")
            else:
                print(f"    Keys in response: {list(clob_data.keys())[:10]}")
                
                # Check if there's a different structure
                if 'clobTokenIds' in str(clob_data):
                    print(f"    Found clobTokenIds!")
                    
        else:
            print(f"    CLOB Status: {clob_resp.status_code}")
            print(f"    Response: {clob_resp.text[:200]}")
            
    except Exception as e:
        print(f"    CLOB Error: {e}")

# Also try simplified markets from CLOB
print("\n" + "=" * 70)
print("ALTERNATIVE: CLOB get_simplified_markets")
print("=" * 70)

try:
    simp_resp = httpx.get('https://clob.polymarket.com/simplified-markets', timeout=10.0)
    print(f"Status: {simp_resp.status_code}")
    if simp_resp.status_code == 200:
        simp_data = simp_resp.json()
        if isinstance(simp_data, list) and simp_data:
            print(f"Count: {len(simp_data)}")
            m = simp_data[0]
            print(f"First market keys: {list(m.keys())[:10]}")
            print(f"First market: {json.dumps(m, indent=2)[:500]}")
except Exception as e:
    print(f"Error: {e}")
