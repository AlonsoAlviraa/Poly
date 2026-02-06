"""
The Teacher (Offline Resolver)
Process unmatched candidates from 'unmatched_queue.json' and inject them into memory.
"""
import json
import os
import sys
import logging
from typing import List, Dict

# Adjust path to import src modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.arbitrage.entity_resolver_logic import get_resolver

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TheTeacher")

QUEUE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'learning', 'unmatched_queue.json')

def run_resolver():
    if not os.path.exists(QUEUE_PATH):
        logger.info("No unmatched queue found.")
        return

    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        try:
            queue = json.load(f)
        except json.JSONDecodeError:
            queue = []

    if not queue:
        logger.info("Queue is empty.")
        return

    logger.info(f"Loaded {len(queue)} orphans from queue.")
    resolver = get_resolver()
    
    remaining_queue = []
    
    counts = {"auto": 0, "manual": 0, "skipped": 0}

    for item in queue:
        poly_name = item['poly_name']
        bf_name = item['bf_candidate']
        score = item['score']
        sport = item['sport']
        
        # STRATEGY A: Auto-Accept High Confidence Near-Misses
        # Threshold: 75% (0.75)
        if score >= 0.75:
            logger.info(f"[AUTO] Learning: '{poly_name}' == '{bf_name}' (Score: {score:.2f})")
            resolver.add_mapping(poly_name, bf_name, sport, auto_save=False)
            counts["auto"] += 1
            continue

        # STRATEGY B: Manual / LLM Assist
        if score >= 0.60:
             logger.info(f"[MEDIUM CL] Consider adding manually: '{poly_name}' vs '{bf_name}' (Score: {score:.2f})")
        else:
             # Weak matches, just log them for "Deep Mining" later
             logger.debug(f"[WEAK CL] '{poly_name}' vs '{bf_name}' (Score: {score:.2f})")

        remaining_queue.append(item)
        counts["skipped"] += 1

    # Save changes
    if counts["auto"] > 0:
        resolver.save_mappings()
        logger.info(f"Saved {counts['auto']} new mappings to memory.")

    # Rewrite queue
    with open(QUEUE_PATH, 'w', encoding='utf-8') as f:
        json.dump(remaining_queue, f, indent=2)
    
    logger.info(f"Done. Auto-resolved: {counts['auto']}, Pending: {counts['skipped']}")

if __name__ == "__main__":
    run_resolver()
