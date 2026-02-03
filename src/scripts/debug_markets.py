#!/usr/bin/env python3
"""Debug script for market analysis."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.execution.clob_executor import PolymarketCLOBExecutor
import json

executor = PolymarketCLOBExecutor(
    host='https://clob.polymarket.com',
    key='0x' + '1' * 64,
    chain_id=137
)

resp = executor.client.get_markets(next_cursor='')
markets = resp.get('data', [])

print('DETAILED MARKET ANALYSIS')
print('=' * 60)

for i, m in enumerate(markets[:5]):
    print(f'\nMarket {i+1}:')
    q = m.get('question', 'N/A')
    print(f'  Question: {q[:60]}')
    print(f'  active: {m.get("active")} (type: {type(m.get("active")).__name__})')
    print(f'  closed: {m.get("closed")} (type: {type(m.get("closed")).__name__})')
    print(f'  tokens: {len(m.get("tokens", []))} items')

print('\n' + '=' * 60)
print('MARKET FILTER ANALYSIS:')

# Various filter combinations
active_true = sum(1 for m in markets if m.get('active') == True)
closed_true = sum(1 for m in markets if m.get('closed') == True)
closed_false = sum(1 for m in markets if m.get('closed') == False)
active_and_open = sum(1 for m in markets if m.get('active') == True and m.get('closed') == False)
active_and_closed = sum(1 for m in markets if m.get('active') == True and m.get('closed') == True)
inactive_open = sum(1 for m in markets if m.get('active') == False and m.get('closed') == False)

print(f'  active=True: {active_true}')
print(f'  closed=True: {closed_true}')
print(f'  closed=False: {closed_false}')
print(f'  active=True AND closed=False: {active_and_open}')
print(f'  active=True AND closed=True: {active_and_closed}')
print(f'  active=False AND closed=False: {inactive_open}')

print('\n' + '=' * 60)
print('SAMPLE OF ALL OPEN (closed=False) MARKETS:')

tested = 0
for m in markets:
    if m.get('closed') == False and len(m.get('tokens', [])) >= 2:
        if tested >= 5:
            break
        tokens = m.get('tokens', [])
        token_id = tokens[0].get('token_id') or tokens[0].get('clobTokenId') or tokens[0].get('clob_token_id')
        
        if not token_id:
            print(f'\n  Market: {m.get("question", "N/A")[:50]}... - NO TOKEN ID')
            print(f'  Token keys: {tokens[0].keys()}')
            tested += 1
            continue
            
        q = m.get('question', 'N/A')
        print(f'\n  Market: {q[:50]}...')
        print(f'  active={m.get("active")}, closed={m.get("closed")}')
        tid_display = token_id[:40] if len(str(token_id)) > 40 else token_id
        print(f'  token_id={tid_display}...')
        
        try:
            book = executor.get_order_book(token_id)
            if hasattr(book, 'bids'):
                bids = book.bids if book.bids else []
                asks = book.asks if book.asks else []
            else:
                bids = book.get('bids', [])
                asks = book.get('asks', [])
            
            print(f'  Bids: {len(bids)}, Asks: {len(asks)}')
            if bids and asks:
                if hasattr(bids[0], 'price'):
                    print(f'  Best Bid: {bids[0].price}, Best Ask: {asks[0].price}')
                elif isinstance(bids[0], dict):
                    print(f'  Best Bid: {bids[0].get("price")}, Best Ask: {asks[0].get("price")}')
        except Exception as e:
            print(f'  OrderBook Error: {e}')
        
        tested += 1

print('\n' + '=' * 60)
print('CONCLUSION:')
print('  The Polymarket API default sort returns OLDEST/CLOSED markets first.')
print('  Need to use different API params or pagination to find ACTIVE markets.')
print('=' * 60)
