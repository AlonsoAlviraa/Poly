import time
from decimal import Decimal

from src.execution.smart_router import SmartRouter
from src.data.entity_resolution import EntityResolver
from src.utils.ws_guard import WebsocketGuard
from src.utils.feed_health import FeedHealthMonitor
from src.utils.tick_buffer import TickBuffer


class DummyExecutor:
    def place_order(self, token_id, side, limit_price, size):
        return {"order_id": "dummy", "status": "filled", "executed_price": limit_price}


def test_decimal_json_parsing_is_exact():
    payload = '{"price": 0.1, "fee": 0.2}'
    data = SmartRouter.parse_ws_payload(payload)
    assert isinstance(data["price"], Decimal)
    assert data["price"] + data["fee"] == Decimal("0.3")


def test_entity_resolver_normalizes_alias():
    resolver = EntityResolver()
    assert resolver.resolve("Man City") == "Manchester City"


def test_tick_to_decision_latency_under_threshold():
    router = SmartRouter(executor_client=DummyExecutor())
    start = time.perf_counter()
    router.calculate_kelly_size(
        bankroll=1000.0,
        edge_pct=2.0,
        win_prob=0.6,
        liquidity_limit=10000,
        min_bet=1.0
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 50


def test_websocket_guard_rotates_proxy_and_heartbeat():
    guard = WebsocketGuard(
        proxies=["ip1", "ip2"],
        user_agents=["ua1", "ua2"],
        heartbeat_timeout_s=0.01
    )
    guard.record_heartbeat()
    profile1 = guard.next_profile()
    profile2 = guard.next_profile()
    assert profile1["proxy"] != profile2["proxy"]
    time.sleep(0.02)
    assert guard.is_stale() is True


def test_feed_health_monitor_pauses_on_asym_disconnect():
    monitor = FeedHealthMonitor(max_stale_s=0.01)
    monitor.update_feed("polymarket")
    time.sleep(0.02)
    assert monitor.is_healthy() is False


def test_tick_buffer_bounds_memory():
    buffer = TickBuffer(maxlen=100)
    for i in range(500):
        buffer.push(i)
    assert len(buffer) == 100
    assert buffer.dropped == 400
