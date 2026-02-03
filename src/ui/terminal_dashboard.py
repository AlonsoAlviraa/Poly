from datetime import datetime
from typing import List, Dict, Optional
import threading
import time

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
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self.live:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def update_summary(self, balance: float, pnl_daily: float, exposure: float) -> None:
        with self._lock:
            self.balance = balance
            self.pnl_daily = pnl_daily
            self.exposure = exposure

    def update_positions(self, positions: List[Dict]) -> None:
        with self._lock:
            self.positions = positions

    def update_events(self, events: List[str]) -> None:
        with self._lock:
            self.events = events[-5:]

    def update_websocket_status(self, status: str) -> None:
        with self._lock:
            self.websocket_status = status

    def _refresh(self) -> None:
        if self.live:
            self.live.update(self._render_layout())

    def _run_loop(self) -> None:
        with Live(self._render_layout(), console=self.console, refresh_per_second=10) as live:
            self.live = live
            while not self._stop_event.is_set():
                self._refresh()
                time.sleep(0.1)
        self.live = None

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

        with self._lock:
            balance = self.balance
            pnl_daily = self.pnl_daily
            exposure = self.exposure
            websocket_status = self.websocket_status
        table.add_row(
            f"${balance:,.2f}",
            f"${pnl_daily:,.2f}",
            f"${exposure:,.2f}",
            websocket_status
        )
        return table

    def _render_positions(self) -> Table:
        table = Table(title="📌 Posiciones Abiertas")
        table.add_column("Evento")
        table.add_column("Tamaño", justify="right")
        table.add_column("P&L", justify="right")
        table.add_column("Tiempo", justify="right")

        with self._lock:
            positions = list(self.positions)

        if not positions:
            table.add_row("—", "—", "—", "—")
            return table

        now = datetime.utcnow()
        for pos in positions:
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
        with self._lock:
            events = list(self.events[-5:])
        for event in events:
            table.add_row(event)
        return table
