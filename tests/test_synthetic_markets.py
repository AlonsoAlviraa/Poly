import pytest

from src.arbitrage.cross_platform_mapper import CrossPlatformMapper


def test_resolve_over_under_selection():
    mapper = CrossPlatformMapper()
    runners = [
        {"selectionId": "1", "runnerName": "Over 2.5"},
        {"selectionId": "2", "runnerName": "Under 2.5"},
    ]
    sel_id, sel_name = mapper._resolve_over_under_selection("Sevilla vs Girona: Over 2.5", runners, "soccer")
    assert sel_id == "1"
    assert "Over" in sel_name


def test_resolve_draw_selection():
    mapper = CrossPlatformMapper()
    runners = [
        {"selectionId": "1", "runnerName": "Home"},
        {"selectionId": "2", "runnerName": "Draw"},
        {"selectionId": "3", "runnerName": "Away"},
    ]
    sel_id, sel_name = mapper._resolve_draw_selection("Match result - Draw", runners, "soccer")
    assert sel_id == "2"
    assert sel_name == "Draw"


def test_double_side_overlap_guardrail():
    mapper = CrossPlatformMapper()
    assert mapper._verify_team_overlap("Team A vs Team B", "Team A vs Team B", "soccer", allow_fuzzy=False)
    assert not mapper._verify_team_overlap("Team A vs Team B", "Team A vs Other", "soccer", allow_fuzzy=False)


def test_competition_hard_filter():
    mapper = CrossPlatformMapper()
    poly = {"slug": "nba-finals", "category": "basketball"}
    bf_ev = {"name": "Lakers vs Celtics", "competition": "WNBA"}
    assert not mapper._sport_cross_check(poly, bf_ev, "basketball")


def test_market_fingerprint_totals():
    mapper = CrossPlatformMapper()
    fp1 = mapper._market_fingerprint_from_text("Sevilla vs Girona: Over 2.5", market_type="OVER_UNDER_25")
    fp2 = mapper._market_fingerprint_from_text("Sevilla vs Girona: Under 2.5", market_type="OVER_UNDER_25")
    assert fp1 == fp2
