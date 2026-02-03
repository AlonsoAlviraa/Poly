from prometheus_client import start_http_server, Gauge, Counter, Histogram
import time
import logging
import socket

logger = logging.getLogger(__name__)

class MetricsServer:
    """
    Exposes Prometheus metrics for Grafana visualization.
    Singleton pattern usage recommended.
    """
    
    def __init__(self, port: int = 8000):
        self.port = port
        self._server_started = False
        
        # Metrics Definitions
        self.latency_histogram = Histogram(
            'trade_execution_latency_seconds',
            'Time from detection to transaction submission',
            buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0]
        )
        
        self.fill_rate_counter = Counter(
            'trade_fill_total',
            'Total trades executed',
            ['status']
        )
        
        self.pnl_gauge = Gauge(
            'net_profit_accumulated_usd',
            'Accumulated Net Profit (PnL) in USD'
        )
        
        self.arb_opportunities_gauge = Gauge(
            'active_arbitrage_opportunities',
            'Number of currently detected opportunities'
        )
        
        self.arb_drift_gauge = Gauge(
            'arbitrage_drift_usd',
            'Difference between Target Price (Bregman) and Execution Price'
        )
        
        self.gas_spent_counter = Counter(
            'gas_spent_usd_total',
            'Total estimated gas fees spent in USD'
        )
        
        self.recovery_counter = Counter(
            'recovery_events_total',
            'Number of times RecoveryHandler was triggered'
        )
        
    def _is_port_in_use(self) -> bool:
        """Check if port is already bound."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', self.port)) == 0
        
    def start(self):
        """Start Prometheus HTTP server with collision handling."""
        if self._server_started:
            logger.info(f"📊 Metrics Server already running on port {self.port}")
            return
            
        if self._is_port_in_use():
            logger.warning(f"⚠️ Port {self.port} already in use. Assuming metrics server is external.")
            self._server_started = True  # Assume external Prometheus
            return
            
        try:
            start_http_server(self.port)
            self._server_started = True
            logger.info(f"📊 Metrics Server exposed at port {self.port}")
        except OSError as e:
            if "Address already in use" in str(e) or "10048" in str(e):
                logger.warning(f"⚠️ Port {self.port} collision. Metrics may be externally available.")
                self._server_started = True
            else:
                logger.error(f"❌ Failed to start Metrics Server: {e}")
                
    def health_check(self) -> bool:
        """Verify metrics endpoint is accessible."""
        return self._is_port_in_use() if self._server_started else False
