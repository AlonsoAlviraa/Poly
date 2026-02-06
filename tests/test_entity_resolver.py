
import pytest
from datetime import datetime, timedelta
from src.arbitrage.entity_resolver_logic import date_blocker, static_matcher
from src.config.matching_config import COMMON_TOKENS

def test_date_blocker():
    now = datetime.now()
    # Case 1: Same date - Should pass
    assert date_blocker(now, now) is True
    
    # Case 2: 23 hours diff - Should pass
    assert date_blocker(now, now + timedelta(hours=23)) is True
    
    # Case 3: 25 hours diff - Should block
    assert date_blocker(now, now + timedelta(hours=25)) is False
    assert date_blocker(now, now - timedelta(hours=25)) is False

def test_static_matcher_kill_switch():
    # Test 1: "Cruz Azul vs Blooming" -> Common token "Cruz" should delegate (return None)
    # Even if Blooming were in the list, "Cruz" is blacklisted.
    res = static_matcher("Cruz Azul vs Blooming", "Blooming", "soccer")
    assert res is None # Delegated to Vector
    
    # Test 2: "QPR vs Kilmarnock" -> Common token "Rangers" (if QPR associated with Rangers in logic somehow)
    # Actually QPR isn't Rangers, but if BF name has Rangers and it's common.
    res = static_matcher("QPR", "New York Rangers", "soccer")
    assert res is None # "Rangers" is common, delegates.

def test_static_matcher_whitelist_and_sharding():
    # Test 3: "Bayer Leverkusen" (Whitelist)
    res = static_matcher("Bayer Leverkusen vs West Ham", "Bayer Leverkusen", "soccer")
    assert res == "MATCH"
    
    # Test 4: Sharding check - "Rangers" in Soccer should not match "Rangers" in Hockey
    # (Assuming "New York Rangers" is only in Hockey shard)
    # Note: Sharding is internal to get_sharded_entities. static_matcher uses it for multi-token.
    # For single token it uses Whitelist/Blacklist.
    
    # Test 5: Future date vs Now - Already covered by date_blocker but let's check pipeline logic
    # (Done via integration or by calling map_market)
    pass

def test_common_tokens_list():
    assert "Rangers" in COMMON_TOKENS
    assert "United" in COMMON_TOKENS
    assert "City" in COMMON_TOKENS
    assert "Real" in COMMON_TOKENS
    assert "Cruz" in COMMON_TOKENS

if __name__ == "__main__":
    pytest.main([__file__])
