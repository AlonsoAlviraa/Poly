
import pytest
from src.arbitrage.entity_resolver_logic import static_matcher

def test_classic_soccer_aliases():
    # These should match if our system is robust
    assert static_matcher("Man Utd", "Manchester United FC", "soccer") == "MATCH"
    assert static_matcher("Man City", "Manchester City", "soccer") == "MATCH"
    assert static_matcher("Barça", "FC Barcelona", "soccer") == "MATCH"
    assert static_matcher("Madrid", "Real Madrid", "soccer") == "MATCH"

def test_tennis_player_variations():
    # Tennis names are notoriously variable
    assert static_matcher("Nadal", "Rafael Nadal", "tennis") == "MATCH"
    assert static_matcher("R. Nadal", "R. Nadal-Parera", "tennis") == "MATCH"

def test_esports_tags():
    # Esports uses short tags often
    assert static_matcher("G2 Esports", "G2", "esports") == "MATCH"
    assert static_matcher("T1", "SK telecom T1", "esports") == "MATCH"

def test_false_positives():
    # These should NOT match despite sharing tokens
    assert static_matcher("Atletico Madrid", "Real Madrid", "soccer") is None
    assert static_matcher("Manchester City", "Manchester United", "soccer") is None
    assert static_matcher("Paris FC", "Paris Saint-Germain", "soccer") is None

def test_fuzzy_corruption():
    # Fuzzy matching should pick up typos
    assert static_matcher("Manchesteer United", "Manchester United", "soccer") == "MATCH"
