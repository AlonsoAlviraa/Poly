
import json
import logging
from datetime import datetime, timedelta
from rapidfuzz import fuzz
import regex as re
import time

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.sx_normalizer import SXNormalizer

# --- COPIED LOGIC FROM CROSS_PLATFORM_MAPPER (For Isolation) ---

def parse_versus_format(text: str):
    """Split 'Team A vs Team B'. DEPRECATED: Use SXNormalizer."""
    # We keep it for verification report logic if needed, or replace it.
    t = text.lower()
    if " vs " in t: return [s.strip() for s in t.split(" vs ")]
    if " @ " in t: return [s.strip() for s in t.split(" @ ")]
    if " - " in t: return [s.strip() for s in t.split(" - ")]
    return [t]

def get_sig_tokens(text):
    """Get significant tokens."""
    stop = {'the', 'win', 'will', 'match', 'odds', 'ends', 'draw', 'both', 'teams', 'score', 'end', 'fc', 'cf', 'bc', 'st', 'st.', 'united', 'city', 'real', 'club', 'de', 'v', 'vs', 'and'}
    tokens = set(re.findall(r'\w+', text.lower()))
    return tokens - stop

def verify_team_overlap(poly_text: str, bf_text: str) -> dict:
    """
    Detailed verification returning a SCORECARD instead of boolean.
    """
    bf_sides = [s for part in parse_versus_format(bf_text) for s in re.split(r' vs\.? | v\.? | @ | - ', part) if len(s.strip()) > 2]
    p_sides = [s.strip() for s in re.split(r' vs\.? | v\.? | @ | - ', poly_text) if len(s.strip()) > 2]
    
    scorecard = {
        'poly_sides': p_sides,
        'bf_sides': bf_sides,
        'matches': [],
        'passed': False
    }

    if not p_sides or not bf_sides: 
        scorecard['error'] = "Parse Error"
        return scorecard

    matches_per_p_side = []
    
    for p_side in p_sides:
        p_tokens = get_sig_tokens(p_side)
        found_match = False
        token_overlap = set()
        
        for bf_side in bf_sides:
            bf_tokens = get_sig_tokens(bf_side)
            intersection = p_tokens & bf_tokens
            if intersection:
                # Logic check
                common_generic = {'city', 'united', 'fc', 'real'}
                if len(intersection) == 1 and list(intersection)[0] in common_generic:
                     p_clean = p_side.replace('fc', '').replace('bc', '').strip()
                     bf_clean = bf_side.replace('fc', '').replace('bc', '').strip()
                     if p_clean in bf_clean or bf_clean in p_clean:
                         found_match = True
                         token_overlap = intersection
                else:
                    found_match = True
                    token_overlap = intersection
            if found_match: break
        
        matches_per_p_side.append(found_match)
        scorecard['matches'].append({'side': p_side, 'found': found_match, 'tokens': list(token_overlap)})

    if len(p_sides) >= 2:
        scorecard['passed'] = all(matches_per_p_side)
    else:
        scorecard['passed'] = any(matches_per_p_side)
        
    return scorecard

