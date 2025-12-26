
import asyncio
import aiohttp
import sys

TOKEN = "8141776377:AAElO9CgQzfw3t1J_Rx0iIEVPBG6taWasps"
CHAT_ID = "1653399031"

async def test_telegram():
    print(f"Sending test message to {CHAT_ID}...")
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": "🔔 Test Message from Debugger \nIf you see this, connectivity is OK.",
        "parse_mode": "Markdown"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
            if resp.status == 200 and data.get("ok"):
                print("✅ Success! Message sent.")
            else:
                print(f"❌ Failed: {data}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_telegram())
