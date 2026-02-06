import asyncio
import logging
import json
import aiohttp
from datetime import datetime, timezone
from rapidfuzz import fuzz

# Add src to path
import sys
import os
sys.path.append(os.getcwd())

from src.data.gamma_client import GammaAPIClient
from src.data.sx_bet_client import SXBetClient

# Setup simple logging
logging.basicConfig(level=logging.INFO)

async def run_diagnosis():
    print(">> FETCHING DATA FOR DIAGNOSIS...")
    
    # 1. Fetch Poly
    gamma = GammaAPIClient()
    print("   Fetching Polymarket...")
    poly_markets = await gamma.get_all_match_markets(limit=200) 
    print(f"   Fetched {len(poly_markets)} Polymarket questions.")

    # 2. Fetch SX RAW (to debug dates) and Client Objects
    sx = SXBetClient()
    print("   Fetching SX Bet...")
    
    # Fetch raw first to see JSON structure
    session = await sx._get_session()
    raw_markets = []
    try:
        async with session.get(f"{sx.BASE_URL}/markets/active", timeout=15) as response:
            data = await response.json()
            raw_markets = data.get("data", {}).get("markets", [])
            print(f"   [RAW DEBUG] Fetched {len(raw_markets)} raw markets.")
            if raw_markets:
                print("   [RAW DEBUG] Sample Market 0 Keys:", raw_markets[0].keys())
                print("   [RAW DEBUG] Sample Market 0 gameTime:", raw_markets[0].get('gameTime'))
                print("   [RAW DEBUG] Sample Market 0 item:", json.dumps(raw_markets[0], indent=2)[:500])
    except Exception as e:
        print(f"   [RAW DEBUG] Error fetching raw: {e}")

    sx_markets = await sx.get_active_markets()
    print(f"   Fetched {len(sx_markets)} parsed SX Bet markets.")

    # Debug Date Parsing in Objects
    print("\n   [DEBUG] SX Date Parsing Sample (Parsed Objects):")
    for i, m in enumerate(sx_markets[:5]):
        print(f"     Label: {m.label} | GameTime: {m.game_time} | Status: {m.status}")

    print("\n>> RUNNING STRING WAR (Top Matches > 50)...")
    print("-" * 120)
    print(f"{'SCORE':<5} | {'POLYMARKET QUESTION':<50} | {'SX BET LABEL':<40} | {'MATCH TYPE'}")
    print("-" * 120)

    matches_found = 0
    
    # Optimization: Pre-clean poly questions
    poly_data = []
    for pm in poly_markets:
        q = pm.get('question', '')
        poly_data.append(q)

    # Manual Loop
    for sx_mkt in sx_markets:
        sx_name = sx_mkt.label
        t1 = sx_mkt.team_one_name
        t2 = sx_mkt.team_two_name
        
        # Construct SX Variants
        variants = [sx_name]
        if t1: variants.append(t1)
        if t2: variants.append(t2)
        
        for q in poly_data:
            # Check against all variants
            best_score = 0
            best_variant = ""
            
            for v in variants:
                # Token Set Ratio is the standard flexible matcher
                score = fuzz.token_set_ratio(q.lower(), v.lower())
                if score > best_score:
                    best_score = score
                    best_variant = v
            
            if best_score > 60: # Threshold to see "near misses"
                print(f"{best_score:<5} | {q[:50]:<50} | {sx_name[:40]:<40} | Matches: '{best_variant}'")
                matches_found += 1
                
        if matches_found > 100:
            print("... limit reached ...")
            break

    print("-" * 120)
    print(f"Total potential matches checked. Found {matches_found} pairs > 60 score.")

    await gamma.close() if hasattr(gamma, 'close') else None
    await sx.close()

if __name__ == "__main__":
    asyncio.run(run_diagnosis())
