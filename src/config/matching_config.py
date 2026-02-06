
# Matching Configuration for Entity Resolution

# Whitelist of entities that are safe to match with a single token
UNIQUE_IDS = {
    "Bayer Leverkusen", 
    "FC Barcelona", 
    "Real Madrid",
    "Manchester City",
    "Manchester United",
    "Bayern Munich",
    "Paris Saint-Germain",
    "Liverpool",
    "Arsenal",
    "Chelsea",
    "Tottenham Hotspur",
    "Juventus",
    "Inter Milan",
    "AC Milan",
    "Atletico Madrid",
    "Borussia Dortmund",
    "Los Angeles Lakers",
    "Golden State Warriors",
    "Boston Celtics",
    "New York Knicks"
}

# Blacklist of tokens that are too generic and should force Vector Matcher delegation
COMMON_TOKENS = {
    "Rangers", 
    "United", 
    "City", 
    "Real", 
    "Cruz", 
    "Junior", 
    "Athletic", 
    "Central", 
    "Union", 
    "San", 
    "Sport", 
    "Club", 
    "Team", 
    "Racing", 
    "Sporting",
    "National",
    "Youth",
    "Women",
    "U21",
    "U19",
    "FC", 
    "CF", 
    "SC", 
    "Atletico", 
    "CD", 
    "AFC", 
    "v", 
    "vs",
    "Club"
}

# Leagues that we currently operate in
OPERATED_LEAGUES = [
    "Premier League", 
    "La Liga", 
    "NBA", 
    "ATP", 
    "WTA", 
    "Champions League",
    "Bundesliga",
    "Serie A",
    "Ligue 1",
    "Liga MX",
    "Copa Libertadores",
    "NFL",
    "NHL"
]

# Sport Category Mapping (Normalization)
SPORT_ALIASES = {
    "soccer": ["football", "soccer", "fútbol", "balompié"],
    "basketball": ["basketball", "baloncesto"],
    "tennis": ["tennis", "tenis"],
    "ice_hockey": ["ice hockey", "hockey sobre hielo", "nhl"],
    "american_football": ["american football", "nfl", "fútbol americano"],
    "esports": ["esports", "gaming", "league of legends", "csgo", "dota 2"]
}
