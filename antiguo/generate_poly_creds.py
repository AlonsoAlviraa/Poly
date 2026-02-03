from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON

# User's private key
PK = "0xa31f000a223c023c542060055b5abc05ca1c110a3c5255863316650c70448512"

def main():
    print("Generating Polymarket API Keys...")
    try:
        # Initialize client with Private Key on Polygon (Chain ID 137)
        client = ClobClient(
            host="https://clob.polymarket.com",
            key=PK,
            chain_id=137
        )
        
        # Create API Key
        creds = client.create_api_key()
        
        print("\n--- CREDENTIALS GENERATED ---")
        print(f"POLY_API_KEY={creds.api_key}")
        print(f"POLY_API_SECRET={creds.api_secret}")
        print(f"POLY_PASSPHRASE={creds.api_passphrase}")
        print("-----------------------------\n")
        
    except Exception as e:
        print(f"Error generating keys: {e}")

if __name__ == "__main__":
    main()
