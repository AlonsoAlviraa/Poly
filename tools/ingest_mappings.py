
import json
import logging
import re
import requests
import io
import pandas as pd
from typing import Dict, List, Set, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MAPPINGS_FILE = "src/data/mappings.json"

class MappingIngester:
    def __init__(self):
        self.mappings: Dict[str, Dict] = {
            "soccer": {},
            "tennis": {},
            "basketball": {},
            "american_football": {},
            "baseball": {},
            "ice_hockey": {},
            "esports": {}
        }
    
    def fetch_soccer(self):
        """Fetch soccer teams from footballcsv (Raw CSVs from GitHub)."""
        logger.info("[Soccer] Fetching data from ~20 leagues (footballcsv)...")
        
        # Sources: raw.githubusercontent.com/footballcsv/[repo]/master/[season]/[league].csv
        base_url = "https://raw.githubusercontent.com/footballcsv"
        
        sources = [
            # Top 5 (Corrected Repo Names)
            f"{base_url}/england/master/2020s/2020-21/eng.1.csv",
            f"{base_url}/espana/master/2020s/2020-21/es.1.csv",
            f"{base_url}/deutschland/master/2020s/2020-21/de.1.csv",
            f"{base_url}/italy/master/2020s/2020-21/it.1.csv",
            f"{base_url}/france/master/2020s/2020-21/fr.1.csv",
            
            # Second Tiers
            f"{base_url}/england/master/2020s/2020-21/eng.2.csv",
            f"{base_url}/espana/master/2020s/2020-21/es.2.csv",
            f"{base_url}/deutschland/master/2020s/2020-21/de.2.csv",
            
            # Global / Others
            f"{base_url}/portugal/master/2020s/2020-21/pt.1.csv",
            f"{base_url}/belgie/master/2020s/2020-21/be.1.csv",
            f"{base_url}/österreich/master/2020s/2020-21/at.1.csv",
            f"{base_url}/scotland/master/2020s/2020-21/sc.1.csv",
            f"{base_url}/brasil/master/2020s/2020/br.1.csv",
            f"{base_url}/argentina/master/2020s/2020/ar.1.csv",
            f"{base_url}/mexico/master/2020s/2020-21/mx.1.csv",
            f"{base_url}/usa/master/2020s/2021/us.1.csv",
        ]
        
        count = 0
        for url in sources:
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    df = pd.read_csv(io.StringIO(resp.text))
                    if 'Team 1' in df.columns:
                        teams = pd.concat([df['Team 1'], df['Team 2']]).unique()
                        for team in teams:
                            if team and isinstance(team, str):
                                aliases = self._generate_soccer_aliases(team)
                                self._add_entity("soccer", team, aliases)
                                count += 1
                else:
                    logger.debug(f"[Soccer] URL not found: {url}")
            except Exception as e:
                logger.warning(f"[Soccer] Failed to fetch {url}: {e}")
        
        # Fallback Expanded
        fallback_teams = [
            "Manchester City FC", "Arsenal FC", "Liverpool FC", "Real Madrid CF", "FC Barcelona",
            "Atletico Madrid", "Bayern Munich", "Borussia Dortmund", "Paris Saint-Germain", "Juventus FC",
            "Inter Milan", "AC Milan", "Napoli", "Atalanta BC", "AS Roma", "Bayer Leverkusen", 
            "RB Leipzig", "Ajax", "PSV Eindhoven", "Feyenoord", "Benfica", "FC Porto", "Sporting CP"
        ]
        for team in fallback_teams:
            aliases = self._generate_soccer_aliases(team)
            self._add_entity("soccer", team, aliases)
            count += 1
                
        logger.info(f"[Soccer] Ingested {count} unique teams (including fallbacks).")

    def _generate_soccer_aliases(self, canonical: str, code: str = None) -> List[str]:
        aliases = set()
        if code:
            aliases.add(code)
        
        # Variations: "Arsenal FC" -> "Arsenal"
        name = canonical
        aliases.add(name)
        
        # Remove common suffixes
        cleaned = re.sub(r'\s(FC|CF|SC|BC|AS|United|City|Athletic|Real|Club|Deportivo|S\.A\.)$', '', name, flags=re.IGNORECASE).strip()
        if cleaned and cleaned != name:
            aliases.add(cleaned)
            
        # Specific patterns
        if "Manchester" in name:
            aliases.add(name.replace("Manchester", "Man"))
            aliases.add(name.replace("Manchester", "Man."))
        
        return list(aliases)

    def fetch_tennis(self):
        """Fetch Tennis players (ATP/WTA) via GitHub CSV."""
        logger.info("[Tennis] Fetching ATP players...")
        # ATP Players (JeffSackmann)
        url = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_players.csv"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                df = pd.read_csv(io.StringIO(resp.text))
                # Columns: player_id, name_first, name_last, hand, dob, country
                # Filter for active/recent players (dob > 1985 roughly to keep size manageable, or just top logic)
                # Since we don't have rank here easily without matches, let's take all who have a name
                
                # Heuristic: Process chunk, or limit to known names if possible. 
                # Better: Use a list of current top 100 if available, but for now ingestion is fine.
                # We will limit to ~500 most recent entries based on IDs (higher ID = newer player usually)
                
                recent_players = df.tail(2000) # Last 2000 registered players
                
                count = 0
                for _, row in recent_players.iterrows():
                    first = str(row['name_first']).strip()
                    last = str(row['name_last']).strip()
                    if first and last and first != 'nan' and last != 'nan':
                        canonical = f"{first} {last}"
                        aliases = self._generate_player_aliases(first, last)
                        self._add_entity("tennis", canonical, aliases)
                        count += 1
                logger.info(f"[Tennis] Ingested {count} ATP players.")
        except Exception as e:
            logger.warning(f"[Tennis] Failed data fetch: {e}")

    def _generate_player_aliases(self, first: str, last: str) -> List[str]:
        aliases = set()
        aliases.add(f"{first} {last}")
        aliases.add(f"{first[0]}. {last}") # J. Sinner
        aliases.add(f"{last}")             # Sinner
        return list(aliases)

    def fetch_us_sports(self):
        """Fetch NBA, NFL, MLB, NHL teams."""
        logger.info("[US Sports] Fetching data...")
        
        # Dictionary of leagues and their wiki/data source (Simulated with static lists for stability 
        # as fetching wikipedia HTML is messy without explicit scraping libs like BS4)
        
        # Hardcoded lists for reliability in this sprint, but structured for expansion
        nba_teams = [
            "Atlanta Hawks", "Boston Celtics", "Brooklyn Nets", "Charlotte Hornets", "Chicago Bulls",
            "Cleveland Cavaliers", "Dallas Mavericks", "Denver Nuggets", "Detroit Pistons", "Golden State Warriors",
            "Houston Rockets", "Indiana Pacers", "Los Angeles Clippers", "Los Angeles Lakers", "Memphis Grizzlies",
            "Miami Heat", "Milwaukee Bucks", "Minnesota Timberwolves", "New Orleans Pelicans", "New York Knicks",
            "Oklahoma City Thunder", "Orlando Magic", "Philadelphia 76ers", "Phoenix Suns", "Portland Trail Blazers",
            "Sacramento Kings", "San Antonio Spurs", "Toronto Raptors", "Utah Jazz", "Washington Wizards"
        ]
        
        nfl_teams = [
            "Arizona Cardinals", "Atlanta Falcons", "Baltimore Ravens", "Buffalo Bills", "Carolina Panthers",
            "Chicago Bears", "Cincinnati Bengals", "Cleveland Browns", "Dallas Cowboys", "Denver Broncos",
            "Detroit Lions", "Green Bay Packers", "Houston Texans", "Indianapolis Colts", "Jacksonville Jaguars",
            "Kansas City Chiefs", "Las Vegas Raiders", "Los Angeles Chargers", "Los Angeles Rams", "Miami Dolphins",
            "Minnesota Vikings", "New England Patriots", "New Orleans Saints", "New York Giants", "New York Jets",
            "Philadelphia Eagles", "Pittsburgh Steelers", "San Francisco 49ers", "Seattle Seahawks", "Tampa Bay Buccaneers",
            "Tennessee Titans", "Washington Commanders"
        ]

        # Add NBA
        for team in nba_teams:
            aliases = self._generate_us_aliases(team)
            self._add_entity("basketball", team, aliases)
            
        # Add NFL
        for team in nfl_teams:
            aliases = self._generate_us_aliases(team)
            self._add_entity("american_football", team, aliases)

        # NCAA Division I (Subset of major) - Vital for Poly
        ncaa_teams = [
            "Duke Blue Devils", "North Carolina Tar Heels", "Kansas Jayhawks", "Kentucky Wildcats", 
            "UConn Huskies", "Alabama Crimson Tide", "Gonzaga Bulldogs", "Houston Cougars",
            "Purdue Boilermakers", "Arizona Wildcats", "Tennessee Volunteers", "Marquette Golden Eagles"
        ]
        for team in ncaa_teams:
            aliases = self._generate_us_aliases(team)
            self._add_entity("basketball", team, aliases) # Categorize as basketball for now
            
        logger.info(f"[US Sports] Ingested {len(nba_teams)} NBA, {len(nfl_teams)} NFL, {len(ncaa_teams)} NCAA.")

    def _generate_us_aliases(self, canonical: str) -> List[str]:
        """
        Generate aliases for US teams (City + Mascot).
        Canonical: "Los Angeles Lakers"
        Aliases: ["Lakers", "LA Lakers", "L.A. Lakers"]
        """
        aliases = set()
        aliases.add(canonical)
        
        parts = canonical.split()
        if len(parts) >= 2:
            # Mascot only (Last word usually, but simple heuristic)
            mascot = parts[-1] 
            aliases.add(mascot)
            
            # City + Mascot (if City matches abbreviations)
            if "Los Angeles" in canonical:
                aliases.add(canonical.replace("Los Angeles", "LA"))
                aliases.add(canonical.replace("Los Angeles", "L.A."))
            if "New York" in canonical:
                aliases.add(canonical.replace("New York", "NY"))
                aliases.add(canonical.replace("New York", "N.Y."))
                
        return list(aliases)

    def fetch_esports(self):
        """Fetch major Esports teams (Valorant, LoL, CS2, Dota2)."""
        logger.info("[Esports] Fetching major teams...")
        
        # Major Esports organizations that compete across multiple games
        esports_orgs = [
            # Tier 1 Orgs
            "T1", "Cloud9", "Fnatic", "G2 Esports", "Team Liquid", "100 Thieves",
            "NRG Esports", "Sentinels", "FaZe Clan", "NAVI", "Team Vitality",
            "Evil Geniuses", "TSM", "Gen.G", "DRX", "LOUD", "Paper Rex",
            "EDward Gaming", "JD Gaming", "Top Esports", "Bilibili Gaming",
            "Team Spirit", "OG", "Gaimin Gladiators", "Team Secret", "BetBoom Team",
            "Astralis", "MOUZ", "Heroic", "ENCE", "Virtus.pro",
            # VCT Teams
            "MIBR", "Leviatán", "KRÜ Esports", "FURIA", "Keyd Stars",
            # LCK/LPL
            "T1 LoL", "Gen.G LoL", "Hanwha Life Esports", "KT Rolster", "Dplus KIA",
            "LNG Esports", "Weibo Gaming", "FunPlus Phoenix", "OMG", "RNG",
        ]
        
        for org in esports_orgs:
            aliases = self._generate_esports_aliases(org)
            self._add_entity("esports", org, aliases)
        
        logger.info(f"[Esports] Ingested {len(esports_orgs)} organizations.")
    
    def _generate_esports_aliases(self, canonical: str) -> List[str]:
        """Generate aliases for esports organizations."""
        aliases = set()
        aliases.add(canonical)
        
        # Common abbreviations
        if "Esports" in canonical:
            aliases.add(canonical.replace(" Esports", ""))
        if "Gaming" in canonical:
            aliases.add(canonical.replace(" Gaming", ""))
        
        # Specific org aliases
        aliases_map = {
            "G2 Esports": ["G2", "G2 LoL", "G2 Valorant"],
            "Cloud9": ["C9", "Cloud 9"],
            "Team Liquid": ["TL", "Liquid"],
            "100 Thieves": ["100T"],
            "NAVI": ["Natus Vincere", "Na'Vi"],
            "Evil Geniuses": ["EG"],
            "FaZe Clan": ["FaZe"],
            "Sentinels": ["SEN"],
            "Gen.G": ["GenG", "Gen G"],
        }
        
        if canonical in aliases_map:
            aliases.update(aliases_map[canonical])
        
        return list(aliases)
    
    def fetch_ice_hockey(self):
        """Fetch NHL teams."""
        logger.info("[Ice Hockey] Fetching NHL teams...")
        
        nhl_teams = [
            "Anaheim Ducks", "Arizona Coyotes", "Boston Bruins", "Buffalo Sabres",
            "Calgary Flames", "Carolina Hurricanes", "Chicago Blackhawks", "Colorado Avalanche",
            "Columbus Blue Jackets", "Dallas Stars", "Detroit Red Wings", "Edmonton Oilers",
            "Florida Panthers", "Los Angeles Kings", "Minnesota Wild", "Montreal Canadiens",
            "Nashville Predators", "New Jersey Devils", "New York Islanders", "New York Rangers",
            "Ottawa Senators", "Philadelphia Flyers", "Pittsburgh Penguins", "San Jose Sharks",
            "Seattle Kraken", "St. Louis Blues", "Tampa Bay Lightning", "Toronto Maple Leafs",
            "Vancouver Canucks", "Vegas Golden Knights", "Washington Capitals", "Winnipeg Jets"
        ]
        
        for team in nhl_teams:
            aliases = self._generate_us_aliases(team)
            self._add_entity("ice_hockey", team, aliases)
        
        logger.info(f"[Ice Hockey] Ingested {len(nhl_teams)} NHL teams.")

    def _add_entity(self, category: str, canonical: str, aliases: List[str]):
        if category not in self.mappings:
            self.mappings[category] = {}
            
        if canonical not in self.mappings[category]:
            self.mappings[category][canonical] = []
        
        # Merge unique aliases
        current = set(self.mappings[category][canonical])
        current.update(aliases)
        self.mappings[category][canonical] = list(current)

    def merge_existing(self):
        """Merge with existing mappings.json to preserve manual entries."""
        try:
            with open(MAPPINGS_FILE, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                
            for category, entities in existing.items():
                if category not in self.mappings:
                    self.mappings[category] = {}
                
                for canonical, aliases in entities.items():
                    self._add_entity(category, canonical, aliases)
                    
            logger.info("Merged existing mappings successfully.")
        except FileNotFoundError:
            logger.info("No existing mappings found. Creating new.")
        except Exception as e:
            logger.error(f"Error merging existing mappings: {e}")

    def save(self):
        """Save to JSON."""
        with open(MAPPINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.mappings, f, indent=4, sort_keys=True, ensure_ascii=False)
        logger.info(f"Saved mappings to {MAPPINGS_FILE}")

if __name__ == "__main__":
    ingester = MappingIngester()
    
    # 1. Fetch Data (All Categories)
    ingester.fetch_soccer()
    ingester.fetch_tennis()
    ingester.fetch_us_sports()
    ingester.fetch_esports()
    ingester.fetch_ice_hockey()
    
    # 2. Merge & Save
    ingester.merge_existing()
    ingester.save()
