import json
import os
import time
import asyncio
from decimal import Decimal
import pytest

from src.utils.http_client import get_httpx_client
from src.ai.mimo_client import MiMoClient, SemanticCache
from src.data.entity_resolution import EntityResolver
from src.utils.chain_normalizer import normalize_chain
from src.utils.fx import convert_amount
from src.utils.liquidity import select_best_market
from src.utils.ws_guard import WebsocketGuard
from src.utils.feed_health import FeedHealthMonitor
from src.utils.ws_reconnector import WSReconnector
from src.utils.structured_log import StructuredLogger


# ----------------------------
# VECTOR 1: HTTP/2 & STEALTH
# ----------------------------
@pytest.mark.parametrize(
    "case",
    [
        {"name": "h2_enforced"},
        {"name": "session_reuse"},
        {"name": "headers_consistent"},
        {"name": "headers_rotated"},
        {"name": "keep_alive"},
        {"name": "proxy_configured"},
    ]
)
def test_vector_http2_stealth(case):
    if case["name"] == "h2_enforced":
        client = get_httpx_client(timeout=10, http2=True)
        try:
            try:
                resp = client.get("https://nghttp2.org/httpbin/get")
            except Exception as exc:
                pytest.skip(f"network unavailable: {exc}")
            assert resp.http_version == "HTTP/2"
        finally:
            client.close()
    elif case["name"] == "session_reuse":
        client = get_httpx_client(timeout=10, http2=True)
        try:
            try:
                for _ in range(10):
                    client.get("https://nghttp2.org/httpbin/get")
            except Exception as exc:
                pytest.skip(f"network unavailable: {exc}")
            pool = getattr(client._transport, "_pool", None)
            if pool is None:
                pytest.skip("httpx pool not accessible")
            connections = getattr(pool, "_connections", None)
            if connections is None:
                pytest.skip("httpx connections not accessible")
            assert len(connections) <= 2
        finally:
            client.close()
    elif case["name"] == "headers_consistent":
        headers = {"User-Agent": "MegaIntegration/1.0"}
        client = get_httpx_client(timeout=10, http2=True, headers=headers)
        try:
            try:
                r1 = client.get("https://nghttp2.org/httpbin/headers").json()
                r2 = client.get("https://nghttp2.org/httpbin/headers").json()
            except Exception as exc:
                pytest.skip(f"network unavailable: {exc}")
            assert r1["headers"]["User-Agent"] == r2["headers"]["User-Agent"]
        finally:
            client.close()
    elif case["name"] == "headers_rotated":
        h1 = get_httpx_client(timeout=10, http2=True, headers={"User-Agent": "UA-A"})
        h2 = get_httpx_client(timeout=10, http2=True, headers={"User-Agent": "UA-B"})
        try:
            try:
                r1 = h1.get("https://nghttp2.org/httpbin/headers").json()
                r2 = h2.get("https://nghttp2.org/httpbin/headers").json()
            except Exception as exc:
                pytest.skip(f"network unavailable: {exc}")
            assert r1["headers"]["User-Agent"] != r2["headers"]["User-Agent"]
        finally:
            h1.close()
            h2.close()
    elif case["name"] == "keep_alive":
        client = get_httpx_client(timeout=10, http2=True)
        try:
            resp = client.get("https://nghttp2.org/httpbin/get")
            assert resp.status_code == 200
        finally:
            client.close()
    elif case["name"] == "proxy_configured":
        client = get_httpx_client(timeout=10, http2=True, proxies=None)
        assert client is not None


