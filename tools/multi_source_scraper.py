#!/usr/bin/env python3
"""
Aggressive multi-source scraper orchestrator with confidence reconciliation and dedupe.
"""

import argparse
import asyncio
from typing import Dict, List

from src.data.gamma_client import GammaAPIClient


def _dedupe_markets(markets: List[Dict]) -> List[Dict]:
    seen = {}
    for m in markets:
        key = (m.get("slug") or m.get("question") or "").lower()
        if not key:
            continue
        existing = seen.get(key)
        if not existing or m.get("_confidence", 0) > existing.get("_confidence", 0):
            seen[key] = m
    return list(seen.values())


async def _scrape_gamma(limit: int) -> List[Dict]:
    client = GammaAPIClient()
    try:
        markets = await client.get_all_match_markets(limit=limit)
        for m in markets:
            m["_source"] = "gamma"
            m["_confidence"] = 0.9
        return markets
    finally:
        await client.close()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-source scraper with dedupe.")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    markets = []
    markets.extend(await _scrape_gamma(args.limit))
    deduped = _dedupe_markets(markets)

    print(f"Fetched {len(markets)} raw markets. Dedupe -> {len(deduped)}.")


if __name__ == "__main__":
    asyncio.run(main())
