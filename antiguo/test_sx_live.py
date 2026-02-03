import os
import sys
from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3

# Force LIVE settings
os.environ["MODE"] = "LIVE"
load_dotenv()

def test_sx_transaction():
    print("="*60)
    print("🧪 SX NETWORK LIVE TEST (Self-Transfer)")
    print("="*60)
    
    # 1. Setup
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        print("❌ CRITICAL: No Private Key found")
        return

    account = Account.from_key(private_key)
    address = account.address
    print(f"📍 Wallet: {address}")
    
    # Connect to SX Network
    rpc_url = "https://rpc.sx.technology"
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    
    if not w3.is_connected():
        print("❌ Connection Failed: Could not connect to SX RPC")
        return
        
    print("✅ Connected to SX Network node")

    # 2. Check Balance
    balance_wei = w3.eth.get_balance(address)
    balance_sx = w3.from_wei(balance_wei, 'ether')
    print(f"💰 Balance: {balance_sx:.6f} SX")
    
    if balance_sx < 0.002:
        print("❌ INSUFFICIENT GAS: Need at least 0.002 SX to test")
        return

    # 3. Build Transaction (Self-transfer 0.0001 SX)
    print("\n📤 Preparing test transaction...")
    tx_params = {
        'nonce': w3.eth.get_transaction_count(address),
        'to': address,
        'value': w3.to_wei(0.0001, 'ether'),
        'gas': 21000,
        'gasPrice': w3.eth.gas_price,
        'chainId': 416  # SX Network Chain ID
    }
    
    # 4. Sign & Send
    try:
        signed_tx = w3.eth.account.sign_transaction(tx_params, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        print(f"🚀 Transaction SENT! Hash: {w3.to_hex(tx_hash)}")
        print("⏳ Waiting for confirmation...")
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        
        if receipt.status == 1:
            print("\n✅ SUCCESS: Transaction confirmed on blockchain!")
            print(f"   Block: {receipt.blockNumber}")
            print(f"   Gas Used: {receipt.gasUsed}")
        else:
            print("\n❌ FAILURE: Transaction reverted on-chain")
            
    except Exception as e:
        print(f"\n❌ ERROR SENDING TRANSACTION: {e}")

if __name__ == "__main__":
    test_sx_transaction()
