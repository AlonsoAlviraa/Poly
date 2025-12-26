import asyncio
import aiohttp
import json

async def inspect_sx():
    url = "https://api.sx.bet/markets/active"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            markets = data.get("data", {}).get("markets", [])
            print(f"Total: {len(markets)}")
            if markets:
                # Print everything for the first market
                print(json.dumps(markets[0], indent=2))
                
                print("\nLabels/Names found:")
                for m in markets[:10]:
                    label = m.get('label')
                    o1 = m.get('outcomeOneName')
                    o2 = m.get('outcomeTwoName')
                    team1 = m.get('teamOneName')
                    team2 = m.get('teamTwoName')
                    print(f"  Label: {label} | O1: {o1} | O2: {o2} | T1: {team1} | T2: {team2}")

if __name__ == "__main__":
    asyncio.run(inspect_sx())
