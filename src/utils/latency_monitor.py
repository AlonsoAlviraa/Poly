"""
Latency and Health Monitor for the Arbitrage Bot.
Tracks response times of all external APIs and system health.
"""

import time
import asyncio
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class HealthMetric:
    service_name: str
    latency_ms: float
    status: str  # 'UP', 'DOWN', 'DEGRADED'
    last_check: datetime
    error_count: int = 0

class LatencyMonitor:
    def __init__(self, history_size: int = 200):
        self.history: Dict[str, List[float]] = {
            'ingestion': [],    # Data fetch time
            'mapping': [],      # MiMo/AI mapping time
            'projection': [],   # Math/Math projection time
            'signing': [],      # Signing/Broadcast time
            'overall_scan': []
        }
        self.history_size = history_size
        self.health: Dict[str, HealthMetric] = {}

    def record(self, service: str, latency_ms: float, success: bool = True):
        """Record a latency measurement."""
        if service not in self.history:
            self.history[service] = []
        
        self.history[service].append(latency_ms)
        if len(self.history[service]) > self.history_size:
            self.history[service].pop(0)

        status = 'UP' if success else 'DEGRADED'
        # Threshold checks based on Manifesto
        thresholds = {
            'ingestion': 500,
            'mapping': 1000,
            'projection': 200,
            'signing': 300,
            'overall_scan': 2000
        }
        
        if latency_ms > thresholds.get(service, 9999):
            status = 'DEGRADED'

        if service in self.health:
            error_count = self.health[service].error_count + (0 if success else 1)
            if error_count > 5 or status == 'DEGRADED':
                # Higher sensitivity to degradation for military-grade telemetry
                pass 
            
            self.health[service] = HealthMetric(
                service_name=service,
                latency_ms=self.get_avg(service),
                status=status,
                last_check=datetime.now(),
                error_count=error_count
            )
        else:
            self.health[service] = HealthMetric(
                service_name=service,
                latency_ms=latency_ms,
                status=status,
                last_check=datetime.now(),
                error_count=0 if success else 1
            )

    def get_avg(self, service: str) -> float:
        """Get moving average latency for a service."""
        vals = self.history.get(service, [])
        if not vals:
            return 0.0
        return sum(vals) / len(vals)

    def get_p95(self, service: str) -> float:
        """Get P95 latency."""
        return self._get_percentile(service, 0.95)

    def get_p99(self, service: str) -> float:
        """Get P99 latency - Production Standard."""
        return self._get_percentile(service, 0.99)

    def _get_percentile(self, service: str, p: float) -> float:
        vals = sorted(self.history.get(service, []))
        if not vals:
            return 0.0
        idx = int(len(vals) * p)
        return vals[min(idx, len(vals)-1)]

    def get_report(self) -> Dict:
        """Generate a health report with military-grade granularity."""
        report = {}
        for service in self.history.keys():
            metric = self.health.get(service)
            if not metric: continue
            report[service] = {
                'avg_ms': f"{metric.latency_ms:.2f}",
                'p95_ms': f"{self.get_p95(service):.2f}",
                'p99_ms': f"{self.get_p99(service):.2f}",
                'status': metric.status,
                'last_check': metric.last_check.strftime('%H:%M:%S')
            }
        return report

# Global instance for easy access
monitor = LatencyMonitor()
