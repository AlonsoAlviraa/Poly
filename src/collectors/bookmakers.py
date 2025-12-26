import aiohttp
import asyncio
from datetime import datetime, timedelta
from config import ODDS_API_KEYS

class BookmakerClient:
    def __init__(self):
        # API Key Rotation
        self.api_keys = ODDS_API_KEYS
        self.current_key_index = 0
        print(f"📊 BookmakerClient initialized with {len(self.api_keys)} API keys for rotation")
        
        self.base_url = "https://api.the-odds-api.com/v4/sports"
        self.leagues = [
            "soccer_epl",
            "soccer_spain_la_liga",
            "soccer_germany_bundesliga",
            "soccer_italy_serie_a",
            "soccer_france_ligue_one",
            "soccer_uefa_champs_league",
            "basketball_nba",
            "americanfootball_nfl"
        ]
    
    def get_next_api_key(self):
        """Round-robin API key selection"""
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key

    async def fetch_league_odds(self, session, sport, markets="h2h"):
        """
        Fetches odds for a single league asynchronously.
        """
        # 7-day window
        now = datetime.utcnow()
        commence_time_from = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        commence_time_to = (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # For NBA/NFL, we might want player props.
        # But 'markets' can be comma separated.
        
        params = {
            "apiKey": self.get_next_api_key(),  # Rotate API key
            "regions": "eu",
            "markets": markets,
            "oddsFormat": "decimal",
            "commenceTimeFrom": commence_time_from,
            "commenceTimeTo": commence_time_to
        }
        url = f"{self.base_url}/{sport}/odds"
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 429:
                    print(f"Rate limit hit for {sport}. Retrying...")
                    # Simple backoff could be implemented here, but for now just log
                    return []
                response.raise_for_status()
                data = await response.json()
                # print(f"Fetched {len(data)} events for {sport}")
                return data
        except Exception as e:
            print(f"Error fetching odds for {sport}: {e}")
            return []

    async def fetch_event_odds(self, session, sport, event_id, markets):
        """
        Fetches specific markets for a single event.
        """
        url = f"{self.base_url}/{sport}/events/{event_id}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": "us", # Assume US for props
            "markets": markets,
            "oddsFormat": "decimal"
        }
        try:
             async with session.get(url, params=params) as response:
                if response.status == 429:
                    print(f"Rate limit hit for event {event_id}. Retrying...")
                    return None
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            # print(f"Error fetching props for event {event_id}: {e}")
            return None

    async def get_all_odds_async(self):
        """
        Fetches odds for all configured leagues.
        For NBA/NFL, performs 2-step fetch for Player Props.
        """
        all_events = []
        
        async with aiohttp.ClientSession() as session:
            # 1. Fetch Base Events (H2H) for all leagues
            tasks = [self.fetch_league_odds(session, league) for league in self.leagues]
            results = await asyncio.gather(*tasks)
            
            # Flatten H2H results
            h2h_events = []
            for res in results:
                h2h_events.extend(res)
            
            all_events.extend(h2h_events)
            
            # 2. Identify Events needing Props (NBA/NFL)
            prop_tasks = []
            prop_event_count = 0
            max_prop_events = 5  # LIMIT for testing
            
            for event in h2h_events:
                sport = event.get("sport_key")
                event_id = event.get("id")
                
                if sport in ["basketball_nba", "americanfootball_nfl"]:
                    if prop_event_count >= max_prop_events:
                        break
                    # Fetch props
                    markets = "player_points,player_assists,player_rebounds" if sport == "basketball_nba" else "player_pass_yds,player_rush_yds,player_reception_yds"
                    prop_tasks.append(self.fetch_event_odds(session, sport, event_id, markets))
                    prop_event_count += 1
            
            # Fetch Props Concurrently
            if prop_tasks:
                print(f"Fetching props for {len(prop_tasks)} events...")
                prop_results = await asyncio.gather(*prop_tasks)
                
                # Merge logic? Or just append as separate "events" with different market data?
                # The Matcher expects "events". 
                # If I append new objects, the Matcher sees them as duplicates or new events.
                # It's better to MERGE props into the original event object if possible, 
                # OR just treat them as separate data entries.
                # Simpler: Return list of prop-enriched events?
                # Actually, the prop response is an "Event" object with "bookmakers" list.
                # So I can just add them to all_events.
                
                for p in prop_results:
                    if p:
                        all_events.append(p)

            return all_events

if __name__ == "__main__":
    # Test Async Client
    async def test():
        client = BookmakerClient()
        print("Fetching odds asynchronously...")
        start = datetime.now()
        events = await client.get_all_odds_async()
        end = datetime.now()
        print(f"Fetched {len(events)} events in {(end-start).total_seconds():.2f} seconds.")
        if events:
            print(f"Sample: {events[0].get('sport_key')} - {events[0].get('home_team')} vs {events[0].get('away_team')}")

    asyncio.run(test())
