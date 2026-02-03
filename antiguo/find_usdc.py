import os
import sys
from eth_account import Account
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

# SX Rollup configuration
SX_RPC = "https://rpc.sx-rollup.gelato.digital"
# Common USDC contract possibilities on SX (from standard lists + older chain)
POSSIBLE_USDC = [
    "0xe2aa35C2039Bd0Ff196A6Ef99523CC0D3972ae3e", # Old logic?
    "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", # Polygon POS USDC (sometimes reused)
    "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063", # DAI (for sanity check)
    "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8", # Arbitrum USDC (sometimes reused)
]

ADDRESS = "0x1AE485FEfFa7aeb8f4cc036d3D182E6E77963172"

def find_usdc():
    print("🔎 Searching for your USDC on SX Network...")
    w3 = Web3(Web3.HTTPProvider(SX_RPC))
    
    if not w3.is_connected():
        print("❌ Cannot connect to RPC")
        return

    # Generic ERC20 ABI
    abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
    
    # Check known addresses
    found = False
    for addr in POSSIBLE_USDC:
        try:
            checksum_addr = w3.to_checksum_address(addr)
            contract = w3.eth.contract(address=checksum_addr, abi=abi)
            bal = contract.functions.balanceOf(ADDRESS).call()
            if bal > 0:
                print(f"🎉 FOUND IT! Address: {addr}")
                print(f"💰 Balance: {bal / 1e6} USDC")
                found = True
                break
        except Exception:
            pass

    if not found:
        print("❌ Could not find USDC in standard addresses. Need to check Explorer manualy.")
        print("   Please check your transaction hash on https://explorer.sx.technology and copy the Token Address.")

if __name__ == "__main__":
    find_usdc()
