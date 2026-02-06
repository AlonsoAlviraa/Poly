
import asyncio
import logging
from datetime import datetime, timezone
from src.data.gamma_client import GammaAPIClient
from src.data.sx_bet_client import SXBetClient
from src.arbitrage.cross_platform_mapper import CrossPlatformMapper

async def debug_sx():
    poly = GammaAPIClient()
    sx = SXBetClient()
    mapper = CrossPlatformMapper()
    
    print("\n" + "="*50)
    print("SX BET DISCOVERY DEBUGGER")
    print("="*50)
    
    # 1. Fetch Poly
    print("\n>> Fetching Polymarket (Broad)...")
    poly_markets = await poly.get_all_match_markets()
    
    basket_keywords = ['basketball', 'nba', ' ncaa', 'basket', 'lakers', 'warriors', 'knicks', 'suns', 'euroleague', '76ers', 'celtics', 'wnba', 'bulls', 'cavaliers', 'rockets', 'hornets', 'clippers', 'nuggets', 'pacers', 'grizzlies', 'timberwolves', 'pelicans', 'magic', 'raptors', 'jazz']
    
    nba_poly = [m for m in poly_markets if any(k in f"{m.get('question','') } {m.get('slug','')}".lower() for k in basket_keywords)]
    print(f"   Found {len(nba_poly)} NBA-related markets on Polymarket.")
    
    # 2. Fetch SX Metadata
    print("\n>> Fetching SX Bet Metadata...")
    session = await sx._get_session()
    async with session.get(f"{sx.BASE_URL}/sports") as response:
        sports_data = await response.json()
        print(f"   Sports: {sports_data.get('data', {}).get('sports', [])}")
        
    async with session.get(f"{sx.BASE_URL}/leagues") as response:
        leagues_data = await response.json()
        all_leagues = leagues_data.get('data', {}).get('leagues', [])
        basket_leagues = [l for l in all_leagues if "basketball" in str(l).lower() or "nba" in str(l).lower()]
        print(f"   NBA/Basketball Leagues: {basket_leagues}")
    
    # Check what is "active" specifically for basketball
    # Using the sportId for Basketball (usually 2 or something)
    # SX Bet uses sportId in some endpoints.
    
    sx_events = await sx.get_markets_standardized()
    
    # 3. Trace Mapping for a few NBA markets
    if not nba_poly or not sx_events:
        print("!! Missing data for trace.")
        return

    print("\n>> TRACING NBA MATCHING (POLY -> SX):")
    for pm in nba_poly[:10]:
        print(f"\n[POLY] {pm['question']}")
        
        # Manually apply date blocker logic for debugging
        poly_start = pm.get('gameStartTime') or pm.get('startDate')
        p_dt = datetime.fromisoformat(str(poly_start).replace('Z', '+00:00')) if poly_start else None
        print(f"   - Poly Time: {p_dt}")
        
        candidates = []
        for ev in sx_events:
            ev_start = ev.get('open_date')
            e_dt = datetime.fromisoformat(ev_start.replace('Z', '+00:00')) if ev_start else None
            
            # Check Date Blocker
            from src.arbitrage.entity_resolver_logic import date_blocker
            if p_dt and e_dt and date_blocker(p_dt, e_dt):
                candidates.append(ev)
            elif p_dt and e_dt:
                # Debug why rejected
                diff = abs((p_dt - e_dt).total_seconds()) / 3600
                if diff < 48: # Only show "Close but no cigar"
                    pass # print(f"     [DATE REJECT] {ev['name']} (Diff: {diff:.1f}h)")
        
        print(f"   - Date-Valid SX Candidates: {len(candidates)}")
        for c in candidates:
            # print(f"     - {c['name']}")
            pass
            
        m = await mapper.map_market(pm, sx_events, sport_category="basketball")
        if m:
            print(f"   [RESULT] MATCH! ==> {m.betfair_event_name} (Conf: {m.confidence:.2%})")
        else:
            print(f"   [RESULT] FAILED")

if __name__ == "__main__":
    asyncio.run(debug_sx())