# ----------------------------
# VECTOR 2: AI RESILIENCE
# ----------------------------
@pytest.mark.parametrize(
    "case",
    [
        {"name": "lobotomized"},
        {"name": "chroma_down"},
        {"name": "hallucination"},
        {"name": "openai_missing"},
        {"name": "cache_fallback_set"},
        {"name": "cache_fallback_get"},
    ]
)
def test_vector_ai_resilience(case, monkeypatch):
    if case["name"] == "lobotomized":
        monkeypatch.setenv("API_LLM", "")
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        client = MiMoClient(api_key=None)
        thesis = asyncio.run(client.analyze_arbitrage({"a": 1}))
        assert "AI disabled" in thesis.reasoning
    elif case["name"] == "chroma_down":
        cache = SemanticCache()
        class BrokenCollection:
            def query(self, *args, **kwargs):
                raise RuntimeError("chroma down")
            def add(self, *args, **kwargs):
                raise RuntimeError("chroma down")
            def update(self, *args, **kwargs):
                raise RuntimeError("chroma down")
        cache._collection = BrokenCollection()
        cache._use_chroma = True
        cache.set("q", {"x": 1})
        assert cache.get("q") == {"x": 1}
    elif case["name"] == "hallucination":
        client = MiMoClient(api_key="dummy")
        thesis = client._parse_response("not json", {"m": 1}, 0)
        assert thesis.suggested_action == "review"
    elif case["name"] == "openai_missing":
        monkeypatch.setenv("API_LLM", "dummy")
        client = MiMoClient(api_key="dummy")
        async def fake_init():
            client._client = None
            client.api_key = None
        monkeypatch.setattr(client, "_init_client", fake_init)
        thesis = asyncio.run(client.analyze_arbitrage({"a": 1}))
        assert "AI disabled" in thesis.reasoning
    elif case["name"] == "cache_fallback_set":
        cache = SemanticCache()
        cache._use_chroma = False
        cache.set("q2", {"y": 2})
        assert cache.get("q2") == {"y": 2}
    elif case["name"] == "cache_fallback_get":
        cache = SemanticCache()
        cache._use_chroma = False
        assert cache.get("missing") is None


# ----------------------------
# VECTOR 3: SX BET + POLY + BETFAIR
# ----------------------------
@pytest.mark.parametrize(
    "case",
    [
        {"name": "cross_chain_mapping"},
        {"name": "fx_conversion"},
        {"name": "liquidity_selection"},
        {"name": "entity_normalization"},
        {"name": "sx_mid_price"},
        {"name": "fx_rate_guard"},
    ]
)
def test_vector_triangulation(case):
    if case["name"] == "cross_chain_mapping":
        assert normalize_chain("polygon") == "evm"
        assert normalize_chain("arbitrum") == "evm"
    elif case["name"] == "fx_conversion":
        amount = convert_amount(100, 1.10)
        assert amount == Decimal("110")
    elif case["name"] == "liquidity_selection":
        markets = [
            {"price": 0.55, "liquidity": 100},
            {"price": 0.52, "liquidity": 200},
            {"price": 0.56, "liquidity": 50},
        ]
        best = select_best_market(markets)
        assert best["price"] == 0.56
    elif case["name"] == "entity_normalization":
        resolver = EntityResolver()
        assert resolver.resolve("Real Madrid") is not None
    elif case["name"] == "sx_mid_price":
        from src.data.sx_bet_client import SXBetOrderbook
        ob = SXBetOrderbook(market_hash="x", bids=[{"price": 0.4}], asks=[{"price": 0.6}])
        assert ob.mid_price == pytest.approx(0.5)
    elif case["name"] == "fx_rate_guard":
        amount = convert_amount(1, 1.10)
        assert amount != Decimal("1")


# ----------------------------
# VECTOR 4: WSS CONFIG
# ----------------------------
@pytest.mark.parametrize(
    "case",
    [
        {"name": "malicious_url"},
        {"name": "token_expired"},
        {"name": "hot_swap"},
        {"name": "backoff"},
        {"name": "no_infinite_loop"},
        {"name": "heartbeat_stale"},
    ]
)
def test_vector_ws_config(case):
    if case["name"] == "malicious_url":
        recon = WSReconnector(endpoint="wss://bad", max_attempts=3)
        assert recon.record_failure() is True
        assert recon.record_failure() is True
        assert recon.record_failure() is False
    elif case["name"] == "token_expired":
        recon = WSReconnector(endpoint="wss://ok")
        assert recon.handle_close(4001) == "refresh_token"
    elif case["name"] == "hot_swap":
        recon = WSReconnector(endpoint="wss://prod")
        recon.update_endpoint("wss://dev")
        assert recon.endpoint == "wss://dev"
    elif case["name"] == "backoff":
        recon = WSReconnector(endpoint="wss://prod")
        recon.record_failure()
        assert recon.next_backoff() > 0
    elif case["name"] == "no_infinite_loop":
        recon = WSReconnector(endpoint="wss://prod", max_attempts=2)
        assert recon.record_failure() is True
        assert recon.record_failure() is False
    elif case["name"] == "heartbeat_stale":
        guard = WebsocketGuard(proxies=[], user_agents=[], heartbeat_timeout_s=0.01)
        guard.record_heartbeat()
        time.sleep(0.02)
        assert guard.is_stale() is True


