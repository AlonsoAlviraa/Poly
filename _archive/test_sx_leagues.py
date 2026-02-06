#!/usr/bin/env python3
"""Get SX Bet markets by league (for Politics, Crypto, etc.)."""

import asyncio
import aiohttp

async def get_markets_by_league():
    """Fetch markets by iterating through leagues."""
    
    async with aiohttp.ClientSession() as session:
        # 1. Get all active leagues
        r = await session.get("https://api.sx.bet/leagues/active")
        data = await r.json()
        leagues = data.get("data", [])
        
        # Filter for interesting categories
        interesting_sports = {17: 'Politics', 14: 'Crypto', 16: 'Economics', 18: 'Entertainment', 10: 'Novelty'}
        
        print("=" * 60)
        print("ACTIVE LEAGUES FOR POLITICS/CRYPTO/ENTERTAINMENT")
        print("=" * 60)
        
        for league in leagues:
            sport_id = league.get('sportId')
            if sport_id in interesting_sports:
                league_id = league.get('leagueId')
                label = league.get('label')
                print(f"\n📋 {label} (League ID: {league_id}, Sport: {interesting_sports[sport_id]})")
                
                # Try to get markets for this league
                try:
                    r = await session.get(f"https://api.sx.bet/markets/active?leagueId={league_id}")
                    data = await r.json()
                    markets = data.get("data", {}).get("markets", [])
                    
                    # Filter to only this league
                    league_markets = [m for m in markets if m.get('leagueId') == league_id]
                    
                    print(f"   Markets: {len(league_markets)}")
                    
                    for m in league_markets[:3]:
                        o1 = m.get('outcomeOneName', '')
                        o2 = m.get('outcomeTwoName', '')
                        print(f"   - {o1} vs {o2}")
                        
                except Exception as e:
                    print(f"   Error: {e}")
        
        print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(get_markets_by_league())
