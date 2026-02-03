#!/usr/bin/env python3
"""
Test different CLOB endpoints for market access.
"""

import httpx
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.execution.clob_executor import PolymarketCLOBExecutor

print("=" * 70)
print("ORDERBOOK ACCESS TEST")
print("=" * 70)

# Initialize CLOB client
executor = PolymarketCLOBExecutor(
    host='https://clob.polymarket.com',
    key='0x' + '1' * 64,
    chain_id=137
)

# Get a tradeable market first
resp = executor.client.get_simplified_markets(next_cursor='')
markets = resp.get('data', [])

# Find one accepting orders
tradeable = None
for m in markets:
    if m.get('accepting_orders') == True and not m.get('closed'):
        tradeable = m
        break

if not tradeable:
    # Try a few pages
    for _ in range(10):
        cursor = resp.get('next_cursor', '')
        if not cursor:
            break
        resp = executor.client.get_simplified_markets(next_cursor=cursor)
        markets = resp.get('data', [])
        for m in markets:
            if m.get('accepting_orders') == True and not m.get('closed'):
                tradeable = m
                break
        if tradeable:
            break

if not tradeable:
    print("No tradeable market found!")
    sys.exit(1)

print(f"\nFound tradeable market:")
print(f"  Condition ID: {tradeable.get('condition_id')}")
print(f"  Accepting Orders: {tradeable.get('accepting_orders')}")
print(f"  Closed: {tradeable.get('closed')}")

tokens = tradeable.get('tokens', [])
print(f"  Tokens: {len(tokens)}")

if len(tokens) >= 2:
    token_id = tokens[0].get('token_id')
    print(f"  Token ID: {token_id}")
    
    print("\n" + "-" * 50)
    print("Testing different endpoints:")
    print("-" * 50)
    
    # Test 1: Direct orderbook
    print("\n1. get_order_book(token_id):")
    try:
        book = executor.client.get_order_book(token_id)
        print(f"   Response type: {type(book)}")
        if hasattr(book, 'bids'):
            print(f"   Bids: {len(book.bids) if book.bids else 0}")
            print(f"   Asks: {len(book.asks) if book.asks else 0}")
        else:
            print(f"   Response: {book}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 2: Get price
    print("\n2. get_price(token_id):")
    try:
        price = executor.client.get_price(token_id, 'BUY')
        print(f"   Buy Price: {price}")
        price_sell = executor.client.get_price(token_id, 'SELL')
        print(f"   Sell Price: {price_sell}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 3: Get midpoint
    print("\n3. get_midpoint(token_id):")
    try:
        mid = executor.client.get_midpoint(token_id)
        print(f"   Midpoint: {mid}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 4: Get spread
    print("\n4. get_spread(token_id):")
    try:
        spread = executor.client.get_spread(token_id)
        print(f"   Spread: {spread}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 5: Raw HTTP request to orderbook
    print("\n5. Raw HTTP to /book endpoint:")
    try:
        r = httpx.get(f'https://clob.polymarket.com/book?token_id={token_id}', timeout=10)
        print(f"   Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"   Response: {json.dumps(data, indent=2)[:500]}")
        else:
            print(f"   Response: {r.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")

print("\n" + "=" * 70)
