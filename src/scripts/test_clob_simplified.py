#!/usr/bin/env python3
"""Test CLOB simplified markets endpoint."""

import httpx
import json

print("Testing CLOB simplified-markets endpoint...")
r = httpx.get('https://clob.polymarket.com/simplified-markets', timeout=15)
data = r.json()

print(f'Type: {type(data)}')

if isinstance(data, list):
    print(f'Count: {len(data)}')
    if data:
        first = data[0]
        print(f'\nFirst Market:')
        print(json.dumps(first, indent=2, default=str)[:1500])
        
        # Check for active ones
        active_count = 0
        for m in data:
            if m.get('active') and not m.get('closed'):
                active_count += 1
        
        print(f'\nActive & Not Closed: {active_count}')
        
        # Show first active one
        for m in data:
            if m.get('active') and not m.get('closed'):
                print(f'\nFirst Active Market:')
                print(f'  Question: {m.get("question", "N/A")[:60]}')
                print(f'  condition_id: {m.get("condition_id")}')
                
                tokens = m.get('tokens', [])
                print(f'  Tokens: {len(tokens)}')
                for t in tokens[:2]:
                    print(f'    - {t}')
                break
elif isinstance(data, dict):
    print(f'Keys: {list(data.keys())}')
    print(json.dumps(data, indent=2, default=str)[:1000])
