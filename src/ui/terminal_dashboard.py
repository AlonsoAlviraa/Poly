from datetime import datetime
from typing import List, Dict, Optional

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.layout import Layout


class TerminalDashboard:
    """
    Real-time TUI dashboard using Rich.
    Shows balance, P&L, exposure, open positions, and recent events.
    """

    def __init__(self):
        self.console = Console()
        self.live: Optional[Live] = None
        self.balance = 0.0
        self.pnl_daily = 0.0
        self.exposure = 0.0
        self.positions: List[Dict] = []
        self.events: List[str] = []
        self.websocket_status = "unknown"

    def start(self) -> None:
        if self.live:
            return
        self.live = Live(self._render_layout(), console=self.console, refresh_per_second=4)
        self.live.start()

    def stop(self) -> None:
        if self.live:
            self.live.stop()
            self.live = None

    def update_summary(self, balance: float, pnl_daily: float, exposure: float) -> None:
        self.balance = balance
        self.pnl_daily = pnl_daily
        self.exposure = exposure
        self._refresh()

    def update_positions(self, positions: List[Dict]) -> None:
        self.positions = positions
        self._refresh()

    def update_events(self, events: List[str]) -> None:
        self.events = events[-5:]
        self._refresh()

    def update_websocket_status(self, status: str) -> None:
        self.websocket_status = status
        self._refresh()

    def _refresh(self) -> None:
        if self.live:
            self.live.update(self._render_layout())

    def _render_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(self._render_summary(), size=6),
            Layout(self._render_positions(), ratio=2),
            Layout(self._render_events(), size=8)
        )
        return layout

    def _render_summary(self) -> Table:
        table = Table(title="⚡ Command Center")
        table.add_column("Balance", justify="right")
        table.add_column("P&L Diario", justify="right")
        table.add_column("Exposición", justify="right")
        table.add_column("WS", justify="center")

        table.add_row(
            f"${self.balance:,.2f}",
            f"${self.pnl_daily:,.2f}",
            f"${self.exposure:,.2f}",
            self.websocket_status
        )
        return table

    def _render_positions(self) -> Table:
        table = Table(title="📌 Posiciones Abiertas")
        table.add_column("Evento")
        table.add_column("Tamaño", justify="right")
        table.add_column("P&L", justify="right")
        table.add_column("Tiempo", justify="right")

        if not self.positions:
            table.add_row("—", "—", "—", "—")
            return table

        now = datetime.utcnow()
        for pos in self.positions:
            opened = pos.get("opened_at", now)
            elapsed = (now - opened).total_seconds()
            table.add_row(
                pos.get("event", "Unknown"),
                f"${pos.get('size', 0):.2f}",
                f"${pos.get('pnl', 0):.2f}",
                f"{elapsed:.0f}s"
            )
        return table

    def _render_events(self) -> Table:
        table = Table(title="🧾 Últimos Eventos")
        table.add_column("Evento")
        for event in self.events[-5:]:
            table.add_row(event)
        return table
