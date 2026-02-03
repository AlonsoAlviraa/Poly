#!/usr/bin/env python3
"""
Complete System Diagnostic for Arbitrage Bot
Checks: ENV vars, APIs, Wallet connections, Contract addresses
"""

import os
import sys
from dotenv import load_dotenv
import asyncio

print("="*70)
print("🔍 COMPLETE SYSTEM DIAGNOSTIC")
print("="*70)

# 1. Check .env file
print("\n📄 STEP 1: Checking .env configuration...")
load_dotenv()

required_vars = [
    "MODE", "PRIVATE_KEY", "WALLET_ADDRESS",
    "POLY_KEY", "POLY_SECRET", "POLY_PASSPHRASE", "POLY_HOST",
    "SX_BET_API_KEY"
]

missing = []
for var in required_vars:
    value = os.getenv(var)
    if not value:
        missing.append(var)
        print(f"   ❌ {var}: MISSING")
    else:
        # Mask sensitive data
        if "KEY" in var or "SECRET" in var or "PASS" in var:
            display = value[:8] + "..." if len(value) > 8 else "***"
        else:
            display = value
        print(f"   ✅ {var}: {display}")

if missing:
    print(f"\n⚠️  Missing variables: {missing}")
else:
    print("\n✅ All ENV variables present")

# 2. Test Polygon RPC
print("\n🟣 STEP 2: Testing Polygon RPC connection...")
try:
    from web3 import Web3
    polygon_rpc = "https://polygon-rpc.com"
    w3_poly = Web3(Web3.HTTPProvider(polygon_rpc))
    if w3_poly.is_connected():
        block = w3_poly.eth.block_number
        print(f"   ✅ Polygon RPC connected (Block: {block})")
    else:
        print("   ❌ Polygon RPC failed to connect")
except Exception as e:
    print(f"   ❌ Polygon RPC Error: {e}")

# 3. Test SX Network RPC
print("\n🔵 STEP 3: Testing SX Network RPC connection...")
try:
    sx_rpc = "https://rpc.sx.technology"
    w3_sx = Web3(Web3.HTTPProvider(sx_rpc))
    if w3_sx.is_connected():
        block = w3_sx.eth.block_number
        print(f"   ✅ SX Network RPC connected (Block: {block})")
    else:
        print("   ❌ SX Network RPC failed to connect")
except Exception as e:
    print(f"   ❌ SX Network RPC Error: {e}")

# 4. Check wallet balance on Polygon (native token)
print("\n💰 STEP 4: Checking native token balances...")
try:
    wallet_addr = os.getenv("WALLET_ADDRESS")
    if wallet_addr:
        # POL balance
        bal_wei = w3_poly.eth.get_balance(wallet_addr)
        bal_pol = w3_poly.from_wei(bal_wei, 'ether')
        print(f"   Polygon (POL): {bal_pol:.4f} POL")
        
        # SX balance
        bal_wei_sx = w3_sx.eth.get_balance(wallet_addr)
        bal_sx = w3_sx.from_wei(bal_wei_sx, 'ether')
        print(f"   SX Network (SX): {bal_sx:.4f} SX")
        
        if bal_pol < 0.1:
            print("   ⚠️  Low POL balance for gas")
        if bal_sx < 0.1:
            print("   ⚠️  Low SX balance for gas")
    else:
        print("   ❌ No wallet address configured")
except Exception as e:
    print(f"   ❌ Error checking balances: {e}")

# 5. Check USDC contract addresses
print("\n💵 STEP 5: Verifying USDC contract addresses...")
USDC_POLYGON = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # Native USDC on Polygon
USDC_SX = "0xe2aa35C2039Bd0Ff196A6Ef99523CC0D3972ae3e"  # USDC on SX Network

print(f"   Polygon USDC: {USDC_POLYGON}")
print(f"   SX USDC:      {USDC_SX}")

# Try to read USDC balance
try:
    from web3 import Web3
    erc20_abi = [
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "", "type": "uint8"}],
            "type": "function"
        }
    ]
    
    usdc_poly_contract = w3_poly.eth.contract(
        address=Web3.to_checksum_address(USDC_POLYGON),
        abi=erc20_abi
    )
    usdc_sx_contract = w3_sx.eth.contract(
        address=Web3.to_checksum_address(USDC_SX),
        abi=erc20_abi
    )
    
    wallet_addr = os.getenv("WALLET_ADDRESS")
    if wallet_addr:
        # Polygon USDC
        bal_poly = usdc_poly_contract.functions.balanceOf(
            Web3.to_checksum_address(wallet_addr)
        ).call()
        decimals_poly = usdc_poly_contract.functions.decimals().call()
        bal_poly_formatted = bal_poly / (10 ** decimals_poly)
        print(f"   Polygon USDC Balance: ${bal_poly_formatted:.2f}")
        
        # SX USDC
        bal_sx = usdc_sx_contract.functions.balanceOf(
            Web3.to_checksum_address(wallet_addr)
        ).call()
        decimals_sx = usdc_sx_contract.functions.decimals().call()
        bal_sx_formatted = bal_sx / (10 ** decimals_sx)
        print(f"   SX USDC Balance: ${bal_sx_formatted:.2f}")
        
except Exception as e:
    print(f"   ❌ USDC Balance Error: {e}")

# 6. Test Polymarket API
print("\n📊 STEP 6: Testing Polymarket API...")
try:
    import aiohttp
    async def test_poly():
        async with aiohttp.ClientSession() as session:
            url = "https://gamma-api.polymarket.com/events?limit=1&active=true"
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"   ✅ Polymarket API working (Got {len(data)} events)")
                else:
                    print(f"   ❌ Polymarket API returned {resp.status}")
    
    asyncio.run(test_poly())
except Exception as e:
    print(f"   ❌ Polymarket API Error: {e}")

# 7. Test SX Bet API
print("\n🎲 STEP 7: Testing SX Bet API...")
try:
    async def test_sx():
        api_key = os.getenv("SX_BET_API_KEY")
        if not api_key:
            print("   ❌ No SX_BET_API_KEY found")
            return
            
        async with aiohttp.ClientSession() as session:
            headers = {"X-Api-Key": api_key}
            url = "https://api.sx.bet/markets/active"
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"   ✅ SX Bet API working (Got {len(data.get('data', []))} markets)")
                else:
                    text = await resp.text()
                    print(f"   ❌ SX Bet API returned {resp.status}: {text[:100]}")
    
    asyncio.run(test_sx())
except Exception as e:
    print(f"   ❌ SX Bet API Error: {e}")

print("\n" + "="*70)
print("✅ DIAGNOSTIC COMPLETE")
print("="*70)
