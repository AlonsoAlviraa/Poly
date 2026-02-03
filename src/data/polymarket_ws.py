import os


def get_polymarket_ws_url() -> str:
    return os.getenv("POLY_WS_URL", "wss://ws-subscriptions-clob.polymarket.com/ws/market")
