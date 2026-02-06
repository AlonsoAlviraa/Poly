
import json
import requests

url = "https://gamma-api.polymarket.com/markets?limit=1&closed=false&tag_id=100639"
resp = requests.get(url)
data = resp.json()

if data:
    market = data[0]
    print(f"Market: {market.get('question')}")
    print(f"ID: {market.get('id')}")
    print(f"Condition ID: {market.get('conditionId')}")
    print(f"Tokens: {json.dumps(market.get('tokens'), indent=2)}")
    
    # Check if 'clobTokenIds' exists (common in some Gamma versions)
    print(f"CLOB Token IDs: {market.get('clobTokenIds')}")
else:
    print("No markets found")
