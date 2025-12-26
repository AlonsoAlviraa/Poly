import re
from thefuzz import fuzz
from src.utils.normalization import normalize_text

class PlayerMatcher:
    def __init__(self):
        # Mappings for Stat Types
        self.stat_map = {
            "player_points": ["points", "pts", "score", "scored"],
            "player_assists": ["assists", "ast"],
            "player_rebounds": ["rebounds", "rebs", "reb"],
        }
        
    def parse_bookmaker_props(self, event):
        """
        Extracts player props from a Bookmaker event object.
        Returns a list of dicts: {'player': 'LeBron James', 'market': 'player_points', 'line': 25.5, 'over_price': 1.9, 'under_price': 1.9, 'bookie': 'fanduel'}
        """
        props = []
        bookmakers = event.get("bookmakers", [])
        for bookie in bookmakers:
            bookie_key = bookie.get("key")
            markets = bookie.get("markets", [])
            for market in markets:
                market_key = market.get("key")
                # Check if it's a known prop market
                if market_key not in self.stat_map:
                    continue
                
                outcomes = market.get("outcomes", [])
                # Outcomes structure: [{'name': 'Over', 'description': 'Player Name', 'price': 1.9, 'point': 25.5}, ...]
                
                # Group by Player + Line
                # We need to find matching Over/Under pairs to form a complete market if possible, 
                # but for arbitrage against Poly (which might be single sided?), we just need the odds.
                
                # Let's extract individual quotes first
                for outcome in outcomes:
                    player_name = outcome.get("description") # 'LeBron James'
                    side = outcome.get("name") # 'Over' or 'Under'
                    line = outcome.get("point")
                    price = outcome.get("price")
                    
                    if not player_name or not line or not price:
                        continue
                        
                    props.append({
                        "player_raw": player_name,
                        "player_norm": normalize_text(player_name),
                        "market_key": market_key,
                        "side": side.lower(), # 'over' or 'under'
                        "line": float(line),
                        "price": float(price),
                        "bookie": bookie_key,
                        "event_id": event.get("id"),
                        "event_name": f"{event.get('home_team')} vs {event.get('away_team')}"
                    })
        return props

    def parse_polymarket_prop(self, event):
        """
        Parses a Polymarket event title to extract Player, Stat, and Line.
        Example: "LeBron James points > 25.5?" or "Will LeBron James score 25+ points?"
        """
        title = event.get("title", "")
        market_slug = event.get("slug", "") # e.g. "lebron-james-over-25-5-points"
        
        # Regex strategies
        # 1. "Player Name ... Stat ... Line"
        # 2. "Stat ... Player Name ... Line"
        
        # Simple extraction attempts using self.stat_map keys
        found_stat = None
        for stat_key, aliases in self.stat_map.items():
            for alias in aliases:
                if alias in title.lower():
                    found_stat = stat_key
                    break
            if found_stat:
                break
        
        if not found_stat:
            return None # Not a recognized prop
            
        # Extract Line (Number)
        # Look for floats or integers possibly preceded by > < or +
        # "25.5" or "25+"
        import re
        # Match number at end or middle: (\d+\.?\d*)
        # Context hints: ">", "Over"
        
        # Logic: If "> 25.5", it's Over 25.5.
        
        line_match = re.search(r"(\d+\.?\d*)", title)
        if not line_match:
            return None
            
        line = float(line_match.group(1))
        
        # Determine Player Name
        # Remove stat keywords and line from title, remainder is likely player name?
        # e.g. "LeBron James 25.5 Points" -> "LeBron James"
        # Robust way: Compare against known bookie players?
        # For parsing, let's keep it fuzzy.
        
        # Clean title to get player name candidate
        # This is hard. "Will LeBron James score...?"
        
        return {
            "title": title,
            "stat_type": found_stat,
            "line": line,
            "poly_id": event.get("id"),
            # "player_guess": ... # To be matched later
        }

    def match_player_prop(self, bookie_prop, poly_event):
        """
        Matches a specific Bookmaker Prop against a Polymarket Event.
        """
        # 1. Match Stat Type
        poly_parsed = self.parse_polymarket_prop(poly_event)
        if not poly_parsed or poly_parsed["stat_type"] != bookie_prop["market_key"]:
            return None
            
        # 2. Match Line (Exact)
        # Polymarket often uses 0.5 steps differently? "25+" usually means >= 25 (Over 24.5).
        # "> 25.5" means Over 25.5.
        # Let's require exact equality for initial safety.
        if poly_parsed["line"] != bookie_prop["line"]:
             return None
             
        # 3. Match Player Name (Fuzzy)
        # Check if Bookie Player Name is in Poly Title
        # "LeBron James" in "LeBron James > 25.5 Points?"
        
        ratio = fuzz.partial_token_set_ratio(bookie_prop["player_norm"], normalize_text(poly_parsed["title"]))
        if ratio < 85:
            return None
            
        return {
            "match_score": ratio,
            "bookie_prop": bookie_prop,
            "poly_prop": poly_parsed
        }
