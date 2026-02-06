
import json
import os
import logging
from typing import Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def partition_mappings(input_path: str):
    """
    Reorganizes mappings.json into a sport-partitioned structure.
    """
    if not os.path.exists(input_path):
        logger.error(f"Input file not found: {input_path}")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # If data is already partitioned (at least has soccer/basketball/etc), 
    # we just ensure the structure is clean.
    # The user provided an example where mappings.json already has some structure.
    
    partitioned = {}
    
    # We want to ensure entries are in their correct 'sport' shard.
    # If the current structure is: { "sport": { "Canonical": [Aliases] } }
    # We keep it but we might want to move things from "learned" or "events" 
    # into specific sport shards if we can identify them.

    for category, entities in data.items():
        if category in ["learned", "events"]:
            # Potentially distribute these if we wanted to be fancy, 
            # but for now, we keep them as categories but ensure 
            # the resolver treats them as shards.
            partitioned[category] = entities
            continue
            
        if isinstance(entities, dict):
            partitioned[category] = entities
        else:
            logger.warning(f"Unexpected structure in category '{category}': {type(entities)}")

    # Specific requested shards
    shards = ["soccer", "basketball", "tennis", "ice_hockey", "american_football", "esports"]
    for shard in shards:
        if shard not in partitioned:
            partitioned[shard] = {}

    # Write back
    with open(input_path, 'w', encoding='utf-8') as f:
        json.dump(partitioned, f, indent=4, ensure_ascii=False)
    
    logger.info(f"Successfully partitioned {input_path}")

if __name__ == "__main__":
    mappings_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'mappings.json')
    partition_mappings(mappings_file)
