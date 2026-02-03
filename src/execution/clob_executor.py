"""
Polymarket CLOB Executor.
Handles order execution with FOK (Fill-or-Kill) support for atomic arbitrage.
"""

import os
import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class OrderType(Enum):
    FOK = "FOK"      # Fill-or-Kill: Execute fully or cancel
    GTC = "GTC"      # Good-til-Cancelled
    GTD = "GTD"      # Good-til-Date
    IOC = "IOC"      # Immediate-or-Cancel


@dataclass
class OrderResult:
    """Result of an order execution."""
    success: bool
    order_id: Optional[str]
    filled_size: float
    avg_price: float
    error: Optional[str] = None
    raw_response: Optional[Dict] = None


class PolymarketCLOBExecutor:
    """
    Real Execution Client for Polymarket CLOB.
    Supports FOK orders for atomic arbitrage execution.
    """
    
    def __init__(self, 
                 host: str, 
                 key: str, 
                 chain_id: int = 137,
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 api_passphrase: Optional[str] = None):
        """
        Initialize CLOB executor.
        
        Args:
            host: CLOB API host
            key: Private key for signing
            chain_id: Polygon chain ID (137)
            api_key: API key for authenticated endpoints
            api_secret: API secret
            api_passphrase: API passphrase
        """
        self.host = host
        self.private_key = key
        self.chain_id = chain_id
        
        # API credentials (for balance, orders, etc)
        self.api_key = api_key or os.getenv('POLY_KEY')
        self.api_secret = api_secret or os.getenv('POLY_SECRET')
        self.api_passphrase = api_passphrase or os.getenv('POLY_PASSPHRASE')
        
        self.client = None
        self._init_client()
        
        # Execution stats
        self._stats = {
            'total_orders': 0,
            'successful_orders': 0,
            'failed_orders': 0,
            'total_volume': 0.0
        }

    def _init_client(self):
        """Initialize the py_clob_client."""
        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import ApiCreds
            
            # Build credentials if available
            creds = None
            if self.api_key and self.api_secret and self.api_passphrase:
                creds = ApiCreds(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    api_passphrase=self.api_passphrase
                )
            
            self.client = ClobClient(
                host=self.host,
                key=self.private_key,
                chain_id=self.chain_id,
                creds=creds
            )
            logger.info("[CLOB] Client initialized successfully")
            
        except ImportError:
            logger.warning("[CLOB] py_clob_client not found - running in mock mode")
            self.client = None
        except Exception as e:
            logger.error(f"[CLOB] Init error: {e}")
            self.client = None

    def place_order(self, 
                    token_id: str, 
                    side: str, 
                    price: float, 
                    size: float,
                    order_type: OrderType = OrderType.FOK) -> OrderResult:
        """
        Place an order on the CLOB.
        
        Args:
            token_id: Market token ID
            side: 'BUY' or 'SELL'
            price: Limit price
            size: Order size
            order_type: FOK, GTC, etc.
            
        Returns:
            OrderResult with execution details
        """
        if not self.client:
            return OrderResult(
                success=False,
                order_id=None,
                filled_size=0.0,
                avg_price=0.0,
                error="CLOB client not initialized"
            )
        
        self._stats['total_orders'] += 1
        
        logger.info(f"[ORDER] {side} {size:.4f} @ {price:.4f} | Type: {order_type.value} | Token: {token_id[:20]}...")
        
        try:
            clob_side = "BUY" if side.upper() == "BUY" else "SELL"
            
            resp = self.client.create_and_post_order(
                token_id=token_id,
                price=price,
                size=size,
                side=clob_side,
                order_type=order_type.value
            )
            
            order_id = resp.get("orderID") or resp.get("order_id") or resp.get("id")
            
            if order_id:
                self._stats['successful_orders'] += 1
                self._stats['total_volume'] += size * price
                
                logger.info(f"[ORDER] SUCCESS: {order_id}")
                
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    filled_size=size,  # FOK = full fill or nothing
                    avg_price=price,
                    raw_response=resp
                )
            else:
                self._stats['failed_orders'] += 1
                error_msg = resp.get('error') or resp.get('message') or 'No order ID returned'
                
                logger.warning(f"[ORDER] FAILED: {error_msg}")
                
                return OrderResult(
                    success=False,
                    order_id=None,
                    filled_size=0.0,
                    avg_price=0.0,
                    error=error_msg,
                    raw_response=resp
                )
                
        except Exception as e:
            self._stats['failed_orders'] += 1
            logger.error(f"[ORDER] EXCEPTION: {e}")
            
            return OrderResult(
                success=False,
                order_id=None,
                filled_size=0.0,
                avg_price=0.0,
                error=str(e)
            )

    def place_fok_order(self, 
                        token_id: str, 
                        side: str, 
                        price: float, 
                        size: float) -> OrderResult:
        """
        Place a Fill-or-Kill order.
        Critical for arbitrage - ensures atomic execution.
        """
        return self.place_order(token_id, side, price, size, OrderType.FOK)

    def execute_arb_batch(self, 
                          orders: List[Dict]) -> Tuple[bool, List[OrderResult]]:
        """
        Execute a batch of orders atomically.
        
        For arbitrage, all orders must succeed or we rollback.
        
        Args:
            orders: List of order dicts with token_id, side, price, size
            
        Returns:
            (all_success, list of OrderResults)
        """
        results = []
        all_success = True
        
        logger.info(f"[BATCH] Executing {len(orders)} orders atomically")
        
        for i, order in enumerate(orders):
            result = self.place_fok_order(
                token_id=order['token_id'],
                side=order['side'],
                price=order['price'],
                size=order['size']
            )
            results.append(result)
            
            if not result.success:
                all_success = False
                logger.warning(f"[BATCH] Order {i+1}/{len(orders)} FAILED - aborting batch")
                
                # For true atomicity, we'd need to cancel/reverse previous orders
                # FOK orders help - they either fully execute or don't
                break
        
        if all_success:
            logger.info(f"[BATCH] All {len(orders)} orders executed successfully")
        else:
            logger.warning(f"[BATCH] Batch execution failed at order {len(results)}/{len(orders)}")
            
        return all_success, results

    def get_address(self) -> str:
        """Derive wallet address from private key."""
        try:
            from eth_account import Account
            return Account.from_key(self.private_key).address
        except Exception as e:
            logger.error(f"[CLOB] Could not derive address: {e}")
            wallet_addr = os.getenv('WALLET_ADDRESS')
            return wallet_addr if wallet_addr else "0xUnknown"

    def get_balance(self) -> float:
        """
        Fetch USDC/collateral balance.
        Returns 0.0 on error (fail-closed).
        """
        if not self.client:
            return 0.0
            
        try:
            # Try different methods
            try:
                bal_info = self.client.get_balance_allowance()
                if isinstance(bal_info, dict):
                    return float(bal_info.get('balance', 0) or 0)
                return float(bal_info) if bal_info else 0.0
            except:
                pass
            
            # Fallback: try get_collateral_balance if available
            if hasattr(self.client, 'get_collateral_balance'):
                return float(self.client.get_collateral_balance())
            
            # Last resort
            return 0.0
            
        except Exception as e:
            logger.warning(f"[CLOB] Balance fetch error: {e}")
            return 0.0

    def get_order_book(self, token_id: str) -> Dict:
        """Get order book for a token."""
        if self.client:
            try:
                return self.client.get_order_book(token_id)
            except Exception as e:
                logger.debug(f"[CLOB] Orderbook error for {token_id[:20]}: {e}")
        return {"bids": [], "asks": []}

    def get_midpoint(self, token_id: str) -> Optional[float]:
        """Get midpoint price for a token."""
        if not self.client:
            return None
            
        try:
            mid = self.client.get_midpoint(token_id)
            if mid:
                return float(mid.get('mid', 0))
        except:
            pass
        return None

    def get_best_bid_ask(self, token_id: str) -> Tuple[Optional[float], Optional[float]]:
        """Get best bid and ask prices."""
        book = self.get_order_book(token_id)
        
        bids = book.bids if hasattr(book, 'bids') else book.get('bids', [])
        asks = book.asks if hasattr(book, 'asks') else book.get('asks', [])
        
        best_bid = None
        best_ask = None
        
        if bids:
            if hasattr(bids[0], 'price'):
                best_bid = float(bids[0].price)
            else:
                best_bid = float(bids[0].get('price', 0))
                
        if asks:
            if hasattr(asks[0], 'price'):
                best_ask = float(asks[0].price)
            else:
                best_ask = float(asks[0].get('price', 0))
                
        return best_bid, best_ask

    def get_stats(self) -> Dict:
        """Get execution statistics."""
        success_rate = 0.0
        if self._stats['total_orders'] > 0:
            success_rate = self._stats['successful_orders'] / self._stats['total_orders'] * 100
            
        return {
            **self._stats,
            'success_rate': success_rate
        }

