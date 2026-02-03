import json
import logging
import os
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Deque, Optional

logger = logging.getLogger(__name__)


class RiskGuardian:
    """
    Global risk guardian with kill switches:
    - Max drawdown in 24h
    - Consecutive losers
    - API error rate burst
    """

    def __init__(
        self,
        initial_balance: float,
        max_drawdown_pct: float = 0.05,
        max_consecutive_losers: int = 5,
        pause_minutes: int = 60,
        api_error_limit: int = 10,
        api_error_window_s: int = 60,
        notifier: Optional[object] = None,
        kill_on_drawdown: bool = False,
        state_file: str = "risk_guardian_state.json"
    ):
        self.initial_balance = initial_balance
        self.max_drawdown_pct = max_drawdown_pct
        self.max_consecutive_losers = max_consecutive_losers
        self.pause_minutes = pause_minutes
        self.api_error_limit = api_error_limit
        self.api_error_window_s = api_error_window_s
        self.notifier = notifier
        self.kill_on_drawdown = kill_on_drawdown
        self.state_file = state_file

        self.current_balance = initial_balance
        self.consecutive_losers = 0
        self.pause_until: Optional[datetime] = None
        self.api_errors: Deque[datetime] = deque()
        self._load_state()

    def update_balance(self, balance: float) -> None:
        self.current_balance = balance
        self._save_state()

    def record_trade(self, pnl: float) -> None:
        self.current_balance += pnl
        if pnl < 0:
            self.consecutive_losers += 1
        else:
            self.consecutive_losers = 0
        self._check_drawdown()
        self._check_consecutive_losses()
        self._save_state()

    def record_api_error(self) -> None:
        now = datetime.now(timezone.utc)
        self.api_errors.append(now)
        self._trim_api_errors(now)
        self._save_state()

    def can_trade(self) -> bool:
        now = datetime.now(timezone.utc)
        if self.pause_until and now < self.pause_until:
            logger.warning("RiskGuardian pause active.")
            return False
        if self._drawdown_pct() > self.max_drawdown_pct:
            logger.critical("RiskGuardian drawdown limit reached.")
            return False
        if self.consecutive_losers >= self.max_consecutive_losers:
            logger.critical("RiskGuardian consecutive loser limit reached.")
            return False
        if len(self.api_errors) >= self.api_error_limit:
            logger.critical("RiskGuardian API error rate limit reached.")
            return False
        return True

    def _drawdown_pct(self) -> float:
        if self.initial_balance <= 0:
            return 0.0
        loss = max(self.initial_balance - self.current_balance, 0.0)
        return loss / self.initial_balance

    def _check_drawdown(self) -> None:
        if self._drawdown_pct() > self.max_drawdown_pct:
            self.pause_until = datetime.now(timezone.utc) + timedelta(minutes=self.pause_minutes)
            logger.critical("RiskGuardian triggered drawdown kill switch.")
            if self.notifier:
                self.notifier.send_alert("Kill Switch: Drawdown diario excedido.")
            if self.kill_on_drawdown:
                raise SystemExit("Drawdown limit reached.")

    def _check_consecutive_losses(self) -> None:
        if self.consecutive_losers >= self.max_consecutive_losers:
            self.pause_until = datetime.now(timezone.utc) + timedelta(minutes=self.pause_minutes)
            logger.critical("RiskGuardian triggered consecutive losses kill switch.")
            if self.notifier:
                self.notifier.send_alert("Kill Switch: pérdidas consecutivas detectadas.")

    def _trim_api_errors(self, now: datetime) -> None:
        while self.api_errors and (now - self.api_errors[0]).total_seconds() > self.api_error_window_s:
            self.api_errors.popleft()

    def _load_state(self) -> None:
        if not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self.current_balance = data.get("current_balance", self.current_balance)
            self.consecutive_losers = data.get("consecutive_losers", self.consecutive_losers)
            pause_until = data.get("pause_until")
            if pause_until:
                self.pause_until = datetime.fromisoformat(pause_until)
            self.api_errors = deque(
                datetime.fromisoformat(ts) for ts in data.get("api_errors", [])
            )
        except (json.JSONDecodeError, OSError, ValueError):
            logger.warning("Failed to load RiskGuardian state; starting fresh.")

    def _save_state(self) -> None:
        data = {
            "current_balance": self.current_balance,
            "consecutive_losers": self.consecutive_losers,
            "pause_until": self.pause_until.isoformat() if self.pause_until else None,
            "api_errors": [ts.isoformat() for ts in self.api_errors]
        }
        try:
            with open(self.state_file, "w", encoding="utf-8") as handle:
                json.dump(data, handle)
        except OSError:
            logger.warning("Failed to persist RiskGuardian state.")
