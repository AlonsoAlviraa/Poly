
import asyncio
import json
import os
from datetime import datetime
from src.data.gamma_client import GammaAPIClient
from src.data.sx_bet_client import SXBetClient
from src.data.betfair_client import BetfairClient

# Custom JSON Encoder for datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

async def dump_data():
    print("🚀 STARTING DATA DUMP FOR FORENSICS...")
    
    # 1. POLYMARKET
    print(">> Fetching Polymarket...")
    gamma = GammaAPIClient()
    try:
        poly_markets = await gamma.get_all_match_markets(limit=500)
        with open('dump_poly.json', 'w', encoding='utf-8') as f:
            json.dump(poly_markets, f, indent=2, cls=DateTimeEncoder)
        print(f"✅ Saved {len(poly_markets)} Polymarket events to dump_poly.json")
    except Exception as e:
        print(f"❌ Error fetching Poly: {e}")
    finally:
        if hasattr(gamma, 'close'): await gamma.close()

    # 2. SX BET
    print(">> Fetching SX Bet...")
    sx = SXBetClient()
    try:
        sx_markets = await sx.get_markets_standardized()
        # Clean non-serializable objects
        for m in sx_markets:
            if '_sx_market_obj' in m:
                del m['_sx_market_obj']
                
        with open('dump_sx.json', 'w', encoding='utf-8') as f:
            json.dump(sx_markets, f, indent=2, cls=DateTimeEncoder)
        print(f"✅ Saved {len(sx_markets)} SX Bet events to dump_sx.json")
    except Exception as e:
        print(f"❌ Error fetching SX: {e}")
    finally:
        await sx.close()

    # 3. BETFAIR (For Tennis Forensics)
    print(">> Fetching Betfair (Targeting Tennis & Soccer)...")
    bf = BetfairClient()
    try:
        if await bf.login():
            # target_ids = ['1', '2'] # Soccer, Tennis
            # Logic from MegaAudit logic for consistency
            target_ids = ['1', '2']
            if "betfair.es" in bf.base_url: target_ids = ['1', '2']
            
            bf_events = []
            for tid in target_ids:
                payload = {
                    "filter": {
                        "eventTypeIds": [tid],
                        "marketStartTime": {"from": datetime.utcnow().isoformat() + "Z"}
                    },
                    "maxResults": 200,
                    "marketProjection": ["EVENT", "MARKET_START_TIME", "COMPETITION"]
                }
                # Tennis Fix
                if tid == '2':
                    if "marketTypeCodes" in payload["filter"]: del payload["filter"]["marketTypeCodes"]
                
                res = await bf._api_request('listMarketCatalogue', payload)
                if res:
                    for m in res:
                        # Standardize for consistency
                        ev = m.get('event', {})
                        bf_events.append({
                            'id': ev.get('id'),
                            'name': ev.get('name'),
                            'market_id': m.get('marketId'),
                            'open_date': m.get('marketStartTime'),
                            'market_type': m.get('description', {}).get('marketType', 'MATCH_ODDS'),
                            'exchange': 'bf',
                            '_sport': 'tennis' if tid=='2' else 'soccer'
                        })
            
            with open('dump_bf.json', 'w', encoding='utf-8') as f:
                json.dump(bf_events, f, indent=2, cls=DateTimeEncoder)
            print(f"✅ Saved {len(bf_events)} Betfair events to dump_bf.json")
        else:
            print("❌ Betfair Login Failed")
    except Exception as e:
        print(f"❌ Error fetching Betfair: {e}")
    finally:
        await bf.logout()

if __name__ == "__main__":
    asyncio.run(dump_data())
