import time
from typing import List, Dict, Optional


class WebsocketGuard:
    """
    Minimal guard for websocket reconnections and proxy rotation.
    """

    def __init__(self, proxies: List[str], user_agents: List[str], heartbeat_timeout_s: float = 10.0):
        self.proxies = proxies
        self.user_agents = user_agents
        self.heartbeat_timeout_s = heartbeat_timeout_s
        self._last_heartbeat: Optional[float] = None
        self._index = 0

    def record_heartbeat(self) -> None:
        self._last_heartbeat = time.monotonic()

    def is_stale(self) -> bool:
        if self._last_heartbeat is None:
            return True
        return (time.monotonic() - self._last_heartbeat) > self.heartbeat_timeout_s

    def next_profile(self) -> Dict[str, str]:
        if not self.proxies:
            proxy = ""
        else:
            proxy = self.proxies[self._index % len(self.proxies)]
        if not self.user_agents:
            user_agent = ""
        else:
            user_agent = self.user_agents[self._index % len(self.user_agents)]
        self._index += 1
        return {"proxy": proxy, "user_agent": user_agent}
