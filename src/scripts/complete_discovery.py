#!/usr/bin/env python3
"""
COMPLETE MARKET DISCOVERY TEST
Find active, tradeable markets with orderbooks.
"""

import httpx
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.execution.clob_executor import PolymarketCLOBExecutor

print("=" * 70)
print("POLYMARKET ACTIVE MARKET DISCOVERY - COMPLETE TEST")
print("=" * 70)

# Initialize CLOB client
executor = PolymarketCLOBExecutor(
    host='https://clob.polymarket.com',
    key='0x' + '1' * 64,
    chain_id=137
)

# Scan for active markets
print("\n[1] Scanning CLOB simplified-markets for TRADEABLE markets...")

all_markets = []
next_cursor = ''
pages = 0
max_pages = 20

while pages < max_pages:
    try:
        resp = executor.client.get_simplified_markets(next_cursor=next_cursor)
        
        if isinstance(resp, dict):
            batch = resp.get('data', [])
            next_cursor = resp.get('next_cursor', '')
        elif isinstance(resp, list):
            batch = resp
            next_cursor = ''
        else:
            break
            
        all_markets.extend(batch)
        pages += 1
        
        accepting = sum(1 for m in batch if m.get('accepting_orders'))
        print(f"    Page {pages}: {len(batch)} markets, {accepting} accepting orders")
        
        if not next_cursor or next_cursor == "LTE=":
            break
    except Exception as e:
        print(f"    Error: {e}")
        break

print(f"\n    TOTAL: {len(all_markets)} markets scanned")

# Filter for tradeable markets
tradeable = [
    m for m in all_markets 
    if m.get('accepting_orders') == True and m.get('closed') != True
]

print(f"    TRADEABLE (accepting_orders=True, closed!=True): {len(tradeable)}")

# Show top tradeable markets
print("\n" + "=" * 70)
print("[2] TOP TRADEABLE MARKETS")
print("=" * 70)

tested = 0
for m in tradeable[:10]:
    if tested >= 5:
        break
        
    condition_id = m.get('condition_id', 'N/A')[:20]
    tokens = m.get('tokens', [])
    
    if len(tokens) < 2:
        continue
    
    token_id = tokens[0].get('token_id')
    outcome_yes = tokens[0].get('outcome')
    outcome_no = tokens[1].get('outcome') if len(tokens) > 1 else 'N/A'
    price_yes = tokens[0].get('price', 0)
    price_no = tokens[1].get('price', 0) if len(tokens) > 1 else 0
    
    print(f"\n    Market {tested + 1}:")
    print(f"      Condition: {condition_id}...")
    print(f"      Outcomes: {outcome_yes} / {outcome_no}")
    print(f"      Prices: {price_yes} / {price_no}")
    print(f"      Token ID: {token_id[:40]}...")
    
    # Test orderbook
    print(f"      Testing OrderBook...")
    try:
        book = executor.get_order_book(token_id)
        
        if hasattr(book, 'bids'):
            bids = book.bids if book.bids else []
            asks = book.asks if book.asks else []
        else:
            bids = book.get('bids', [])
            asks = book.get('asks', [])
        
        print(f"      OrderBook: {len(bids)} bids, {len(asks)} asks")
        
        if bids and asks:
            if hasattr(bids[0], 'price'):
                best_bid = float(bids[0].price)
                best_ask = float(asks[0].price)
            elif isinstance(bids[0], dict):
                best_bid = float(bids[0].get('price', 0))
                best_ask = float(asks[0].get('price', 0))
            else:
                best_bid = 0
                best_ask = 0
            
            if best_bid > 0 and best_ask > 0:
                spread = best_ask - best_bid
                print(f"      Bid: ${best_bid:.4f} | Ask: ${best_ask:.4f} | Spread: {spread:.4f}")
                print("      STATUS: LIQUID & TRADEABLE")
            else:
                print("      STATUS: ZERO PRICES")
        else:
            print("      STATUS: EMPTY ORDERBOOK")
            
    except Exception as e:
        print(f"      OrderBook Error: {e}")
    
    tested += 1

# Final summary
print("\n" + "=" * 70)
print("[3] SUMMARY")
print("=" * 70)

if tradeable:
    print(f"""
    MARKETS FOUND: {len(tradeable)} tradeable markets
    
    SYSTEM STATUS: READY FOR TRADING
    
    First tradeable token_id:
    {tradeable[0].get('tokens', [{}])[0].get('token_id', 'N/A')}
    """)
else:
    print("""
    NO TRADEABLE MARKETS FOUND
    
    This could mean:
    1. All markets are currently closed
    2. API access issue
    3. Need to use different filtering
    """)

print("=" * 70)
