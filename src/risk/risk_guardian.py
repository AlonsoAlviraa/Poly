import logging
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
        api_error_window_s: int = 60
    ):
        self.initial_balance = initial_balance
        self.max_drawdown_pct = max_drawdown_pct
        self.max_consecutive_losers = max_consecutive_losers
        self.pause_minutes = pause_minutes
        self.api_error_limit = api_error_limit
        self.api_error_window_s = api_error_window_s

        self.current_balance = initial_balance
        self.consecutive_losers = 0
        self.pause_until: Optional[datetime] = None
        self.api_errors: Deque[datetime] = deque()

    def update_balance(self, balance: float) -> None:
        self.current_balance = balance

    def record_trade(self, pnl: float) -> None:
        self.current_balance += pnl
        if pnl < 0:
            self.consecutive_losers += 1
        else:
            self.consecutive_losers = 0
        self._check_drawdown()
        self._check_consecutive_losses()

    def record_api_error(self) -> None:
        now = datetime.now(timezone.utc)
        self.api_errors.append(now)
        self._trim_api_errors(now)

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

    def _check_consecutive_losses(self) -> None:
        if self.consecutive_losers >= self.max_consecutive_losers:
            self.pause_until = datetime.now(timezone.utc) + timedelta(minutes=self.pause_minutes)
            logger.critical("RiskGuardian triggered consecutive losses kill switch.")

    def _trim_api_errors(self, now: datetime) -> None:
        while self.api_errors and (now - self.api_errors[0]).total_seconds() > self.api_error_window_s:
            self.api_errors.popleft()
