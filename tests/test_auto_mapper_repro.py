import asyncio
import os
from dotenv import load_dotenv
load_dotenv() # Load .env for API_LLM

from src.arbitrage.entity_resolver_logic import get_resolver
from src.arbitrage.ai_mapper import get_ai_mapper

async def test_auto_mapper():
    resolver = get_resolver()
    ai_mapper = get_ai_mapper()
    
    print("--- Testing NBA Normalization ---")
    query = "Lakers"
    entity = "Los Angeles Lakers"
    # sport_normalize should turn "Los Angeles Lakers" into "Lakers"
    res = resolver.static_matcher(query, entity, "basketball")
    print(f"Match result for '{query}' vs '{entity}': {res}")
    if res == "MATCH":
        print("✅ SUCCESS: NBA City removal worked.")
    else:
        print("❌ FAILURE: NBA City removal failed.")

    print("\n--- Testing Tennis Normalization ---")
    query = "Alcaraz"
    entity = "C. Alcaraz"
    # sport_normalize should turn "C. Alcaraz" into "alcaraz"
    res = resolver.static_matcher(query, entity, "tennis")
    print(f"Match result for '{query}' vs '{entity}': {res}")
    if res == "MATCH":
        print("✅ SUCCESS: Tennis initial removal worked.")
    else:
        print("❌ FAILURE: Tennis initial removal failed.")

    print("\n--- Testing AI Mapper Fallback (Simulated) ---")
    if not ai_mapper.api_key:
        print("⚠️ Skipping AI test: No API_LLM key found in .env")
    else:
        # Complex one: "Magpies" vs "Newcastle" (Soccer)
        # Or "Red Devils" vs "Manchester United"
        q = "Red Devils"
        e = "Manchester United"
        print(f"Checking AI similarity for '{q}' vs '{e}'...")
        is_match, confidence = await ai_mapper.check_similarity(q, e, "soccer")
        print(f"AI Result: {is_match} (Conf: {confidence})")
        
        if is_match and confidence > 0.9:
            print(f"✅ SUCCESS: AI correctly identified '{q}' as '{e}'.")
            # Test persistence
            resolver.add_mapping(canonical=e, alias=q, sport_category="soccer")
            # Check if it now matches statically
            res_static = resolver.static_matcher(q, e, "soccer")
            print(f"Static match after learning: {res_static}")
            if res_static == "MATCH":
                print("✅ SUCCESS: Persistence logic worked.")
        else:
            print("❌ FAILURE: AI could not identify the pair or confidence too low.")

if __name__ == "__main__":
    asyncio.run(test_auto_mapper())
