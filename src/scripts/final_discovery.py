#!/usr/bin/env python3
"""
FINAL MARKET DISCOVERY TEST - USING SAMPLING MARKETS
This is the correct approach for finding markets with orderbooks.
"""

import httpx
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.execution.clob_executor import PolymarketCLOBExecutor

print("=" * 70)
print("POLYMARKET MARKET DISCOVERY - WORKING SOLUTION")
print("=" * 70)

executor = PolymarketCLOBExecutor(
    host='https://clob.polymarket.com',
    key='0x' + '1' * 64,
    chain_id=137
)

# KEY INSIGHT: Use SAMPLING markets, not simplified markets
print("\n[1] Fetching SAMPLING-SIMPLIFIED-MARKETS (the correct endpoint)...")

all_markets = []
next_cursor = ''
pages = 0
max_pages = 5

while pages < max_pages:
    try:
        resp = executor.client.get_sampling_simplified_markets(next_cursor=next_cursor)
        
        if isinstance(resp, dict):
            batch = resp.get('data', [])
            next_cursor = resp.get('next_cursor', '')
        else:
            batch = resp if isinstance(resp, list) else []
            next_cursor = ''
            
        all_markets.extend(batch)
        pages += 1
        
        accepting = sum(1 for m in batch if m.get('accepting_orders'))
        print(f"    Page {pages}: {len(batch)} markets, {accepting} accepting orders")
        
        if not next_cursor or next_cursor == "LTE=":
            break
    except Exception as e:
        print(f"    Error: {e}")
        break

# Filter tradeable
tradeable = [m for m in all_markets if m.get('accepting_orders') and not m.get('closed')]
print(f"\n    TOTAL: {len(all_markets)} sampling markets")
print(f"    TRADEABLE: {len(tradeable)} accepting orders")

# Test orderbooks
print("\n" + "=" * 70)
print("[2] ORDERBOOK VERIFICATION")
print("=" * 70)

markets_with_orderbook = []

for m in tradeable[:10]:
    tokens = m.get('tokens', [])
    if len(tokens) < 2:
        continue
    
    token_id = tokens[0].get('token_id')
    price_yes = tokens[0].get('price', 0)
    price_no = tokens[1].get('price', 0)
    
    try:
        book = executor.client.get_order_book(token_id)
        
        if hasattr(book, 'bids'):
            bids = book.bids if book.bids else []
            asks = book.asks if book.asks else []
        else:
            bids = book.get('bids', [])
            asks = book.get('asks', [])
        
        if bids and asks:
            if hasattr(bids[0], 'price'):
                best_bid = float(bids[0].price)
                best_ask = float(asks[0].price)
            else:
                best_bid = float(bids[0].get('price', 0))
                best_ask = float(asks[0].get('price', 0))
            
            spread = best_ask - best_bid
            
            markets_with_orderbook.append({
                'token_id': token_id,
                'condition_id': m.get('condition_id'),
                'bids': len(bids),
                'asks': len(asks),
                'best_bid': best_bid,
                'best_ask': best_ask,
                'spread': spread,
                'price_yes': price_yes,
                'price_no': price_no
            })
            
            print(f"\n    Market: {m.get('condition_id', 'N/A')[:20]}...")
            print(f"      Price: Yes={price_yes} / No={price_no}")
            print(f"      Orderbook: {len(bids)} bids / {len(asks)} asks")
            print(f"      Best Bid: {best_bid:.4f} | Best Ask: {best_ask:.4f}")
            print(f"      Spread: {spread:.4f}")
            
    except Exception as e:
        pass  # Skip markets without orderbooks

# Final Summary
print("\n" + "=" * 70)
print("[3] FINAL SUMMARY")
print("=" * 70)

print(f"""
    SYSTEM STATUS: {'FULLY OPERATIONAL' if markets_with_orderbook else 'ISSUE DETECTED'}
    
    Markets Scanned: {len(all_markets)}
    Tradeable (accepting_orders): {len(tradeable)}
    With Active Orderbooks: {len(markets_with_orderbook)}
""")

if markets_with_orderbook:
    print("    READY FOR TRADING!")
    print("\n    Sample Token IDs for testing:")
    for m in markets_with_orderbook[:3]:
        print(f"      {m['token_id']}")
else:
    print("    No markets with orderbooks found at this time.")

print("\n" + "=" * 70)

# Save results to file
results = {
    'timestamp': '2026-02-02T12:36:00Z',
    'total_markets': len(all_markets),
    'tradeable': len(tradeable),
    'with_orderbooks': len(markets_with_orderbook),
    'markets': markets_with_orderbook[:10]
}

with open('market_discovery_results.json', 'w') as f:
    json.dump(results, f, indent=2)
    print("Results saved to market_discovery_results.json")
