import aiohttp
import asyncio

async def test_depth():
    token_id = "0x8ed3cfb15b8dc545bc852f1760f66ac1abae474c02856bbed17c5f9c673af26c"
    print(f"Testing Token ID: {token_id}")
    
    url = "https://clob.polymarket.com/book"
    params = {"token_id": token_id}
    
    print(f"Requesting {url} with params {params}...")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            print(f"Status: {response.status}")
            text = await response.text()
            print(f"Response: {text[:200]}")
            
    # Try decimal format if hex fails
    try:
        decimal_id = str(int(token_id, 16))
        print(f"\nTesting Decimal ID: {decimal_id}")
        params_dec = {"token_id": decimal_id}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params_dec) as response:
                print(f"Status: {response.status}")
                text = await response.text()
                print(f"Response: {text[:200]}")
    except Exception as e:
        print(f"Conversion error: {e}")

if __name__ == "__main__":
    asyncio.run(test_depth())
