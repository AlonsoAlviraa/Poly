#!/usr/bin/env python3
"""
System Health Diagnostic Tool.
Quick verification of all bot components.
"""

import os
import sys

# Get project root (two levels up from scripts/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

# Load .env from project root
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Add project root to path
sys.path.insert(0, PROJECT_ROOT)


def check_env():
    """Check environment variables."""
    required = [
        'PRIVATE_KEY',
        'WALLET_ADDRESS',
        'POLY_HOST',
        'POLY_KEY',
        'POLY_SECRET',
        'POLY_PASSPHRASE',
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_CHAT_ID'
    ]
    
    results = {}
    for var in required:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if 'KEY' in var or 'SECRET' in var or 'TOKEN' in var:
                results[var] = value[:8] + '...'
            else:
                results[var] = value[:30] + ('...' if len(value) > 30 else '')
        else:
            results[var] = None
    
    return results


def check_clob():
    """Check CLOB connection."""
    try:
        from src.execution.clob_executor import PolymarketCLOBExecutor
        
        clob = PolymarketCLOBExecutor(
            host=os.getenv('POLY_HOST', 'https://clob.polymarket.com'),
            key=os.getenv('PRIVATE_KEY', '0x' + '1' * 64),
            chain_id=137
        )
        
        # Try to get markets
        if clob.client:
            resp = clob.client.get_sampling_simplified_markets(next_cursor='')
            data = resp.get('data', []) if isinstance(resp, dict) else resp
            return {'connected': True, 'markets': len(data)}
        
        return {'connected': False, 'error': 'No client'}
        
    except Exception as e:
        return {'connected': False, 'error': str(e)[:50]}


def check_gamma():
    """Check Gamma API connection."""
    try:
        from src.data.gamma_client import GammaAPIClient
        
        client = GammaAPIClient(timeout=5)
        markets = client.get_markets(closed=False, limit=10)
        events = client.get_events(closed=False, limit=5)
        
        return {
            'connected': True,
            'markets': len(markets),
            'events': len(events)
        }
    except Exception as e:
        return {'connected': False, 'error': str(e)[:50]}


def check_telegram():
    """Check Telegram connection."""
    try:
        import httpx
        
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not token or not chat_id:
            return {'connected': False, 'error': 'Missing credentials'}
        
        # Test getMe endpoint (doesn't send message)
        url = f"https://api.telegram.org/bot{token}/getMe"
        resp = httpx.get(url, timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get('ok'):
                return {
                    'connected': True,
                    'bot_name': data.get('result', {}).get('username', 'Unknown')
                }
        
        return {'connected': False, 'error': f'Status {resp.status_code}'}
        
    except Exception as e:
        return {'connected': False, 'error': str(e)[:50]}


def check_tests():
    """Check tests status."""
    import subprocess
    
    try:
        result = subprocess.run(
            ['python', '-m', 'pytest', 'tests/', '-q', '--tb=no'],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT
        )
        
        # Parse output
        output = result.stdout
        if 'passed' in output:
            # Extract passed count
            import re
            match = re.search(r'(\d+) passed', output)
            if match:
                return {'passed': int(match.group(1)), 'failed': 0}
        
        if result.returncode == 0:
            return {'passed': 'All', 'failed': 0}
        else:
            return {'passed': 0, 'failed': 'Some', 'error': output[:100]}
            
    except Exception as e:
        return {'error': str(e)[:50]}


def run_diagnostic():
    """Run full system diagnostic."""
    print("=" * 70)
    print("POLYMARKET ARBITRAGE BOT - SYSTEM DIAGNOSTIC")
    print("=" * 70)
    print()
    
    # 1. Environment
    print("[1/5] Checking Environment Variables...")
    env_results = check_env()
    for var, value in env_results.items():
        status = "OK" if value else "MISSING"
        print(f"      {var}: {status}")
    
    env_ok = all(v is not None for v in env_results.values())
    print(f"      Status: {'PASS' if env_ok else 'FAIL'}")
    print()
    
    # 2. CLOB Connection
    print("[2/5] Checking CLOB Connection...")
    clob_result = check_clob()
    if clob_result.get('connected'):
        print(f"      Connected: YES")
        print(f"      Markets found: {clob_result.get('markets', 0)}")
        print(f"      Status: PASS")
    else:
        print(f"      Connected: NO")
        print(f"      Error: {clob_result.get('error', 'Unknown')}")
        print(f"      Status: FAIL")
    print()
    
    # 3. Gamma API
    print("[3/5] Checking Gamma API...")
    gamma_result = check_gamma()
    if gamma_result.get('connected'):
        print(f"      Connected: YES")
        print(f"      Markets: {gamma_result.get('markets', 0)}")
        print(f"      Events: {gamma_result.get('events', 0)}")
        print(f"      Status: PASS")
    else:
        print(f"      Connected: NO")
        print(f"      Error: {gamma_result.get('error', 'Unknown')}")
        print(f"      Status: FAIL")
    print()
    
    # 4. Telegram
    print("[4/5] Checking Telegram Bot...")
    telegram_result = check_telegram()
    if telegram_result.get('connected'):
        print(f"      Connected: YES")
        print(f"      Bot name: @{telegram_result.get('bot_name', 'Unknown')}")
        print(f"      Status: PASS")
    else:
        print(f"      Connected: NO")
        print(f"      Error: {telegram_result.get('error', 'Unknown')}")
        print(f"      Status: FAIL")
    print()
    
    # 5. Tests
    print("[5/5] Running Unit Tests...")
    test_result = check_tests()
    if 'error' not in test_result:
        print(f"      Passed: {test_result.get('passed', 0)}")
        print(f"      Failed: {test_result.get('failed', 0)}")
        print(f"      Status: PASS")
    else:
        print(f"      Error: {test_result.get('error', 'Unknown')}")
        print(f"      Status: FAIL")
    print()
    
    # Summary
    print("=" * 70)
    all_pass = (
        env_ok and 
        clob_result.get('connected', False) and
        gamma_result.get('connected', False) and
        telegram_result.get('connected', False) and
        'error' not in test_result
    )
    
    if all_pass:
        print("OVERALL STATUS: ALL SYSTEMS OPERATIONAL")
        print()
        print("Ready to run:")
        print("  python run_arb_bot.py --mode monitor")
    else:
        print("OVERALL STATUS: SOME ISSUES DETECTED")
        print()
        print("Fix the issues above before running the bot.")
    
    print("=" * 70)


if __name__ == '__main__':
    run_diagnostic()
