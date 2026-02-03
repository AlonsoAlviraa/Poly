
import asyncio
import aiohttp
import json

GAMMA_URL = "https://gamma-api.polymarket.com/events?limit=20&closed=false&order=volume24hr&ascending=false"
CLOB_URL = "https://clob.polymarket.com"

async def fetch_book(session, token_id):
    try:
        url = f"{CLOB_URL}/book?token_id={token_id}"
        async with session.get(url, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                print(f"[ERR] Book fetch {token_id}: {response.status}")
                return None
    except Exception as e:
        print(f"[EXC] {e}")
        return None

async def main():
    print("[DEBUG] MEGA DEBUG: Checking Top 20 Markets manually...")
    
    async with aiohttp.ClientSession() as session:
        # 1. Fetch Events
        print("1. Fetching Top 20 Events from Gamma...")
        async with session.get(GAMMA_URL) as resp:
            events = await resp.json()
            
        print(f"   Fetched {len(events)} events.")
        
        for i, event in enumerate(events):
            print(f"\n--- Event {i+1}: {event['title'][:50]} ---")
            markets = event.get('markets', [])
            
            for m in markets:
                liq = m.get('liquidityNum', 0)
                q_text = m['question'].encode('ascii', 'ignore').decode()
                print(f"   Market: {q_text[:50]} (Liq: ${liq})")
                
                if liq < 100:
                    print("   [REJECT] Low Liquidity")
                    continue
                    
                token_ids = m.get('clobTokenIds')
                if not token_ids:
                    print("   [SKIP] No Token IDs (AMM only?)")
                    continue
                
                try:
                    if isinstance(token_ids, str): ids = json.loads(token_ids)
                    else: ids = token_ids
                except:
                    continue
                    
                if len(ids) != 2:
                    print(f"   [SKIP] Not binary (IDs: {len(ids)})")
                    continue
                    
                yes_id, no_id = ids[0], ids[1]
                
                # Fetch Books
                print(f"   Fetching books for YES/NO...")
                yes_book = await fetch_book(session, yes_id)
                no_book = await fetch_book(session, no_id)
                
                if not yes_book or not no_book:
                    print("   [FAIL] Could not get books.")
                    continue
                    
                # Analyze Basic Prices
                try:
                    yes_ask = float(yes_book['asks'][0]['price']) if yes_book['asks'] else None
                    yes_bid = float(yes_book['bids'][0]['price']) if yes_book['bids'] else None
                    no_ask = float(no_book['asks'][0]['price']) if no_book['asks'] else None
                    no_bid = float(no_book['bids'][0]['price']) if no_book['bids'] else None
                    
                    print(f"   Prices:")
                    print(f"     YES: Bid {yes_bid} / Ask {yes_ask}")
                    print(f"     NO : Bid {no_bid} / Ask {no_ask}")
                    
                    # Check SPLIT (Sell)
                    # Sell Revenue = YES_BID + NO_BID
                    if yes_bid and no_bid:
                        revenue = yes_bid + no_bid
                        print(f"     [CHECK SPLIT] BidSum = {revenue:.4f}")
                        if revenue > 1.00:
                            print(f"     [!] PROFITABLE SPLIT! +{(revenue-1.0)*100:.2f}%")
                        else:
                            print(f"     [NO] Split needs > 1.00")
                            
                    # Check MERGE (Buy)
                    # Buy Cost = YES_ASK + NO_ASK
                    if yes_ask and no_ask:
                        cost = yes_ask + no_ask
                        print(f"     [CHECK MERGE] AskSum = {cost:.4f}")
                        if cost < 1.00:
                             print(f"     [!] PROFITABLE MERGE! +{(1.0-cost)*100:.2f}%")
                        else:
                             print(f"     [NO] Merge needs < 1.00")
                             
                except Exception as e:
                    print(f"   [ERR] Analyzing prices: {e}")
                    
            await asyncio.sleep(0.5) # Rate limit respect

if __name__ == "__main__":
    asyncio.run(main())
