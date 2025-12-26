import os
import aiohttp
import asyncio
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("SX_BET_API_KEY")
API_URL = "https://api.sx.bet/user/balance"  # Hypothesis, or /balance
# Alternate hypothesis: https://api.sx.bet/account/balance

async def check_api_balance():
    if not API_KEY:
        print("❌ No API Key found")
        return

    async with aiohttp.ClientSession() as session:
        headers = {
            "X-Api-Key": API_KEY,
            "Accept": "application/json"
        }
        
        # Try a few common endpoints for balance
        endpoints = [
            "https://api.sx.bet/balance",
            "https://api.sx.bet/user/balance",
            "https://api.sx.bet/users/balance", # sometimes plural
            "https://api.sx.bet/account",
        ]

        print(f"🔑 Using API Key: {API_KEY[:6]}...")

        for url in endpoints:
            try:
                print(f"Testing {url}...")
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"✅ SUCCESS on {url}")
                        print(data)
                        return
                    else:
                        print(f"❌ Failed: {resp.status}")
            except Exception as e:
                print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_api_balance())
