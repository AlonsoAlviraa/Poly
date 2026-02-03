import pytest

from src.risk.risk_guardian import RiskGuardian


class DummyNotifier:
    def __init__(self):
        self.alerts = []

    def send_alert(self, message: str) -> None:
        self.alerts.append(message)


def test_risk_guardian_consecutive_losses_triggers_pause_and_alert():
    notifier = DummyNotifier()
    guardian = RiskGuardian(initial_balance=1000.0, max_consecutive_losers=5, notifier=notifier)
    for _ in range(6):
        guardian.record_trade(-10.0)
    assert guardian.pause_until is not None
    assert any("pérdidas consecutivas" in alert.lower() for alert in notifier.alerts)


def test_risk_guardian_drawdown_trips_kill_switch():
    notifier = DummyNotifier()
    guardian = RiskGuardian(initial_balance=1000.0, max_drawdown_pct=0.1, notifier=notifier, kill_on_drawdown=True)
    with pytest.raises(SystemExit):
        guardian.record_trade(-150.0)
