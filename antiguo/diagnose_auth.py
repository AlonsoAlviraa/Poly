import os
import sys
import base64
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

def try_auth(name, creds, pk, host, chain_id):
    print(f"\nScanning: {name}")
    for sig_type in [0, 1, 2]:
        try:
            print(f"  > Testing SigType {sig_type}...", end=" ")
            client = ClobClient(
                host, 
                key=pk, 
                chain_id=chain_id, 
                creds=creds,
                signature_type=sig_type
            )
            keys = client.get_api_keys()
            print(f"✅✅ SUCCESS! Strategy '{name}' + SigType {sig_type} worked!")
            print(f"Found keys: {len(keys)}")
            return True
        except Exception as e:
            print(f"❌ Failed")
    return False

def main():
    print("🕵️ STARTING CREDENTIAL DIAGNOSTIC...")
    
    pk = os.getenv('PRIVATE_KEY')
    host = "https://clob.polymarket.com"
    chain_id = 137
    
    api_key = os.getenv('POLY_KEY')
    secret = os.getenv('POLY_SECRET')
    passphrase = os.getenv('POLY_PASSPHRASE')
    
    print(f"API KEY: {api_key}")
    
    # Strategy 1: AS IS (Raw String)
    c1 = ApiCreds(api_key, secret, passphrase)
    if try_auth("Raw String", c1, pk, host, chain_id): return

    # Strategy 2: Passphrase Hex -> Base64
    # Maybe the input is Hex which represents the Bytes of a Base64 string?
    try:
        pass_bytes = bytes.fromhex(passphrase)
        pass_b64 = base64.b64encode(pass_bytes).decode('utf-8')
        c2 = ApiCreds(api_key, secret, pass_b64)
        if try_auth(f"Hex->Base64 ({pass_b64})", c2, pk, host, chain_id): return
    except:
        pass

    # Strategy 3: Passphrase is Base64? No, it's hex.
    
    # Strategy 4: Try swapping Secret and Passphrase? (Unlikely)
    
    print("\n⚠️ All strategies failed. Credentials mismatch confirmed.")

if __name__ == "__main__":
    main()
