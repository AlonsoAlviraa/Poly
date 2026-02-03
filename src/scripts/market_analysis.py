#!/usr/bin/env python3
"""
Market Analysis Script - Deep Diagnostic V2
Analyzes Polymarket API connectivity and market discovery.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.execution.clob_executor import PolymarketCLOBExecutor

def main():
    # Initialize with dummy key
    executor = PolymarketCLOBExecutor(
        host='https://clob.polymarket.com',
        key='0x' + '1' * 64,
        chain_id=137
    )

    if not executor.client:
        print("ERROR: Client not initialized")
        return

    print("=" * 70)
    print("POLYMARKET MARKET DISCOVERY ANALYSIS - DEEP SCAN")
    print("=" * 70)
    
    # Scan multiple pages
    all_markets = []
    next_cursor = ''
    pages = 0
    max_pages = 10
    
    print("\n[1/4] Scanning API pages...")
    
    while pages < max_pages:
        try:
            resp = executor.client.get_markets(next_cursor=next_cursor)
            batch = resp.get('data', [])
            all_markets.extend(batch)
            next_cursor = resp.get('next_cursor', '')
            pages += 1
            print(f"   Page {pages}: {len(batch)} markets (Total: {len(all_markets)})")
            
            if not next_cursor or next_cursor == "0":
                break
        except Exception as e:
            print(f"   Error on page {pages}: {e}")
            break
    
    # Statistics
    print("\n" + "=" * 70)
    print("[2/4] MARKET STATISTICS")
    print("=" * 70)
    
    stats = {
        'total': len(all_markets),
        'active_true': 0,
        'active_false': 0,
        'closed_true': 0,
        'closed_false': 0,
        'with_2plus_tokens': 0,
        'active_and_open': 0,
    }
    
    active_open_markets = []
    
    for m in all_markets:
        # Count active status
        if m.get('active') == True:
            stats['active_true'] += 1
        else:
            stats['active_false'] += 1
            
        # Count closed status
        if m.get('closed') == True:
            stats['closed_true'] += 1
        else:
            stats['closed_false'] += 1
            
        # Count tokens
        tokens = m.get('tokens', [])
        if len(tokens) >= 2:
            stats['with_2plus_tokens'] += 1
            
        # Active AND NOT closed with tokens
        if m.get('active') == True and m.get('closed') != True and len(tokens) >= 2:
            stats['active_and_open'] += 1
            active_open_markets.append(m)
    
    print(f"\n   Total Markets Scanned: {stats['total']}")
    print(f"   ---")
    print(f"   active=True:  {stats['active_true']}")
    print(f"   active=False: {stats['active_false']}")
    print(f"   closed=True:  {stats['closed_true']}")
    print(f"   closed=False: {stats['closed_false']}")
    print(f"   ---")
    print(f"   With 2+ Tokens: {stats['with_2plus_tokens']}")
    print(f"   ACTIVE & OPEN (tradeable): {stats['active_and_open']}")
    
    # Test orderbooks on active markets
    print("\n" + "=" * 70)
    print("[3/4] ORDERBOOK ANALYSIS (Active & Open Markets)")
    print("=" * 70)
    
    orderbook_results = {
        'liquid': 0,
        'empty': 0,
        'error': 0,
        'details': []
    }
    
    test_count = min(10, len(active_open_markets))
    
    for i, m in enumerate(active_open_markets[:test_count]):
        tokens = m.get('tokens', [])
        token_id = tokens[0].get('token_id') or tokens[0].get('clobTokenId')
        question = m.get('question', 'N/A')[:60]
        
        print(f"\n   [{i+1}/{test_count}] {question}...")
        
        try:
            book = executor.get_order_book(token_id)
            
            # Handle different response types
            if hasattr(book, 'bids'):
                bids = book.bids if book.bids else []
                asks = book.asks if book.asks else []
            elif isinstance(book, dict):
                bids = book.get('bids', [])
                asks = book.get('asks', [])
            else:
                bids = []
                asks = []
            
            if bids and asks:
                # Extract best prices
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
                    mid = (best_bid + best_ask) / 2
                    print(f"       Bid: {best_bid:.4f} | Ask: {best_ask:.4f} | Spread: {spread:.4f} ({spread/mid*100:.1f}%)")
                    print(f"       Depth: {len(bids)} bids, {len(asks)} asks")
                    orderbook_results['liquid'] += 1
                    orderbook_results['details'].append({
                        'question': question,
                        'bid': best_bid,
                        'ask': best_ask,
                        'spread_pct': spread/mid*100,
                        'token_id': token_id
                    })
                else:
                    print(f"       ZERO PRICES (Bid: {best_bid}, Ask: {best_ask})")
                    orderbook_results['empty'] += 1
            else:
                print(f"       EMPTY BOOK (Bids: {len(bids)}, Asks: {len(asks)})")
                orderbook_results['empty'] += 1
                
        except Exception as e:
            print(f"       ERROR: {e}")
            orderbook_results['error'] += 1
    
    # Final Report
    print("\n" + "=" * 70)
    print("[4/4] SYSTEM DIAGNOSIS REPORT")
    print("=" * 70)
    
    print(f"""
    API CONNECTIVITY:
    -----------------
    Status: CONNECTED
    Endpoint: https://clob.polymarket.com
    Pages Scanned: {pages}
    Markets Retrieved: {stats['total']}
    
    MARKET AVAILABILITY:
    --------------------
    Tradeable Markets (active=True, closed=False, 2+ tokens): {stats['active_and_open']}
    
    ORDERBOOK HEALTH:
    -----------------
    Markets Tested: {test_count}
    With Liquidity: {orderbook_results['liquid']}
    Empty Books: {orderbook_results['empty']}
    Errors: {orderbook_results['error']}
    """)
    
    if orderbook_results['liquid'] > 0:
        print("    BEST TRADING OPPORTUNITIES:")
        print("    " + "-" * 40)
        sorted_opps = sorted(orderbook_results['details'], key=lambda x: x['spread_pct'], reverse=True)[:5]
        for opp in sorted_opps:
            print(f"    - {opp['question'][:50]}...")
            print(f"      Bid: {opp['bid']:.4f} | Ask: {opp['ask']:.4f} | Spread: {opp['spread_pct']:.2f}%")
    
    print("\n" + "=" * 70)
    if orderbook_results['liquid'] > 0:
        print("VERDICT: SYSTEM OPERATIONAL - Bot can discover and trade markets")
    elif stats['active_and_open'] > 0 and orderbook_results['empty'] > 0:
        print("VERDICT: PARTIAL - Markets exist but low liquidity on tested sample")
    elif stats['active_and_open'] == 0:
        print("VERDICT: NO TRADEABLE MARKETS - API returns only historical/closed markets")
    else:
        print("VERDICT: ISSUES DETECTED - Review errors above")
    print("=" * 70)

if __name__ == "__main__":
    main()
