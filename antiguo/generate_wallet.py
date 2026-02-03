#!/usr/bin/env python3
"""
Wallet Generator for Polygon/Ethereum
Creates a new wallet with private key and address.
"""

from eth_account import Account

def generate_wallet():
    """Generate a new Ethereum/Polygon wallet"""
    account = Account.create()
    
    print("=" * 60)
    print("🔐 NEW WALLET GENERATED")
    print("=" * 60)
    print(f"\nAddress:     {account.address}")
    print(f"Private Key: {account.key.hex()}")
    print("\n" + "=" * 60)
    print("⚠️  SECURITY WARNING:")
    print("   1. NEVER share your private key with anyone")
    print("   2. Store it in a secure password manager")
    print("   3. Add it to .env file (NOT in git)")
    print("   4. Keep a backup in a safe place")
    print("=" * 60)
    print("\n📝 Next steps:")
    print("   1. Copy private key to .env file")
    print("   2. Send USDC to the address above")
    print("   3. Bridge half to SX Network")
    print("=" * 60)

if __name__ == "__main__":
    generate_wallet()
