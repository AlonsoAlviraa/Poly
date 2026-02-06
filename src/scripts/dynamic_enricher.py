
import os
import re
import json
import logging
import asyncio
import httpx
from dotenv import load_dotenv
load_dotenv() # Load API_LLM
from typing import List, Dict, Optional, Set
from datetime import datetime

# Import project logic
from src.arbitrage.entity_resolver_logic import get_resolver
from src.arbitrage.ai_mapper import get_ai_mapper
from src.utils.http_client import get_httpx_client
from src.data.betfair_client import BetfairClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DynamicEnricher")

class DynamicEnricher:
    def __init__(self):
        self.resolver = get_resolver()
        self.ai_mapper = get_ai_mapper()
        self.polymarket_url = "https://gamma-api.polymarket.com/events"
        self.sports_db_teams_url = "https://www.thesportsdb.com/api/v1/json/3/searchteams.php"
        self.sports_db_players_url = "https://www.thesportsdb.com/api/v1/json/3/searchplayers.php"
        self.semaphore = asyncio.Semaphore(5) # Limit concurrency to 5 simultaneous API calls
        self.betfair = BetfairClient()
        self.betfair_sport_ids = {
            "soccer": "1",
            "tennis": "2",
            "basketball": "7522",
            "baseball": "7511",
            "american_football": "6423",
            "ice_hockey": "7524"
        }
        
    async def fetch_polymarket_events(self, limit: int = 100) -> List[Dict]:
        """Fetch active events from Polymarket Gamma API."""
        logger.info(f"Fetching active events from Polymarket (limit={limit})...")
        params = {"active": "true", "closed": "false", "limit": limit, "offset": 0}
        all_events = []
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                while True:
                    resp = await client.get(self.polymarket_url, params=params)
                    if resp.status_code != 200:
                        logger.error(f"Error fetching events: {resp.status_code}")
                        break
                    
                    data = resp.json()
                    if not data:
                        break
                        
                    all_events.extend(data)
                    if len(data) < limit:
                        break
                    
                    params["offset"] += limit
                    await asyncio.sleep(0.5)
                    
            logger.info(f"Retrieved {len(all_events)} events.")
            return all_events
        except Exception as e:
            logger.error(f"Exception fetching events: {e}")
            return []

    async def fetch_betfair_events(self) -> List[Dict]:
        """Fetch active events from Betfair."""
        logger.info("Fetching active events from Betfair...")
        if not self.betfair.is_authenticated:
            logger.info("Betfair not authenticated, logging in...")
            if not await self.betfair.login():
                logger.error("Betfair login failed")
                return []
        
        all_bf_events = []
        for sport_name, sport_id in self.betfair_sport_ids.items():
            try:
                events = await self.betfair.list_events(event_type_ids=[sport_id])
                logger.info(f"Retrieved {len(events)} events for Betfair {sport_name}.")
                for e in events:
                    all_bf_events.append({
                        'title': e['name'],
                        'sport': sport_name,
                        'source': 'betfair',
                        'country': e.get('country_code')
                    })
            except Exception as ex:
                logger.error(f"Error fetching Betfair events for {sport_name}: {ex}")
        
        return all_bf_events

    def clean_title(self, title: str) -> str:
        """Clean title of common prefixes, suffixes, and noise for better regex matching."""
        # Split by ':' or ' - ' to remove market info (e.g. "Team: O/U 3.5" -> "Team")
        t = re.split(r'[:\-]', title)[0]
        
        # Remove common prefixes/suffixes
        t = re.sub(r'^(Will|Who|How many|Total|Over/Under|Spread|Market)\s+', '', t, flags=re.IGNORECASE)
        t = re.sub(r'\s+(win\??|defeat\??|beats\??|win on|win the|win by|win game\s?\d|win match\s?\d|sells any|price|at any point|O/U\s?[\d\.]+|\?)$', '', t, flags=re.IGNORECASE)
        
        # Remove explicit betting terms
        t = re.sub(r'\b(Over/Under|Handicap|Total Goals|Total Games|Total Sets|Asian Handicap|Winner|Markets|Correct Score|BTTS)\b.*', '', t, flags=re.IGNORECASE)
        
        # Remove dates/years
        t = re.sub(r'\b(202[0-9]|2[0-9]-[0-9]{2})\b', '', t)
        
        # Remove common ordinals/round info
        t = re.sub(r'\b(Final|Semifinal|Round \d|Wimbledon|US Open|French Open|Australian Open|NBA|NFL|MLB|UFC|EPL|La Liga)\b', '', t, flags=re.IGNORECASE)
        
        return t.strip()

    def sanitize_name(self, name: str) -> Optional[str]:
        """Final sanitization of extracted entity name."""
        if not name: return None
        n = name.strip()
        # If it's too long or contains market junk, reject
        if len(n) < 2 or len(n) > 40: return None
        if any(x in n.lower() for x in ['o/u', '3.5', '2.5', 'total', 'handicap', 'score', 'games']): return None
        return n

    def extract_entities_from_title(self, title: str) -> List[str]:
        """Extract team/player names using robust patterns."""
        cleaned = self.clean_title(title)
        
        entities = []
        # Pattern 1: Matchups (vs, @, v.)
        vs_match = re.search(r"(.+?)\s+(?:vs|VS|v|V|@)\.?\s+(.+)", cleaned)
        if vs_match:
            entities = [vs_match.group(1).strip(), vs_match.group(2).strip()]
        else:
            # Pattern 2: Single Entity (remaining cleaned string)
            if cleaned and len(cleaned.split()) <= 4:
                 entities = [cleaned]
        
        # Sanitize all
        return [s for e in entities if (s := self.sanitize_name(e))]

    async def search_the_sports_db(self, name: str, sport: str, is_player: bool = False) -> List[str]:
        """Search for a team or player in TheSportsDB and return aliases."""
        url = self.sports_db_players_url if is_player else self.sports_db_teams_url
        param_key = "p" if is_player else "t"
        
        async with self.semaphore:
            logger.debug(f"Searching TheSportsDB ({'Player' if is_player else 'Team'}): {name}")
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, params={param_key: name})
                    if resp.status_code == 200:
                        data = resp.json()
                        key = 'players' if is_player else 'teams'
                        items = data.get(key)
                        if items:
                            # --- [NEW] Strict Sport Verification ---
                            # Filter results to ensure the sport returned by API matches our target category
                            # The SportsDB uses "Soccer", "Tennis", "Basketball", etc.
                            target_sport_map = {
                                "soccer": ["Soccer"],
                                "tennis": ["Tennis"],
                                "basketball": ["Basketball"],
                                "american_football": ["American Football"],
                                "ice_hockey": ["Ice Hockey"],
                                "baseball": ["Baseball"]
                            }
                            allowed_sports = target_sport_map.get(sport, [])
                            
                            valid_item = None
                            for item in items:
                                item_sport = item.get('strSport')
                                if item_sport in allowed_sports:
                                    valid_item = item
                                    break
                            
                            if not valid_item:
                                logger.warning(f"⚠️ Sport Mismatch for {name}: API returned {items[0].get('strSport')} but expected {sport}")
                                return []
                            
                            item = valid_item
                            if is_player:
                                aliases = [item.get('strPlayer')]
                            else:
                                aliases = [
                                    item.get('strTeam'),
                                    item.get('strTeamShort'),
                                    item.get('strAlternate')
                                ]
                            return list(set([a.strip() for a in aliases if a]))
            except Exception as e:
                logger.error(f"TheSportsDB Error for {name}: {e}")
            return []

    async def process_entity(self, entity: str, sport: str, country: Optional[str] = None) -> Optional[Dict]:
        """Handle a single entity candidate: check resolver, query APIs, or LLM."""
        sharded = self.resolver.get_sharded_entities(sport)
        if entity.lower() in sharded:
            return None
            
        logger.info(f"Processing candidate: {entity} (Sport: {sport}, Country: {country})")
        
        # 1. SportsDB Lookup
        is_tennis = (sport == "tennis")
        aliases = await self.search_the_sports_db(entity, sport=sport, is_player=is_tennis)
        
        # 2. LLM Fallback (now with country context)
        if not aliases:
            await asyncio.sleep(1) # Extra gap before LLM
            aliases = await self.llm_generate_aliases(entity, sport, country)
            
        if aliases:
            return {"canonical": aliases[0], "alias": entity, "all_aliases": aliases, "sport": sport}
        return None

    async def llm_generate_aliases(self, name: str, sport: str, country: Optional[str] = None) -> List[str]:
        """Fallback to LLM for alias generation if API fails."""
        if not self.ai_mapper.enabled:
            return []
            
        logger.debug(f"LLM fallback for: {name} ({sport}, {country})")
        
        country_clause = f" located in or representing '{country}'" if country else ""
        prompt = (
            f"Generate 3-5 common aliases or variations for the entity: '{name}' strictly for the sport category: '{sport}'{country_clause}.\n"
            f"CRITICAL RULES:\n"
            f"1. ONLY return entities that belong to {sport}. For example, if sport is 'soccer', do NOT return Rugby teams like 'Newcastle Knights'.\n"
            f"2. IGNORE market-related junk (handicaps, O/U, scores).\n"
            f"3. Return ONLY a JSON list of strings (e.g. [\"Name 1\", \"Name 2\"])."
        )
        
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": { "type": "json_object" }
        }
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                headers = {"Authorization": f"Bearer {self.ai_mapper.api_key}", "Content-Type": "application/json"}
                resp = await client.post(self.ai_mapper.base_url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data['choices'][0]['message']['content']
                    res = json.loads(content)
                    if isinstance(res, list): return res
                    if isinstance(res, dict):
                        for k in ["aliases", "variations", "names"]:
                            if k in res: return res[k]
        except Exception as e:
            logger.error(f"LLM Error for {name}: {e}")
        return []

    async def run(self, max_events: int = 100):
        """Batch processing loop with improved parsing and concurrency."""
        # 1. Fetch from Polymarket
        poly_events = await self.fetch_polymarket_events(limit=100)
        formatted_poly = []
        for e in poly_events:
             slug = e.get('slug', '').lower()
             sport = self.detect_sport(slug)
             if sport:
                titles = set()
                if e.get('title'): titles.add(e['title'])
                for m in e.get('markets', []):
                    if m.get('question'): titles.add(m['question'])
                    if m.get('title'): titles.add(m['title'])
                for t in titles:
                    formatted_poly.append({'title': t, 'sport': sport, 'source': 'polymarket'})

        # 2. Fetch from Betfair
        bf_events = await self.fetch_betfair_events()
        
        # Combine and shuffle
        all_events = formatted_poly + bf_events
        import random
        random.shuffle(all_events)
        logger.info(f"Total entries to process: {len(all_events)}")

        processed_count = 0
        all_new_mappings = []
        
        # Batching for names
        batch_size = 10
        for i in range(0, min(len(all_events), max_events), batch_size):
            batch = all_events[i : i + batch_size]
            processed_count += len(batch)
            tasks = []
            
            for item in batch:
                title = item['title']
                sport = item['sport']
                country = item.get('country')
                entities = self.extract_entities_from_title(title)
                for entity in entities:
                    tasks.append(self.process_entity(entity, sport, country))
            
            if not tasks:
                continue

            # Execute batch of entity processing
            results = await asyncio.gather(*tasks)
            new_batch_mappings = [r for r in results if r]
            
            if new_batch_mappings:
                for mapping in new_batch_mappings:
                    canonical = mapping['canonical']
                    sport = mapping['sport']
                    # Register main alias (Memory only)
                    self.resolver.add_mapping(canonical=canonical, alias=mapping['alias'], sport_category=sport, auto_save=False)
                    # Register alternates (Memory only)
                    for a in mapping['all_aliases'][1:]:
                        if a.lower() != mapping['alias'].lower():
                            self.resolver.add_mapping(canonical=canonical, alias=a, sport_category=sport, auto_save=False)
                    all_new_mappings.append(mapping)
                
                # Persistence after each batch
                self.resolver.save_mappings()
                self.resolver._load_mappings() # Refresh memory after save
                logger.info(f"Batch completed: Added {len(new_batch_mappings)} mappings.")
            
            await asyncio.sleep(1) # Be nice between batches
            
        logger.info(f"Done! Processed {processed_count} items, found {len(all_new_mappings)} new mapping entities.")

    def detect_sport(self, slug: str) -> Optional[str]:
        """Detect sport from slug with exclusion rules."""
        s = slug.lower()
        
        # 1. Exclusion List (Politics, Crypto, Entertainment)
        exclusions = ['election', 'politics', 'senate', 'governor', 'president', 'crypto', 'bitcoin', 'eth', 'price', 'movie', 'oscars']
        if any(x in s for x in exclusions):
            return None

        # 2. Specific Sports
        if 'soccer' in s or 'premier-league' in s or 'la-liga' in s or 'serie-a' in s or 'bundesliga' in s or 'ligue-1' in s or 'mls' in s:
            return "soccer"
        elif 'nba' in s or 'basketball' in s or 'euroleague' in s or 'wnba' in s:
            return "basketball"
        elif 'tennis' in s or 'atp' in s or 'wta' in s:
            return "tennis"
        elif 'nhl' in s or 'hockey' in s:
            return "ice_hockey"
        elif 'nfl' in s or 'football' in s or 'ncaa-football' in s:
            return "american_football"
        elif 'baseball' in s or 'mlb' in s:
            return "baseball"
        
        # 3. Generic fallback (Only if it looks like a matchup)
        if any(x in s for x in ['vs', 'defeats', 'beats']):
            return "soccer" # Matchups default to soccer if not specified
            
        return None

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Dynamic Polymarket Mapping Enricher")
    parser.add_argument("--max-events", type=int, default=100, help="Max number of events to process")
    args = parser.parse_args()
    
    enricher = DynamicEnricher()
    asyncio.run(enricher.run(max_events=args.max_events))