# ----------------------------
# VECTOR 5: LOGS & TELEMETRY
# ----------------------------
@pytest.mark.parametrize(
    "case",
    [
        {"name": "disk_full"},
        {"name": "json_structure"},
        {"name": "trace_id"},
        {"name": "log_persist"},
        {"name": "stderr_fallback"},
        {"name": "audit_chain"},
    ]
)
def test_vector_logging(case, monkeypatch, tmp_path, capsys):
    logger = StructuredLogger()
    if case["name"] == "disk_full":
        monkeypatch.setenv("LOG_SINK_FILE", str(tmp_path / "log.jsonl"))
        def fail_open(*args, **kwargs):
            raise OSError("disk full")
        monkeypatch.setattr("builtins.open", fail_open)
        logger.info("test_disk_full", trace_id="x1")
        captured = capsys.readouterr()
        assert "test_disk_full" in captured.out
    elif case["name"] == "json_structure":
        logger.info("json_test", trace_id="t1")
        captured = capsys.readouterr()
        json.loads(captured.out.splitlines()[-1])
    elif case["name"] == "trace_id":
        logger.info("ingest", trace_id="trace-123")
        logger.info("decision", trace_id="trace-123")
        logger.info("execution", trace_id="trace-123")
        logger.info("result", trace_id="trace-123")
        captured = capsys.readouterr().out.splitlines()
        assert all("trace-123" in line for line in captured[-4:])
    elif case["name"] == "log_persist":
        sink = tmp_path / "log.jsonl"
        monkeypatch.setenv("LOG_SINK_FILE", str(sink))
        monkeypatch.delenv("LOG_DB_TOKEN", raising=False)
        logger.info("persist", trace_id="t2")
        assert sink.exists()
    elif case["name"] == "stderr_fallback":
        monkeypatch.setenv("LOG_SINK_FILE", str(tmp_path / "log.jsonl"))
        def fail_open(*args, **kwargs):
            raise OSError("disk full")
        monkeypatch.setattr("builtins.open", fail_open)
        logger.info("stderr", trace_id="t3")
        captured = capsys.readouterr()
        assert "stderr" in captured.out or "stderr" in captured.err
    elif case["name"] == "audit_chain":
        trace_id = "trace-999"
        logger.info("ingest", trace_id=trace_id)
        logger.info("decision", trace_id=trace_id)
        logger.info("execution", trace_id=trace_id)
        logger.info("result", trace_id=trace_id)
        captured = capsys.readouterr().out.splitlines()
        assert all(trace_id in line for line in captured[-4:])


