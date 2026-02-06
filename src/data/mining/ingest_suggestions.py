"""
Suggestion Ingestor
Reads graph_suggestions.json, filters them, and injects them into the EntityResolver memory
so they are treated as 'Solved cases' in future runs.
"""
import json
import os
import sys

# Add src to path
sys.path.append(os.getcwd())

from src.arbitrage.entity_resolver_logic import get_resolver

def ingest():
    path = "data/learning/graph_suggestions.json"
    if not os.path.exists(path):
        print("No suggestions file found.")
        return

    with open(path, 'r') as f:
        suggestions = json.load(f)
    
    resolver = get_resolver()
    count = 0
    
    print(f">> Ingesting {len(suggestions)} suggestions...")
    
    for s in suggestions:
        # 1. Validation Filter
        score = s.get('score', 0)
        p_q = s.get('poly_question')
        e_n = s.get('exch_name')
        
        # Risk Management for "Illinois" vs "Illinois State"
        # If one has "State" and the other doesn't, DROP IT.
        p_tokens = set(p_q.lower().split())
        e_tokens = set(e_n.lower().split())
        
        if 'state' in p_tokens and 'state' not in e_tokens: continue
        if 'state' in e_tokens and 'state' not in p_tokens: continue
        
        # Score Threshold (Aggressive ingestion for Tennis/Basket)
        if score > 65:
            # We map Canonical (Poly Question) -> Alias (Exch Name)
            # This allows static_matcher to find it next time.
            resolver.add_mapping(canonical=p_q, alias=e_n, sport_category='unknown') 
            count += 1
            
    resolver.save_mappings()
    print(f">> Successfully ingested {count} new mappings into memory.")

if __name__ == "__main__":
    ingest()
