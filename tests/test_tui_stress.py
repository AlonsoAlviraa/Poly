from src.ui.terminal_dashboard import TerminalDashboard


def test_tui_stress_updates_do_not_block():
    dashboard = TerminalDashboard()
    dashboard.start()
    for i in range(200):
        dashboard.update_events([f"event {i}"])
    dashboard.stop()
