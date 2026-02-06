
import asyncio
import logging
from datetime import datetime, timezone
from src.data.gamma_client import GammaAPIClient
from src.data.betfair_client import BetfairClient
from src.arbitrage.cross_platform_mapper import CrossPlatformMapper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_nba():
    poly = GammaAPIClient()
    bf = BetfairClient()
    mapper = CrossPlatformMapper()
    
    print("\n" + "="*50)
    print("NBA DISCOVERY DEBUGGER")
    print("="*50)
    
    # 1. Fetch Poly NBA
    print("\n>> Fetching Polymarket NBA markets...")
    poly_markets = await poly.get_all_match_markets()
    nba_poly = [m for m in poly_markets if "nba" in m.get('question', '').lower() or "nba" in m.get('slug', '').lower() or "10345" in str(m.get('tag_id', ''))]
    print(f"   Found {len(nba_poly)} NBA-related markets on Polymarket.")
    for m in nba_poly[:5]:
        print(f"   - {m['question']} (ID: {m['id']})")
        
    # 2. Fetch Betfair NBA (7522) - EXHAUSTIVE
    print("\n>> Fetching Betfair Basketball markets (ID: 7522) - EXHAUSTIVE...")
    payload = {
        "filter": {
            "eventTypeIds": ["7522"],
            "marketStartTime": {
                "from": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }
        },
        "maxResults": 1000,
        "marketProjection": ["EVENT", "MARKET_START_TIME", "MARKET_DESCRIPTION", "RUNNER_DESCRIPTION"]
    }
    
    bf_markets = await bf._api_request('listMarketCatalogue', payload)
    
    print(f"   Found {len(bf_markets) if bf_markets else 0} Basketball markets on Betfair.")
    
    if bf_markets:
        # Group by market type and competition
        types = {}
        competitions = {}
        for m in bf_markets:
            mt = m.get('description', {}).get('marketType', 'UNKNOWN')
            comp = m.get('competition', {}).get('name', 'NO_COMP')
            types[mt] = types.get(mt, 0) + 1
            competitions[comp] = competitions.get(comp, 0) + 1
        
        print("\n   Betfair Market Types Found:")
        for mt, count in sorted(types.items(), key=lambda x: x[1], reverse=True):
            print(f"      - {mt}: {count}")
            
        print("\n   Betfair Competitions Found:")
        for comp, count in sorted(competitions.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"      - {comp}: {count}")

        print("\n   Sample Betfair Markets:")
        for m in bf_markets[:10]:
            print(f"      - {m.get('event', {}).get('name')} | {m.get('description', {}).get('marketType')}")
            
    # 3. Try Mapping with detailed fail reasons
    print("\n>> Detailed Mapping Trace (Poly vs BF):")
    if nba_poly and bf_markets:
        # Standardize BF for mapper
        standardized_bf = []
        for m in bf_markets:
            standardized_bf.append({
                'id': m['event']['id'],
                'event_id': m['event']['id'],
                'market_id': m['marketId'],
                'name': m['event']['name'],
                'open_date': m['marketStartTime'],
                'market_type': m.get('description', {}).get('marketType', 'MATCH_ODDS'),
                'runners': m.get('runners', []),
                '_start_date_parsed': datetime.fromisoformat(m['marketStartTime'].replace('Z', '+00:00'))
            })

        for pm in nba_poly[:10]:
            # Add parsed date to pm
            start_str = pm.get('gameStartTime') or pm.get('startDate')
            if start_str:
                pm['_event_date_parsed'] = datetime.fromisoformat(str(start_str).replace('Z', '+00:00'))
            
            match = await mapper.map_market(pm, standardized_bf, "basketball")
            if match:
                print(f"   [MATCH!] {pm['question']}  ==>  {match.betfair_event_name} (Conf: {match.confidence:.2%})")
            else:
                print(f"   [FAILED] {pm['question']}")

if __name__ == "__main__":
    asyncio.run(debug_nba())
