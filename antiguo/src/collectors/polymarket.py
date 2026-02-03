import aiohttp
import asyncio
from datetime import datetime, timedelta
from py_clob_client.client import ClobClient
import os
from config import POLY_HOST, POLY_KEY, POLY_CHAIN_ID

class PolymarketClient:
    def __init__(self):
        self.gamma_url = "https://gamma-api.polymarket.com/events"
        # Keep ClobClient for potential execution or deep orderbook if needed
        try:
            self.clob_client = ClobClient(
                host=POLY_HOST,
                key=os.getenv("PRIVATE_KEY"),
                chain_id=POLY_CHAIN_ID
            )
        except Exception as e:
            print(f"Warning: ClobClient init failed: {e}")
            self.clob_client = None

    async def search_events_async(self, keywords=None):
        """
        Fetches ALL active events from Polymarket via pagination.
        Removed sports filter to maximize matching potential.
        """
        all_events = []
        
        params = {
            "closed": "false",
            "limit": 100,
            "offset": 0,
            "order": "volume24hr",  # Most active markets first
            "ascending": "false"
        }
        
        async with aiohttp.ClientSession() as session:
            # Fetch up to 2000 events (20 pages)
            for offset in range(0, 2000, 100):
                params["offset"] = offset
                try:
                    async with session.get(self.gamma_url, params=params, timeout=15) as response:
                        response.raise_for_status()
                        data = await response.json()
                        if not data:
                            break
                        
                        # Filter out aggregated markets
                        filtered_data = [e for e in data if "More Markets" not in e.get("title", "")]
                        all_events.extend(filtered_data)
                                
                except Exception as e:
                    print(f"Error fetching Polymarket events (offset {offset}): {e}")
                    break
        
        print(f"Total Polymarket Events Fetched: {len(all_events)}")
        return all_events

    async def get_orderbook_depth_async(self, token_id):
        """
        Fetches orderbook depth asynchronously using direct CLOB API.
        Returns both bids and asks.
        """
        url = f"{POLY_HOST}/book"
        params = {"token_id": token_id}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    asks = data.get("asks", [])
                    bids = data.get("bids", [])
                    
                    # Ensure numeric types
                    for order in asks:
                        order['price'] = float(order.get('price', 0))
                        order['size'] = float(order.get('size', 0))
                        
                    for order in bids:
                        order['price'] = float(order.get('price', 0))
                        order['size'] = float(order.get('size', 0))
                    
                    return {"bids": bids, "asks": asks}
            except Exception as e:
                print(f"Error fetching depth for {token_id}: {e}")
                return {"bids": [], "asks": []}

if __name__ == "__main__":
    async def test():
        client = PolymarketClient()
        print("Fetching Polymarket events async...")
        events = await client.get_events_async()
        print(f"Fetched {len(events)} events.")
        
        if events:
            # Test depth for first event's first market
            m = events[0].get("markets", [])[0]
            t = m.get("clobTokenIds", [])[0]
            p, s, _ = await client.get_orderbook_depth_async(t)
            print(f"Depth for {t}: Price {p}, Size {s}")

    asyncio.run(test())
