#!/usr/bin/env python3
"""
Wikidata alias enrichment for soccer team names.

Fetches club labels + aliases and writes them into mapping_cache/entities.json
under the "soccer" sport shard. This is optional and intended to be run manually.
"""

import argparse
import json
import logging
import os
from typing import Dict, List

import httpx

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

logger = logging.getLogger("wikidata_alias_enrichment")


def _run_query(limit: int) -> Dict:
    query = f"""
    SELECT ?club ?clubLabel ?altLabel WHERE {{
      ?club wdt:P31/wdt:P279* wd:Q476028 .
      OPTIONAL {{ ?club skos:altLabel ?altLabel . FILTER (lang(?altLabel) IN ("en", "es")) }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,es" . }}
    }}
    LIMIT {limit}
    """
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "APU-Alias-Enrichment/1.0 (contact: local)",
    }
    with httpx.Client(timeout=30) as client:
        response = client.get(WIKIDATA_SPARQL, params={"query": query}, headers=headers)
        response.raise_for_status()
        return response.json()


def _load_entities(path: str) -> Dict[str, Dict[str, str]]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _persist_entities(path: str, entities: Dict[str, Dict[str, str]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(entities, f, indent=4, ensure_ascii=False)
    os.replace(tmp_path, path)


def enrich_soccer_entities(entity_path: str, limit: int) -> int:
    data = _run_query(limit)
    bindings: List[Dict] = data.get("results", {}).get("bindings", [])
    entities = _load_entities(entity_path)
    soccer_map = entities.setdefault("soccer", {})

    added = 0
    for row in bindings:
        label = row.get("clubLabel", {}).get("value")
        alt = row.get("altLabel", {}).get("value")
        if not label or not alt:
            continue
        key = alt.lower().strip()
        if key and key not in soccer_map:
            soccer_map[key] = label
            added += 1

    _persist_entities(entity_path, entities)
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich soccer aliases from Wikidata.")
    parser.add_argument("--entity-path", default="mapping_cache/entities.json")
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()

    try:
        added = enrich_soccer_entities(args.entity_path, args.limit)
        print(f"Added {added} aliases to {args.entity_path}")
    except Exception as exc:
        logger.error("Wikidata enrichment failed: %s", exc)
        raise SystemExit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
