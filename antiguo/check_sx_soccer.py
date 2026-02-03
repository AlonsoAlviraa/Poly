import asyncio
from src.exchanges.sx_bet_client import SXBetClient

async def check_sx_soccer():
    client = SXBetClient()
    markets = await client.get_active_markets()
    soccer = [m for m in markets if m.get('sportLabel') == 'Soccer']
    print(f"Total SX Soccer: {len(soccer)}")
    for m in soccer:
        print(f"  - {m.get('label')}")

if __name__ == "__main__":
    asyncio.run(check_sx_soccer())
