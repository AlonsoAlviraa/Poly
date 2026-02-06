
import asyncio
import logging
import json
from datetime import datetime
from src.data.betfair_client import BetfairClient
from src.data.gamma_client import GammaAPIClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TennisDebug")

async def test_betfair_tennis_raw():
    print("\n" + "="*60)
    print("🎾 BETFAIR TENNIS DIAGNOSTIC (RAW)")
    print("="*60)
    
    bf = BetfairClient()
    if not await bf.login():
        print("!! CRITICAL: Betfair Login Failed.")
        return

    # 1. RAW listEvents Request (Tennis ID = 2)
    # NO filters: no dates, no text, no market types
    print("\n>> [1/3] Fetching RAW Tennis Events from Betfair...")
    payload = {
        "filter": {
            "eventTypeIds": ["2"]
        }
    }
    
    # Using _api_request directly to bypass any internal wrapping
    raw_events = await bf._api_request('listEvents', payload)
    
    if raw_events:
        print(f"✅ [Betfair] Raw Tennis Events Found: {len(raw_events)}")
        for e in raw_events[:5]:
            event_obj = e.get('event', {})
            print(f"   - {event_obj.get('name')} (ID: {event_obj.get('id')}) | Markets: {e.get('marketCount', 0)}")
        
        # 2. Inspect marketTypeCodes for the first event
        print("\n>> [2/3] Inspecting available Market Types for Tennis...")
        first_event_id = raw_events[0]['event']['id']
        catalogue_payload = {
            "filter": {
                "eventIds": [first_event_id]
            },
            "maxResults": 20,
            "marketProjection": ["MARKET_DESCRIPTION"]
        }
        
        raw_catalogue = await bf._api_request('listMarketCatalogue', catalogue_payload)
        
        if raw_catalogue:
            market_types = set()
            print(f"   Sample Markets from Event {first_event_id}:")
            for m in raw_catalogue:
                m_type = m.get('description', {}).get('marketType')
                market_types.add(m_type)
                print(f"     - Type: {m_type.ljust(15)} | Name: {m.get('marketName')}")
            
            print(f"\n   Detección de Tipos Disponibles: {market_types}")
        else:
            print("   ⚠️ No markets found for the sample event.")
    else:
        print("   ❌ No Tennis events found for EventTypeId = 2.")

async def test_polymarket_tennis_raw():
    print("\n" + "="*60)
    print("🌊 POLYMARKET TENNIS DIAGNOSTIC (Tag 100008)")
    print("="*60)
    
    gamma = GammaAPIClient()
    print("\n>> [3/3] Fetching ALL Tennis markets from Polymarket (No limit)...")
    
    # Using the tag directly with pagination to be sure
    tennis_markets = []
    offset = 0
    while True:
        # get_markets is sync in the base class, but let's check GammaAPIClient
        # Actually GammaAPIClient has a sync get_markets
        raw_page = gamma.get_markets(
            closed=False, 
            limit=100, 
            offset=offset, 
            order="volume", 
            tag_id="100008"
        )
        
        if not raw_page: break
        tennis_markets.extend(raw_page)
        if len(raw_page) < 100: break
        offset += 100
        if offset >= 1000: break # Safety cap
    
    print(f"✅ [Polymarket] Total Tennis markets found (Tag 100008): {len(tennis_markets)}")
    for m in tennis_markets[:10]:
        print(f"   - {m.get('question')} (ID: {m.get('id')})")

async def main():
    await test_betfair_tennis_raw()
    await test_polymarket_tennis_raw()

if __name__ == "__main__":
    asyncio.run(main())
