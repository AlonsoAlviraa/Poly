
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from influxdb_client import InfluxDBClient, Point, WritePrecision, WriteOptions
    INFLUX_AVAILABLE = True
except ImportError:
    INFLUX_AVAILABLE = False

logger = logging.getLogger(__name__)

class PriceTickerLogger:
    """
    Logs every price change (tick) to InfluxDB for future backtesting.
    "Lo que no es tiempo real, es historia antigua."
    """
    
    def __init__(self):
        self.url = os.getenv('INFLUXDB_URL', 'http://localhost:8086')
        self.token = os.getenv('INFLUXDB_TOKEN')
        self.org = os.getenv('INFLUXDB_ORG', 'apu_trading')
        self.bucket = os.getenv('INFLUXDB_BUCKET', 'market_ticks')
        
        self.client = None
        self.write_api = None
        
        if INFLUX_AVAILABLE and self.token:
            try:
                self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
                # Use batching and background threads for Task 2
                self.write_api = self.client.write_api(
                    write_options=WriteOptions(
                        batch_size=500,
                        flush_interval=1000,
                        jitter_interval=2000,
                        retry_interval=5000,
                        max_retries=5,
                        max_retry_delay=30000,
                        exponential_base=2
                    )
                )
                logger.info(f"[InfluxDB] Connected to {self.url} (Async/Batch mode)")
            except Exception as e:
                logger.error(f"[InfluxDB] Connection error: {e}")
        else:
            if not self.token:
                logger.warning("[InfluxDB] No token found in .env. Logging to DB disabled.")
            else:
                logger.warning("[InfluxDB] influxdb-client not installed. Logging to DB disabled.")

    def log_tick(self, 
                 platform: str, 
                 market_id: str, 
                 price: float, 
                 size: float, 
                 side: str,
                 runner_name: Optional[str] = None):
        """Record a single price tick."""
        if not self.write_api:
            return
            
        try:
            point = Point("tick") \
                .tag("platform", platform) \
                .tag("market_id", market_id) \
                .tag("side", side) \
                .field("price", float(price)) \
                .field("size", float(size)) \
                .time(datetime.utcnow(), WritePrecision.NS)
            
            if runner_name:
                point.tag("runner", runner_name)
                
            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            
        except Exception as e:
            logger.error(f"[InfluxDB] Write error: {e}")

    def close(self):
        if self.client:
            self.client.close()

# Singleton instance
ticker_logger = PriceTickerLogger()
