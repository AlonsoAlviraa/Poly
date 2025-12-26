import asyncio
import aiohttp
import json

async def inspect_sx_meta():
    url = "https://api.sx.bet/markets/active"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            print("Response Keys:", data.keys())
            if "data" in data:
                print("Data Keys:", data["data"].keys())
                # Check meta/pagination
                for key in data["data"]:
                    if key != "markets":
                        print(f"Key '{key}':", data["data"][key])

if __name__ == "__main__":
    asyncio.run(inspect_sx_meta())
