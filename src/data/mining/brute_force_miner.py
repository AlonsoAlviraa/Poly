"""
Nuclear Diagnosis: Brute Force Matcher
Finds the absolute best match for unmatched events in specific sports, ignoring all thresholds.
"""
import json
import os
import re
from thefuzz import fuzz
from datetime import datetime

DUMP_POLY = 'dump_poly.json'
DUMP_SX = 'dump_sx.json'
# We will use SX dump as proxy for Exchange candidates. 
# If a BF dump exists, we'd load it too.

def normalize(text):
    return text.lower().strip()

def run_diagnosis():
    print(">> STARTING NUCLEAR DIAGNOSIS...")
    
    # Load Poly
    if not os.path.exists(DUMP_POLY):
        print("!! No dump_poly.json found. Run mega-audit first.")
        return
    with open(DUMP_POLY, 'r', encoding='utf-8') as f: 
        poly_data = json.load(f)

    # Load SX
    if not os.path.exists(DUMP_SX):
        print("!! No dump_sx.json found.")
        sx_data = []
    else:
        with open(DUMP_SX, 'r', encoding='utf-8') as f: 
            sx_data = json.load(f)

    print(f"Loaded {len(poly_data)} Poly events and {len(sx_data)} SX events.")

    # Filter target sports
    target_sports = ['tennis', 'basketball']
    
    unmatched_poly = [p for p in poly_data if p.get('category', '').lower() in target_sports]
    exchange_candidates = sx_data # In a real scenario, we'd want BF too if captured.

    print(f"Analyzing {len(unmatched_poly)} Poly events in {target_sports}...")
    
    for p in unmatched_poly:
        q = p['question']
        poly_team = q # Simplification. 
        # Ideally extract "Team A" from "Will Team A win...?"
        
        best_candidate = None
        best_score = 0
        best_name = ""
        
        # O(N*M) Scan
        for sx in exchange_candidates:
            sx_name = sx.get('name', '')
            
            # 1. Token Set Ratio (Good for partials)
            score = fuzz.token_set_ratio(q, sx_name)
            
            if score > best_score:
                best_score = score
                best_candidate = sx
                best_name = sx_name
        
        print("-" * 60)
        print(f"POLY: {q}")
        print(f"BEST MATCH (Score {best_score}): {best_name}")
        
        if best_score > 60:
            print(">> [OPPORTUNITY] This looks valid. Why wasn't it matched?")
        else:
            print(">> [MISSING] Likely not in exchange inventory.")

if __name__ == "__main__":
    run_diagnosis()
