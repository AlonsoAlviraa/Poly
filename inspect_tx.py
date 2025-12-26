import os
from web3 import Web3

# SX Rollup RPC
RPC_URL = "https://rpc.sx-rollup.gelato.digital"
TX_HASH = "0xc983bd4e1481d9ec61ddd18578d03cc1965f518994ce24dba920620eabe98b39"

def check_tx():
    print(f"🕵️ Inspecting TX: {TX_HASH}")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    if not w3.is_connected():
        print("❌ Failed to connect to RPC")
        return

    try:
        receipt = w3.eth.get_transaction_receipt(TX_HASH)
        tx = w3.eth.get_transaction(TX_HASH)
        
        print(f"✅ Status: {receipt.status}")
        print(f"👉 To (Contract): {tx.to}")
        print(f"📄 Logs: {len(receipt.logs)}")
        
        if receipt.logs:
            # The first log usually comes from the token contract for Transfer/Approval
            log_address = receipt.logs[0].address
            print(f"💎 POTENTIAL USDC CONTRACT: {log_address}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_tx()