def forensic_matcher():
    print("🕵️ FORENSIC MATCHING REPORT")
    print("==========================")
    
    # 1. LOAD DATA
    try:
        with open('dump_poly.json', 'r', encoding='utf-8') as f:
            poly_data = json.load(f)
        with open('dump_sx.json', 'r', encoding='utf-8') as f:
            sx_data = json.load(f)
        with open('dump_bf.json', 'r', encoding='utf-8') as f:
            bf_data = json.load(f)
        print(f"Loaded: Poly={len(poly_data)}, SX={len(sx_data)}, BF={len(bf_data)}")
    except FileNotFoundError:
        print("❌ Data dumps not found. Run dump_data.py first.")
        return

    # 2. SX FORENSICS
    print("\n🔬 [SX BET FORENSICS]")
    sx_fails = 0
    sx_analyzed = 0
    
    # Use ALL Poly markets to avoid filtering errors
    relevant_poly = poly_data
    
    start_time = time.time()
    
    # We want to find "Hidden Gems": Events that SHOULD match but don't.
    # Strategy: Find top 3 token overlaps for each parsed SX team.
    
    print(f"Scanning {len(sx_data)} SX events against {len(relevant_poly)} Poly markets...")
    print(f"Sample SX: {[e.get('name') for e in sx_data[:3]]}")
    print(f"Sample Poly: {[p.get('question') for p in relevant_poly[:3]]}")
    
    # Check SX Tennis Inventory
    sx_tennis_count = sum(1 for e in sx_data if 'tennis' in e.get('category','').lower() or 'tennis' in e.get('name','').lower())
    print(f"SX Tennis Events Found in Dump: {sx_tennis_count}")

    potential_matches = []
    
    for sx_ev in sx_data:
        # Use SXNormalizer to generate candidates (Original + Team A + Team B)
        candidates = SXNormalizer.expand_candidates(sx_ev)
        
        best_cand = None
        best_score = 0
        best_sx_variant = ""

        # Check each candidate (e.g. "Carabobo FC" vs Poly)
        for cand in candidates:
            sx_name = cand.get('name', '')
            sx_tokens = get_sig_tokens(sx_name)
            if not sx_tokens: continue
            
            for p in relevant_poly:
                p_q = p.get('question', '')
                p_tokens = get_sig_tokens(p_q)
                
                # Optimization: Must share at least 1 significant token
                if not (sx_tokens & p_tokens):
                    continue
                
                # Fuzzy Score
                score = fuzz.token_set_ratio(sx_name, p_q)
                
                if score > best_score:
                    best_score = score
                    best_cand = p
                    best_sx_variant = sx_name

        if best_cand and best_score > 40:
             potential_matches.append({
                    'sx_name': best_sx_variant, # Log the variant that matched (e.g. "Huachipato")
                    'poly_q': best_cand['question'],
                    'score': best_score,
                    'sx_tokens': list(get_sig_tokens(best_sx_variant)),
                    'p_tokens': list(get_sig_tokens(best_cand['question']))
             })

        if best_cand: # Log ALL bests to sort later
            if best_score > 40: # Lower threshold to see garbage matches
                potential_matches.append({
                    'sx_name': sx_name,
                    'poly_q': best_cand['question'],
                    'score': best_score,
                    'sx_tokens': list(sx_tokens),
                    'p_tokens': list(get_sig_tokens(best_cand['question']))
                })

    # Sort by score desc
    potential_matches.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"\nFound {len(potential_matches)} pairs with score > 40.")
    print("TOP 10 PAIRS (FORENSIC DEEP DIVE):")
    
    for m in potential_matches[:10]:
        print("-" * 60)
        print(f"SX:   {m['sx_name']}")
        print(f"Poly: {m['poly_q']}")
        print(f"Score: {m['score']}")
        print(f"Tokens SX: {m['sx_tokens']}")
        print(f"Tokens Poly: {m['p_tokens']}")
        
        # Run Verification
        report = verify_team_overlap(m['poly_q'], m['sx_name'])
        print(f"Verification Report: {report['passed']}")
        if not report['passed']:
             print(f"   -> FAILED SIDES: {report['matches']}")

    # 3. TENNIS FORENSICS
    print("\n🔬 [TENNIS FORENSICS]")
    poly_tennis = [p for p in poly_data if 'tennis' in p.get('category', '').lower() or 'tennis' in p.get('slug', '').lower()]
    bf_tennis = [e for e in bf_data if 'tennis' in e.get('_sport', 'soccer').lower()] # dump_bf sets _sport
    
    print(f"Poly Tennis: {len(poly_tennis)} | BF Tennis: {len(bf_tennis)}")

    # Check for simple name matches
    matches = 0
    for pt in poly_tennis:
        pq = pt['question']
        pt_tokens = get_sig_tokens(pq)
        
        for bt in bf_tennis:
            bn = bt['name']
            bt_tokens = get_sig_tokens(bn)
            
            # Simple overlap
            if len(pt_tokens & bt_tokens) >= 2: 
                 score = fuzz.token_set_ratio(pq, bn)
                 print(f"Match? '{pq}' vs '{bn}' | Score: {score}")
                 if score >= 85: # Default threshold
                     print(f"   -> WOULD MATCH (High Confidence)")
                     # CHECK DATES
                     try:
                         p_date = pt.get('startDate') or pt.get('gameStartTime')
                         b_date = bt.get('open_date')
                         if p_date and b_date:
                             pd = datetime.fromisoformat(p_date.replace('Z', '+00:00'))
                             bd = datetime.fromisoformat(b_date.replace('Z', '+00:00'))
                             diff_hours = abs((pd - bd).total_seconds()) / 3600
                             print(f"   -> Date Diff: {diff_hours:.2f} hours (Poly: {pd} | BF: {bd})")
                             if diff_hours > 24:
                                 print("   -> 🛑 BLOCKED BY DATE BLOCKER (>24h)")
                             else:
                                 print("   -> ✅ DATES OK")
                     except Exception as e:
                         print(f"   -> Date Check Fail: {e}")

                 elif score > 60:
                     print(f"   -> BLOCKED BY THRESHOLD (<85)")
                 matches += 1

if __name__ == "__main__":
    forensic_matcher()
