import json
import os
import csv
from thefuzz import fuzz
from datetime import datetime
from src.utils.normalization import normalize_text

class EventMatcher:
    def __init__(self, cache_file="known_teams.json", alias_file="data/team_mappings.json", review_file="review_needed.csv"):
        self.cache_file = cache_file
        self.alias_file = alias_file
        self.review_file = review_file
        self.known_teams = self._load_json(self.cache_file)
        self.aliases = self._load_json(self.alias_file)

    def _load_json(self, filepath):
        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def get_alias(self, name):
        """
        Check alias dictionary.
        """
        norm = normalize_text(name)
        raw_lower = name.lower().strip()
        
        if raw_lower in self.aliases:
            return self.aliases[raw_lower]
        if norm in self.aliases:
            return self.aliases[norm]
            
        return norm

    def match_events(self, bookie_events, poly_events):
        matches = []
        log_entries = []

        print(f"DEBUG: Matching {len(bookie_events)} Bookie events vs {len(poly_events)} Poly events.")
        
        if bookie_events:
            print(f"Sample Bookie Date: {bookie_events[0].get('commence_time')}")
        if poly_events:
            print(f"Sample Poly Date: {poly_events[0].get('startDate')}") # Check key name

        for b_event in bookie_events:
            b_home = b_event.get("home_team", "")
            b_away = b_event.get("away_team", "")
            b_start = b_event.get("commence_time", "")
            
            if not b_home or not b_away:
                continue

            b_home_clean = self.get_alias(b_home)
            b_away_clean = self.get_alias(b_away)
            
            for p_event in poly_events:
                p_title = p_event.get("title", "")
                p_start = p_event.get("startDate", "")
                
                if not p_start:
                    continue

                # Time Check (48h window)
                if not self._is_same_day(b_start, p_start):
                    continue

                # Normalize Poly Title
                p_title_clean = normalize_text(p_title)
                
                # Fuzzy Match
                score_home = fuzz.token_set_ratio(b_home_clean, p_title_clean)
                score_away = fuzz.token_set_ratio(b_away_clean, p_title_clean)
                
                avg_score = (score_home + score_away) / 2
                
                # Debug print for lower scores
                if avg_score > 40:
                     print(f"DEBUG: '{b_home_clean}'/'{b_away_clean}' vs '{p_title_clean}' -> Score: {avg_score}")

                if avg_score >= 75:
                    print(f"MATCH FOUND: {b_home} vs {b_away} <=> {p_title} (Score: {avg_score})")
                    matches.append((b_event, p_event))
                    break # Assume 1 match
                elif 40 <= avg_score < 75:
                    print(f"[NEAR MISS] {b_home} vs {b_away} <=> {p_title} (Score: {avg_score})")
                    log_entries.append([
                        datetime.now(),
                        b_home, b_away, p_title, avg_score, "Near Miss"
                    ])
        
        # Write logs
        if log_entries:
            file_exists = os.path.exists(self.review_file)
            with open(self.review_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Timestamp", "Bookie Home", "Bookie Away", "Poly Title", "Score", "Type"])
                writer.writerows(log_entries)

        return matches

    def _is_same_day(self, date_str1, date_str2):
        try:
            # Handle Z for UTC
            d1 = datetime.fromisoformat(date_str1.replace("Z", "+00:00")).date()
            d2 = datetime.fromisoformat(date_str2.replace("Z", "+00:00")).date()
            delta = abs((d1 - d2).days)
            if delta > 2:
                # print(f"DEBUG: Date mismatch {d1} vs {d2}")
                return False
            return True
        except Exception as e:
            print(f"DEBUG: Date parse error: {e} for '{date_str1}' vs '{date_str2}'")
            return False
