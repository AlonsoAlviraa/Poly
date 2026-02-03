#!/usr/bin/env python3
"""Test sampling markets API."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.execution.clob_executor import PolymarketCLOBExecutor
import inspect

executor = PolymarketCLOBExecutor(
    host='https://clob.polymarket.com',
    key='0x' + '1' * 64,
    chain_id=137
)

# Check sampling markets
print('get_sampling_markets signature:')
sig = inspect.signature(executor.client.get_sampling_markets)
print(f'  {sig}')

print()
print('get_sampling_simplified_markets signature:')
sig = inspect.signature(executor.client.get_sampling_simplified_markets)
print(f'  {sig}')

# Test it
print()
print('Testing get_sampling_simplified_markets...')
try:
    result = executor.client.get_sampling_simplified_markets()
    print(f'Type: {type(result)}')
    if isinstance(result, list):
        print(f'Count: {len(result)}')
        if result:
            m = result[0]
            print(f'First market:')
            if isinstance(m, dict):
                print(f'  Keys: {list(m.keys())}')
                q = m.get("question", "N/A")
                print(f'  question: {q[:50]}')
                print(f'  active: {m.get("active")}')
                print(f'  closed: {m.get("closed")}')
                tokens = m.get("tokens", [])
                print(f'  tokens count: {len(tokens)}')
                if tokens:
                    t = tokens[0]
                    print(f'  first token: {t}')
            else:
                print(f'  Type: {type(m)}')
except Exception as e:
    print(f'Error: {e}')

print()
print('Testing get_sampling_markets...')
try:
    result = executor.client.get_sampling_markets()
    print(f'Type: {type(result)}')
    if isinstance(result, list):
        print(f'Count: {len(result)}')
        if result:
            m = result[0]
            print(f'First market:')
            if isinstance(m, dict):
                q = m.get("question", "N/A")
                print(f'  question: {q[:50]}')
                print(f'  active: {m.get("active")}')
                print(f'  closed: {m.get("closed")}')
                tokens = m.get("tokens", [])
                print(f'  tokens count: {len(tokens)}')
                if tokens:
                    t = tokens[0]
                    tid = t.get('token_id') or t.get('clobTokenId')
                    print(f'  token_id: {tid[:50] if tid else "NONE"}...')
except Exception as e:
    print(f'Error: {e}')
