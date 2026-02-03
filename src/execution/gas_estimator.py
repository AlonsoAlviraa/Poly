import httpx
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class GasEstimator:
    """
    Predicts optimal Gas parameters for Polygon (EIP-1559).
    Aims for 'Next Block' inclusion by analyzing priority fee percentiles.
    Supports multiple data sources for reliability.
    """
    
    def __init__(self, 
                 gas_station_url: str = "https://gasstation.polygon.technology/v2",
                 rpc_url: Optional[str] = None,
                 gas_multiplier: float = 1.1):
        """
        Args:
            gas_station_url: Polygon Gas Station API.
            rpc_url: Optional RPC for direct block data.
            gas_multiplier: Safety multiplier for priority fee.
        """
        self.gas_station_url = gas_station_url
        self.rpc_url = rpc_url
        self.multiplier = gas_multiplier
        
        # Cache recent base fees for trend analysis
        self.base_fee_history: list = []
        self.max_history_size = 10

    async def get_optimal_gas(self) -> Dict:
        """
        Fetches gas predictions from multiple sources.
        Returns dict with 'maxFeePerGas' and 'maxPriorityFeePerGas' (in Wei).
        """
        # Try RPC first for fresh data
        if self.rpc_url:
            try:
                rpc_result = await self._get_gas_from_rpc()
                if rpc_result:
                    return rpc_result
            except Exception as e:
                logger.debug(f"RPC gas fetch failed: {e}")
        
        # Fallback to Gas Station
        try:
            return await self._get_gas_from_station()
        except Exception as e:
            logger.warning(f"Gas Station failed ({e}). Using Safe Fallback.")
            return self._get_fallback_gas()
    
    async def _get_gas_from_rpc(self) -> Optional[Dict]:
        """Fetch gas params directly from RPC node."""
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_feeHistory",
            "params": ["0x5", "latest", [25, 50, 75]],  # Last 5 blocks, percentiles
            "id": 1
        }
        
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.post(self.rpc_url, json=payload)
            data = resp.json()
            
            if "result" not in data:
                return None
                
            result = data["result"]
            base_fees = result.get("baseFeePerGas", [])
            reward_percentiles = result.get("reward", [])
            
            if not base_fees or not reward_percentiles:
                return None
            
            # Latest base fee (hex to int)
            latest_base = int(base_fees[-1], 16)
            self._update_base_fee_history(latest_base)
            
            # Calculate trend-adjusted base fee
            predicted_base = self._predict_next_base_fee(latest_base)
            
            # Get median priority fee (50th percentile of last block)
            if reward_percentiles and len(reward_percentiles[-1]) >= 2:
                median_priority = int(reward_percentiles[-1][1], 16)
            else:
                median_priority = int(30 * 1e9)  # 30 Gwei default
            
            # Apply multiplier for competitive positioning
            priority_fee = int(median_priority * self.multiplier)
            max_fee = predicted_base + priority_fee * 2
            
            return {
                "maxFeePerGas": max_fee,
                "maxPriorityFeePerGas": priority_fee,
                "estimatedBaseFee": predicted_base,
                "source": "rpc"
            }
    
    async def _get_gas_from_station(self) -> Dict:
        """Fetch gas params from Polygon Gas Station API."""
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(self.gas_station_url)
            data = resp.json()
            
            fast = data.get("fast", {})
            max_fee = fast.get("maxFee", 50.0)
            max_prio = fast.get("maxPriorityFee", 30.0)
            estimated_base = data.get("estimatedBaseFee", 0.0)
            
            return {
                "maxFeePerGas": int(max_fee * 1e9 * self.multiplier),
                "maxPriorityFeePerGas": int(max_prio * 1e9 * self.multiplier),
                "estimatedBaseFee": int(estimated_base * 1e9),
                "source": "gas_station"
            }
    
    def _get_fallback_gas(self) -> Dict:
        """Hardcoded safe values for Polygon."""
        return {
            "maxFeePerGas": int(300 * 1e9),
            "maxPriorityFeePerGas": int(50 * 1e9),
            "estimatedBaseFee": int(100 * 1e9),
            "source": "fallback"
        }
    
    def _update_base_fee_history(self, base_fee: int):
        """Maintains sliding window of base fees."""
        self.base_fee_history.append(base_fee)
        if len(self.base_fee_history) > self.max_history_size:
            self.base_fee_history = self.base_fee_history[-self.max_history_size:]
    
    def _predict_next_base_fee(self, current_base: int) -> int:
        """
        Predicts next block's base fee using EIP-1559 formula.
        Base fee can increase or decrease by max 12.5% per block.
        """
        if len(self.base_fee_history) < 2:
            return current_base
        
        # Calculate recent trend
        recent = self.base_fee_history[-3:]
        avg_change = (recent[-1] - recent[0]) / len(recent)
        
        # Predict with dampening
        predicted = current_base + int(avg_change * 0.5)
        
        # Apply 12.5% max change rule
        max_increase = int(current_base * 0.125)
        return min(predicted, current_base + max_increase)
    
    def estimate_tx_cost_usd(self, gas_limit: int = 200000, pol_price_usd: float = 0.5) -> float:
        """
        Estimates transaction cost in USD.
        
        Args:
            gas_limit: Expected gas units for the transaction.
            pol_price_usd: Current MATIC/POL price in USD.
        """
        if not self.base_fee_history:
            base_fee = 100 * 1e9  # 100 Gwei default
        else:
            base_fee = self.base_fee_history[-1]
        
        priority_fee = 30 * 1e9  # 30 Gwei typical
        total_gas_price = base_fee + priority_fee
        
        cost_wei = gas_limit * total_gas_price
        cost_matic = cost_wei / 1e18
        cost_usd = cost_matic * pol_price_usd
        
        return cost_usd