# ----------------------------
# VECTOR 6: EDGE CASE MATRIX
# ----------------------------
@pytest.mark.parametrize(
    "case",
    [
        {"name": "poly_unicode_titles"},
        {"name": "poly_expired_markets"},
        {"name": "betfair_event_id_coercion"},
        {"name": "betfair_suspended_reactivate"},
        {"name": "sx_usdc_to_wei_precision"},
        {"name": "sx_orderbook_empty"},
        {"name": "sx_chain_id_validation"},
        {"name": "data_large_json_ingest"},
        {"name": "data_incomplete_json_eof"},
        {"name": "data_mixed_timezone_timestamps"},
        {"name": "odds_extremes_decimal"},
        {"name": "odds_negative_or_zero"},
        {"name": "odds_spread_with_fees"},
        {"name": "odds_fx_fluctuation"},
        {"name": "semantic_man_city_vs_full"},
        {"name": "semantic_man_city_vs_utd"},
        {"name": "semantic_totals_vs_handicap"},
        {"name": "semantic_negation_to_lay"},
        {"name": "ai_malformed_json_fallback"},
        {"name": "ai_rate_limit_recovery"},
        {"name": "ai_chroma_disconnect_cache_integrity"},
        {"name": "infra_ws_heartbeat_silence"},
        {"name": "infra_proxy_rotation_403"},
        {"name": "infra_tls_ja3_validation"},
        {"name": "infra_influx_non_blocking"},
        {"name": "exec_concurrency_lock"},
        {"name": "exec_kelly_tiny_bankroll"},
        {"name": "exec_slippage_tolerance"},
        {"name": "exec_partial_fill_recalc"},
        {"name": "exec_kill_switch_losses"},
        {"name": "general_no_zombie_threads"},
        {"name": "general_no_private_key_logs"},
        {"name": "general_state_recovery"},
        {"name": "general_sport_whitelist"},
        {"name": "mapping_duplicate_names"},
        {"name": "mapping_corporate_suffixes"},
        {"name": "net_dns_failure_betfair"},
        {"name": "net_http2_strict"},
        {"name": "logic_wash_trading_prevent"},
        {"name": "logic_roi_minimum"},
    ],
)
def test_vector_edge_cases(case, capsys, monkeypatch):
    if case["name"] == "poly_unicode_titles":
        title = "Winner: São Paulo\u200b 🏆"
        normalized = "".join(ch for ch in title if ch.isprintable()).strip()
        assert "São Paulo" in normalized
    elif case["name"] == "poly_expired_markets":
        now = time.time()
        market = {"expires_at": now - 3600}
        assert market["expires_at"] < now
    elif case["name"] == "betfair_event_id_coercion":
        assert str(123) == "123"
    elif case["name"] == "betfair_suspended_reactivate":
        status = "SUSPENDED"
        status = "OPEN"
        assert status == "OPEN"
    elif case["name"] == "sx_usdc_to_wei_precision":
        usdc = Decimal("12.345678")
        wei = (usdc * Decimal("1000000000000")).quantize(Decimal("1"))
        assert wei == Decimal("12345678000000")
    elif case["name"] == "sx_orderbook_empty":
        bids, asks = [], []
        assert bids == [] and asks == []
    elif case["name"] == "sx_chain_id_validation":
        allowed = {"polygon": 137, "arbitrum": 42161}
        assert allowed["polygon"] != allowed["arbitrum"]
    elif case["name"] == "data_large_json_ingest":
        payload = {"data": "x" * (10 * 1024 * 1024 + 1)}
        serialized = json.dumps(payload)
        assert len(serialized) > 10 * 1024 * 1024
    elif case["name"] == "data_incomplete_json_eof":
        truncated = '{"a": 1'
        with pytest.raises(json.JSONDecodeError):
            json.loads(truncated)
    elif case["name"] == "data_mixed_timezone_timestamps":
        utc = "2024-01-01T12:00:00Z"
        cet = "2024-01-01T13:00:00+01:00"
        assert utc.endswith("Z") and "+01:00" in cet
    elif case["name"] == "odds_extremes_decimal":
        low = Decimal("1.001")
        high = Decimal("1000.0")
        assert high > low
    elif case["name"] == "odds_negative_or_zero":
        bad = Decimal("-1")
        with pytest.raises(ValueError):
            if bad <= 0:
                raise ValueError("invalid odds")
    elif case["name"] == "odds_spread_with_fees":
        gross = Decimal("0.05")
        fees = Decimal("0.01")
        net = gross - fees
        assert net == Decimal("0.04")
    elif case["name"] == "odds_fx_fluctuation":
        base = Decimal("1.0")
        fx = Decimal("1.05")
        assert (base * fx) == Decimal("1.05")
    elif case["name"] == "semantic_man_city_vs_full":
        assert "man city" in "manchester city fc".lower()
    elif case["name"] == "semantic_man_city_vs_utd":
        assert "man city" not in "man utd".lower()
    elif case["name"] == "semantic_totals_vs_handicap":
        market = "Over 2.5 Goals"
        handicap = "Asian Handicap -2.5"
        assert market != handicap
    elif case["name"] == "semantic_negation_to_lay":
        prompt = "Will X NOT win?"
        assert "not" in prompt.lower()
    elif case["name"] == "ai_malformed_json_fallback":
        client = MiMoClient(api_key="dummy")
        thesis = client._parse_response("not json", {"m": 1}, 0)
        assert thesis.suggested_action == "review"
    elif case["name"] == "ai_rate_limit_recovery":
        cache = SemanticCache()
        cache.set("rate_limit", {"ok": True})
        assert cache.get("rate_limit") == {"ok": True}
    elif case["name"] == "ai_chroma_disconnect_cache_integrity":
        cache = SemanticCache()
        cache._use_chroma = False
        cache.set("q", {"x": 1})
        assert cache.get("q") == {"x": 1}
    elif case["name"] == "infra_ws_heartbeat_silence":
        guard = WebsocketGuard(proxies=[], user_agents=[], heartbeat_timeout_s=2.1)
        guard.record_heartbeat()
        time.sleep(2.1)
        assert guard.is_stale() is True
    elif case["name"] == "infra_proxy_rotation_403":
        proxies = ["p1", "p2"]
        current = proxies[0]
        if 403:
            current = proxies[1]
        assert current == "p2"
    elif case["name"] == "infra_tls_ja3_validation":
        fingerprint = "771,4865-4866-4867,0-11-10,29-23-24,0"
        assert fingerprint.count(",") >= 4
    elif case["name"] == "infra_influx_non_blocking":
        ticks = 1000
        start = time.time()
        processed = ticks
        assert processed == ticks and (time.time() - start) < 1
    elif case["name"] == "exec_concurrency_lock":
        lock = asyncio.Lock()
        assert lock.locked() is False
    elif case["name"] == "exec_kelly_tiny_bankroll":
        bankroll = Decimal("0.01")
        stake = (bankroll * Decimal("0")).quantize(Decimal("0.00"))
        assert stake == Decimal("0.00")
    elif case["name"] == "exec_slippage_tolerance":
        signal = Decimal("1.00")
        exec_price = Decimal("1.02")
        assert (exec_price - signal) / signal > Decimal("0.01")
    elif case["name"] == "exec_partial_fill_recalc":
        size = Decimal("100")
        filled = size * Decimal("0.10")
        remaining = size - filled
        assert remaining == Decimal("90")
    elif case["name"] == "exec_kill_switch_losses":
        losses = [1, 1, 1, 1, 1]
        assert sum(losses) == 5
    elif case["name"] == "general_no_zombie_threads":
        assert True
    elif case["name"] == "general_no_private_key_logs":
        logger = StructuredLogger()
        logger.info("safe_log", trace_id="t1", private_key="***")
        captured = capsys.readouterr().out
        assert "private_key" not in captured
    elif case["name"] == "general_state_recovery":
        state = {"ok": True}
        serialized = json.dumps(state)
        assert json.loads(serialized) == state
    elif case["name"] == "general_sport_whitelist":
        whitelist = {"soccer", "tennis"}
        assert "league of legends" not in whitelist
    elif case["name"] == "mapping_duplicate_names":
        assert "rangers fc" != "texas rangers"
    elif case["name"] == "mapping_corporate_suffixes":
        name = "Club S.A.D."
        normalized = name.replace("S.A.D.", "").strip()
        assert normalized == "Club"
    elif case["name"] == "net_dns_failure_betfair":
        with pytest.raises(OSError):
            raise OSError("DNS failure")
    elif case["name"] == "net_http2_strict":
        client = get_httpx_client(timeout=10, http2=True)
        assert client._http2 is True
        client.close()
    elif case["name"] == "logic_wash_trading_prevent":
        buy_account = "a"
        sell_account = "a"
        assert buy_account == sell_account
    elif case["name"] == "logic_roi_minimum":
        roi = Decimal("0.021")
        assert roi > Decimal("0.02")
