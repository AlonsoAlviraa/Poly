
import asyncio
import json
from src.arbitrage.cross_platform_mapper import CrossPlatformMapper
from src.utils.sx_normalizer import SXNormalizer

async def run():
    print(">> Verifying SX Match Fix...")
    
    # Load Data
    with open('dump_poly.json', 'r', encoding='utf-8') as f:
        poly_data = json.load(f)
    with open('dump_sx.json', 'r', encoding='utf-8') as f:
        sx_data = json.load(f)
        
    # Find Candidates
    poly_market = next((p for p in poly_data if 'Jaxon' in p['question']), None)
    sx_event = next((s for s in sx_data if 'Jaxon' in s.get('name', '')), None)
    
    if not poly_market or not sx_event:
        print("!! Could not find candidates in dump.")
        return

    print(f"POLY: {poly_market['question']}")
    print(f"SX:   {sx_event['name']} | Type: '{sx_event.get('market_type')}'")
    
    # Initialize Mapper
    mapper = CrossPlatformMapper()
    
    # 1. Test Semantic Check directly
    is_compat = mapper._is_semantically_compatible(
        poly_market['question'], 
        sx_event
    )
    print(f"Semantic Check (SX Bypass): {is_compat}")
    
    # 2. Test Full Map (mimicking mega_audit)
    # We pass it as a list to avoid date blocking for this specific test, 
    # or we construct bucket. Let's pass as list and rely on fallback loop?
    # But _apply_date_blocker requires bucket if we want to be safe?
    # No, if buckets=None, it loops all.
    
    mapping = await mapper.map_market(
        poly_market=poly_market,
        betfair_events=[sx_event],
        sport_category='soccer', # Force match sport
        polymarket_slug='nfl',
        bf_buckets=None
    )
    
    if mapping:
        print(f"✅ MATCH SUCCESS! Confidence: {mapping.confidence}")
        print(f"   Exchange: {mapping.exchange}")
        print(f"   Selection: {mapping.bf_runner_name}")
    else:
        print("❌ MATCH FAILED in map_market")

if __name__ == "__main__":
    asyncio.run(run())
