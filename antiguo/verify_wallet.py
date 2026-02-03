import os
from dotenv import load_dotenv
from eth_account import Account
import json
from web3 import Web3

load_dotenv('/home/ubuntu/arbitrage_platform/.env')

def main():
    pk = os.getenv('PRIVATE_KEY')
    expected_addr = os.getenv('WALLET_ADDRESS')
    
    print(f"--- WALLET VERIFICATION ---")
    
    if not pk:
        print("❌ No PRIVATE_KEY in .env")
        return
        
    try:
        # Derive Address
        acct = Account.from_key(pk)
        print(f"Private Key: {pk[:6]}...{pk[-4:]}")
        print(f"Derived Address: {acct.address}")
        print(f"Expected Address: {expected_addr}")
        
        if acct.address.lower() == expected_addr.lower():
            print("✅ Address Match!")
        else:
            print("❌ ADDRESS MISMATCH! content of .env is inconsistent.")
            
        # Check Balance (Polygon)
        # Using a public RPC for checks
        w3 = Web3(Web3.HTTPProvider('https://polygon-rpc.com'))
        if w3.is_connected():
            # Matic Balance
            bal = w3.eth.get_balance(acct.address)
            # Use format instead of f-string with quotes inside if confusing shell
            print(f"POL/MATIC Balance: {w3.from_wei(bal, 'ether')}")
            
            # USDC Balance (0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359)
            usdc_contract = '0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359'
            abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
            contract = w3.eth.contract(address=usdc_contract, abi=abi)
            usdc_bal = contract.functions.balanceOf(acct.address).call()
            print(f"USDC Balance: {usdc_bal / 10**6}")
            
            # Bridged USDC (USDC.e) - 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
            usdc_e_contract = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
            contract_e = w3.eth.contract(address=usdc_e_contract, abi=abi)
            usdc_e_bal = contract_e.functions.balanceOf(acct.address).call()
            print(f"USDC.e Balance: {usdc_e_bal / 10**6}")

        else:
            print("Could not connect to RPC")
            
    except Exception as e:
        print(f"Error deriving wallet: {e}")

if __name__ == '__main__':
    main()
