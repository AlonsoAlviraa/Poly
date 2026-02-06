
import time
from datetime import datetime
from collections import deque
from typing import Dict, List, Optional

from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Console
from rich import box

class ArbitrageDashboard:
    """
    TUI Dashboard for Arbitrage Bot.
    Uses 'rich' library to display real-time stats without blocking.
    """
    def __init__(self):
        self.console = Console()
        self.layout = Layout()
        
        # Data Stores
        self.opportunities = deque(maxlen=15) # Keep last 15
        self.stats = {
            'cycle_count': 0,
            'poly_markets': 0,
            'bf_events': 0,
            'matches_found': 0,
            'errors': 0,
            'uptime': str(datetime.now().strftime("%H:%M:%S")),
            'last_update': 0
        }
        self.latencies = {
            'polymarket': 0,
            'betfair': 0
        }
        
        # Init Layout
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        # Split main into Feed and Side Panel
        self.layout["main"].split_row(
            Layout(name="feed", ratio=3),
            Layout(name="sidebar", ratio=1)
        )

    def update_cycle(self, cycle_num: int, n_poly: int, n_bf: int):
        self.stats['cycle_count'] = cycle_num
        self.stats['poly_markets'] = n_poly
        self.stats['bf_events'] = n_bf
        self.stats['last_update'] = time.time()

    def update_latency(self, source: str, ms: float):
        self.latencies[source] = ms

    def add_opportunity(self, opp_data: Dict):
        """
        opp_data: {
            'event': str,
            'market': str, 
            'poly_price': float,
            'bf_back': float,
            'bf_lay': float,
            'ev': float,
            'roi': float,
            'source': str (BF/SX)
        }
        """
        self.opportunities.appendleft(opp_data) # Newest first
        self.stats['matches_found'] += 1

    def _generate_header(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="right", ratio=1)
        
        title = Text("🚀 SHADOW BOT CONTROL ROOM", style="bold magenta")
        status = Text(f"Cycle: #{self.stats['cycle_count']} | Active", style="bold green")
        
        grid.add_row(title, status)
        return Panel(grid, style="white on blue")

    def _generate_feed(self) -> Panel:
        table = Table(box=box.SIMPLE_HEAD, expand=True)
        table.add_column("Time", style="dim", width=10)
        table.add_column("Event", style="bold white", ratio=2)
        table.add_column("Poly", justify="right")
        table.add_column("Exch (B/L)", justify="right")
        table.add_column("EV (€)", justify="right")
        table.add_column("ROI", justify="right")
        
        for opp in self.opportunities:
            ts = datetime.now().strftime("%H:%M:%S") # Simplified, ideally pass TS
            
            # Color logic
            roi = opp.get('roi', 0)
            color = "green" if roi > 2 else "yellow" if roi > 0 else "red"
            
            ev_str = f"{opp.get('ev',0):.2f}"
            roi_str = f"{roi:.1f}%"
            
            poly_p = f"{opp.get('poly_price',0):.3f}"
            bf_str = f"{opp.get('bf_back',0):.2f}/{opp.get('bf_lay',0):.2f}"
            
            table.add_row(
                ts,
                opp.get('event', '?'),
                poly_p,
                bf_str,
                f"[{color}]{ev_str}[/{color}]",
                f"[{color}]{roi_str}[/{color}]"
            )
            
        return Panel(table, title="📡 Live Opportunities Feed", border_style="blue")

    def _generate_sidebar(self) -> Panel:
        table = Table.grid(expand=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="white")
        
        table.add_row("Poly Latency", f"{self.latencies['polymarket']:.0f}ms")
        table.add_row("BF Latency", f"{self.latencies['betfair']:.0f}ms")
        table.add_row("---", "---")
        table.add_row("Poly Mkts", str(self.stats['poly_markets']))
        table.add_row("BF Events", str(self.stats['bf_events']))
        table.add_row("---", "---")
        table.add_row("Total Matches", str(self.stats['matches_found']))
        table.add_row("Errors", f"[red]{self.stats['errors']}[/red]")
        
        return Panel(table, title="📊 Health", border_style="cyan")

    def render(self) -> Layout:
        self.layout["header"].update(self._generate_header())
        self.layout["feed"].update(self._generate_feed())
        self.layout["sidebar"].update(self._generate_sidebar())
        return self.layout

    def run(self):
        """
        Run the dashboard in a context manager.
        """
        return Live(self.render(), refresh_per_second=4, screen=True)
