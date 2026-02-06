#!/usr/bin/env python3
"""
Complete SX Bet API exploration.
Find Politics, Crypto, and other non-sports markets.
"""

import asyncio
import aiohttp
import json

BASE_URL = "https://api.sx.bet"

async def explore_sx_api():
    print("=" * 70)
    print("SX BET API EXPLORATION")
    print("=" * 70)
    
    async with aiohttp.ClientSession() as session:
        
        # 1. List all sports/categories
        print("\n[1] Available Sports/Categories:")
        async with session.get(f"{BASE_URL}/sports") as r:
            data = await r.json()
            sports = data.get("data", [])
            for s in sports:
                print(f"    {s.get('sportId'):3d}: {s.get('label')}")
        
        # 2. Check each category for active markets
        print("\n[2] Active Markets by Category:")
        
        interesting_sports = [
            (17, 'Politics'),
            (14, 'Crypto'),
            (16, 'Economics'),
            (10, 'Novelty Markets'),
            (18, 'Entertainment'),
            (5, 'Soccer'),
            (1, 'Basketball'),
            (8, 'Football'),  # NFL
        ]
        
        for sport_id, name in interesting_sports:
            # Try with pageSize parameter
            url = f"{BASE_URL}/markets/active?sportId={sport_id}&pageSize=100"
            async with session.get(url) as r:
                data = await r.json()
                markets = data.get("data", {}).get("markets", [])
                
                # Filter by actual sportId in response
                filtered = [m for m in markets if m.get('sportId') == sport_id]
                
                print(f"\n    {name} (ID={sport_id}): {len(filtered)} markets")
                
                if filtered and sport_id in [17, 14, 16, 10]:  # Non-sports
                    for m in filtered[:5]:
                        o1 = m.get('outcomeOneName', 'Yes')
                        o2 = m.get('outcomeTwoName', 'No')
                        t1 = m.get('teamOneName', '')
                        t2 = m.get('teamTwoName', '')
                        label = f"{t1} vs {t2}" if t1 and t2 else f"{o1}/{o2}"
                        print(f"        - {label[:60]}")
        
        # 3. Try /markets/popular endpoint
        print("\n[3] Popular Markets:")
        try:
            async with session.get(f"{BASE_URL}/markets/popular") as r:
                data = await r.json()
                markets = data.get("data", {}).get("markets", [])
                
                print(f"    Found {len(markets)} popular markets")
                
                # Group by sport
                by_sport = {}
                for m in markets:
                    sport = m.get('sportLabel', 'Unknown')
                    by_sport[sport] = by_sport.get(sport, 0) + 1
                
                print("    By category:")
                for sport, count in sorted(by_sport.items(), key=lambda x: x[1], reverse=True):
                    print(f"      {sport}: {count}")
                    
        except Exception as e:
            print(f"    Error: {e}")
        
        # 4. Try leagues endpoint
        print("\n[4] Leagues with active markets:")
        try:
            async with session.get(f"{BASE_URL}/leagues/active") as r:
                data = await r.json()
                leagues = data.get("data", [])
                
                print(f"    Found {len(leagues)} active leagues")
                
                # Show non-sports leagues
                for league in leagues:
                    sport_id = league.get('sportId')
                    if sport_id in [17, 14, 16, 10, 18]:  # Non-sports
                        print(f"    {league.get('label')} (sportId={sport_id})")
                        
        except Exception as e:
            print(f"    Error: {e}")
        
        # 5. Raw check of all active markets
        print("\n[5] All Active Markets Analysis:")
        async with session.get(f"{BASE_URL}/markets/active") as r:
            data = await r.json()
            markets = data.get("data", {}).get("markets", [])
            
            print(f"    Total markets returned: {len(markets)}")
            
            # Unique sport IDs in response
            sport_ids = set(m.get('sportId') for m in markets)
            print(f"    Sport IDs in response: {sport_ids}")
            
            # Sport labels
            sport_labels = set(m.get('sportLabel') for m in markets)
            print(f"    Sport labels in response: {sport_labels}")
    
    print("\n" + "=" * 70)
    print("CONCLUSION:")
    print("  If Politics/Crypto markets show 0, SX Bet may not have active")
    print("  markets in those categories RIGHT NOW. Markets are event-driven.")
    print("  Check back during election periods or crypto volatility events.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(explore_sx_api())
