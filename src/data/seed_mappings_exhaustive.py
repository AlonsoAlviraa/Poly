
import asyncio
import aiohttp
import json
import os
import logging
from typing import List, Dict, Any, Optional
from src.data.cache_manager import CacheManager
from src.utils.async_patterns import RobustConnection

logger = logging.getLogger("SportsSeeder")

class SportsSeeder:
    """
    ETL Pipeline para pre-poblar el CacheManager con entidades de API-Sports.
    Incluye semáforos para Rate Limit y Checkpointing para reanudación.
    """
    API_STATIONS = {
        "football": "https://v3.football.api-sports.io",
        "basketball": "https://v1.basketball.api-sports.io",
        "tennis": "https://v1.tennis.api-sports.io"
    }

    def __init__(self, api_key: str, cache_mgr: CacheManager):
        self.api_key = api_key
        self.cache_mgr = cache_mgr
        self.semaphore = asyncio.Semaphore(5) # Max 5 concurrent requests
        self.checkpoint_path = "mapping_cache/seeder_checkpoint.json"
        self.checkpoint = self._load_checkpoint()

    def _load_checkpoint(self) -> Dict:
        if os.path.exists(self.checkpoint_path):
            with open(self.checkpoint_path, 'r') as f:
                return json.load(f)
        return {"completed_leagues": []}

    def _save_checkpoint(self, league_id: str, sport: str):
        self.checkpoint["completed_leagues"].append(f"{sport}_{league_id}")
        with open(self.checkpoint_path, 'w') as f:
            json.dump(self.checkpoint, f)

    async def fetch_entities(self, sport: str, endpoint: str, params: Dict):
        """Extract: Llamada con Rate Limit."""
        url = f"{self.API_STATIONS[sport]}/{endpoint}"
        headers = {
            "x-apisports-key": self.api_key,
            "x-rapidapi-host": f"v3.{sport}.api-sports.io" if sport == "football" else f"v1.{sport}.api-sports.io"
        }
        
        async with self.semaphore:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"API Error {response.status} for {url}")
                        return None

    async def seed_football(self, league_ids: List[int]):
        """Pipeline para Fútbol."""
        for lid in league_ids:
            if f"football_{lid}" in self.checkpoint["completed_leagues"]:
                logger.info(f"Skipping football league {lid} (already seeded)")
                continue

            logger.info(f"Seeding football league {lid}...")
            data = await self.fetch_entities("football", "teams", {"league": lid, "season": 2024})
            
            if data and data.get("response"):
                for item in data["response"]:
                    team = item["team"]
                    # Transform & Load
                    canonical = team["name"]
                    aliases = [team["name"], team.get("code")]
                    # Add more aliases if needed
                    for alias in filter(None, aliases):
                        self.cache_mgr.save_entity(alias, canonical, "football")
                
                self._save_checkpoint(str(lid), "football")
                await asyncio.sleep(1) # Polite delay

    async def seed_all_major(self):
        """Core ETL Task."""
        # Football: Premier League (39), La Liga (140), Serie A (135), Bundesliga (78), Ligue 1 (61)
        major_leagues = [39, 140, 135, 78, 61]
        await self.seed_football(major_leagues)
        
        # TODO: Implement Basketball (NBA, Euroleague) and Tennis (ATP, WTA)
        logger.info("Exhaustive Seeding Cycle Completed.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    import sys
    key = os.getenv("API_SPORTS_KEY")
    if not key:
        print("Error: API_SPORTS_KEY not found in env. Please set it to seed team entities.")
        # Proceed with empty key if testing logic, but seeder will fail fetch
        sys.exit(1)
        
    cache = CacheManager()
    seeder = SportsSeeder(key, cache)
    asyncio.run(seeder.seed_all_major())
