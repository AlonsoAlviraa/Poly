import asyncio
import httpx
import logging
import time
from typing import List, Optional, Dict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class RPCNodeStats:
    """Tracks performance metrics for an RPC node."""
    url: str
    latency_samples: List[float] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    last_used: float = 0.0
    
    @property
    def avg_latency(self) -> float:
        if not self.latency_samples:
            return float('inf')
        return sum(self.latency_samples[-10:]) / min(len(self.latency_samples), 10)
    
    @property
    def jitter(self) -> float:
        """Standard deviation of recent latencies."""
        if len(self.latency_samples) < 2:
            return 0.0
        recent = self.latency_samples[-10:]
        mean = sum(recent) / len(recent)
        variance = sum((x - mean) ** 2 for x in recent) / len(recent)
        return variance ** 0.5
    
    @property
    def reliability_score(self) -> float:
        """Combined score: lower is better."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5  # Unknown
        success_rate = self.success_count / total
        return self.avg_latency * (2 - success_rate) + self.jitter * 2

class RPCRacer:
    """
    Submits transactions to multiple RPC providers simultaneously.
    'Racing' approach ensures inclusion even if some nodes are slow/lagging.
    Includes adaptive node selection based on latency and reliability.
    """
    
    def __init__(self, rpc_urls: List[str], jitter_threshold: float = 0.5):
        self.rpc_urls = rpc_urls
        self.jitter_threshold = jitter_threshold
        self.node_stats: Dict[str, RPCNodeStats] = {
            url: RPCNodeStats(url=url) for url in rpc_urls
        }
        if not self.rpc_urls:
            logger.warning("No RPC URLs provided to RPCRacer.")

    def get_ranked_nodes(self) -> List[str]:
        """Returns RPC URLs sorted by reliability score (best first)."""
        active_nodes = [
            (url, stats) for url, stats in self.node_stats.items()
            if stats.jitter < self.jitter_threshold or stats.failure_count < 3
        ]
        if not active_nodes:
            # Fallback: use all nodes
            active_nodes = list(self.node_stats.items())
        
        sorted_nodes = sorted(active_nodes, key=lambda x: x[1].reliability_score)
        return [url for url, _ in sorted_nodes]

    async def _send_to_rpc(self, url: str, raw_tx_hex: str) -> Optional[str]:
        """
        Sends raw transaction to a single RPC.
        Returns tx_hash on success, None on failure.
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_sendRawTransaction",
            "params": [raw_tx_hex],
            "id": 1
        }
        
        stats = self.node_stats.get(url)
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.post(url, json=payload)
                data = resp.json()
                
                latency = time.time() - start_time
                
                if stats:
                    stats.latency_samples.append(latency)
                    stats.last_used = time.time()
                
                if "result" in data:
                    if stats:
                        stats.success_count += 1
                    logger.debug(f"RPC {url} accepted tx: {data['result']} (latency: {latency:.3f}s)")
                    return data["result"]
                elif "error" in data:
                    if stats:
                        stats.failure_count += 1
                    logger.debug(f"RPC {url} error: {data['error']}")
                    return None
                    
        except Exception as e:
            if stats:
                stats.failure_count += 1
            logger.debug(f"RPC {url} connection failed: {e}")
            return None
        return None

    async def broadcast_tx_racing(self, raw_tx_hex: str) -> Optional[str]:
        """
        Broadcasts tx to ALL configured RPCs in parallel.
        Returns the first valid TX Hash received.
        Uses adaptive node ranking for optimal propagation.
        """
        ranked_urls = self.get_ranked_nodes()
        logger.debug(f"Racing across {len(ranked_urls)} nodes")
        
        tasks = [self._send_to_rpc(url, raw_tx_hex) for url in ranked_urls]
        pending = [asyncio.create_task(t) for t in tasks]
        
        valid_hash = None
        
        try:
            for coro in asyncio.as_completed(pending):
                result = await coro
                if result and not valid_hash:
                    valid_hash = result
                    logger.info(f"⚡ Tx accepted by network! Hash: {valid_hash}")
                    return valid_hash
                    
        except Exception as e:
            logger.error(f"Race Exception: {e}")
            
        return valid_hash
    
    async def health_check(self) -> Dict[str, Dict]:
        """
        Performs health check on all RPC nodes.
        Returns status for each node.
        """
        results = {}
        
        for url, stats in self.node_stats.items():
            results[url] = {
                "avg_latency": stats.avg_latency,
                "jitter": stats.jitter,
                "success_rate": stats.success_count / max(1, stats.success_count + stats.failure_count),
                "score": stats.reliability_score,
                "healthy": stats.jitter < self.jitter_threshold
            }
            
        return results
