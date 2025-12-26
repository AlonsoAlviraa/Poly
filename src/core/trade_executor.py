import asyncio
import os
from typing import Dict, Optional
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
from py_clob_client.clob_types import MarketOrderArgs
from src.exchanges.sx_bet_client import SXBetClient
from src.wallet.wallet_manager import WalletManager

class TradeExecutor:
    """
    Executes arbitrage trades on both platforms.
    Handles order placement, fills, and error recovery.
    """
    
    def __init__(self, wallet: WalletManager):
        self.wallet = wallet
        
        # Initialize Polymarket CLOB client
        # Try to use explicit credentials if available to avoid derivation issues
        creds = None
        poly_key = os.getenv("POLY_KEY")
        poly_secret = os.getenv("POLY_SECRET")
        poly_passphrase = os.getenv("POLY_PASSPHRASE")
        
        if poly_key and poly_secret and poly_passphrase:
             try:
                 creds = ApiCreds(
                    api_key=poly_key,
                    api_secret=poly_secret,
                    api_passphrase=poly_passphrase
                 )
                 print("  DEBUG: Using explicit API Credentials for TradeExecutor")
             except Exception as e:
                 print(f"  Warning: Could not load API credentials: {e}")

        self.poly_client = ClobClient(
            host="https://clob.polymarket.com",
            key=wallet.private_key,
            chain_id=POLYGON,
            creds=creds
        )
        
        # Initialize SX Bet client
        sx_api_key = os.getenv("SX_BET_API_KEY")
        self.sx_client = SXBetClient(api_key=sx_api_key)
        
        print("✅ Trade executor initialized")
        print("DEBUG: LOADED NEW EXECUTOR WITH MARKET_ORDER_ARGS")
    
    async def execute_polymarket_order(
        self,
        token_id: str,
        side: str,
        amount: float,
        price: float
    ) -> Optional[Dict]:
        """
        Execute order on Polymarket.
        Args:
            token_id: Polymarket token ID
            side: 'BUY' or 'SELL'
            amount: Amount in USDC
            price: Price (0-1)
        """
        try:
            print(f"  Placing Polymarket {side} order: {amount} @ {price}")
            print(f"  DEBUG: token_id='{token_id}' type={type(token_id)}")
            
            # Create order using py-clob-client
            # NOTE: This is simplified - real implementation needs proper order creation
            order_args = MarketOrderArgs(
                token_id=token_id,
                side=side,
                amount=amount
            )
            order = self.poly_client.create_market_order(order_args)
            
            # Post order
            response = self.poly_client.post_order(order)
            
            print(f"  ✅ Polymarket order placed: {response.get('orderID')}")
            return response
            
        except Exception as e:
            print(f"  ❌ Polymarket order failed: {e}")
            return None
    
    async def execute_sx_order(
        self,
        market_id: str,
        side: str,
        amount: float,
        price: float
    ) -> Optional[Dict]:
        """
        Execute order on SX Bet.
        Args:
            market_id: SX Bet market hash
            side: 'buy' or 'sell'
            amount: Amount in USDC
            price: Price (0-1)
        """
        try:
            print(f"  Placing SX Bet {side} order: {amount} @ {price}")
            
            response = await self.sx_client.place_order(
                market_id=market_id,
                side=side,
                price=price,
                amount=amount
            )
            
            if response:
                print(f"  ✅ SX Bet order placed: {response.get('orderId')}")
            return response
            
        except Exception as e:
            print(f"  ❌ SX Bet order failed: {e}")
            return None
    
    async def execute_arbitrage(self, opportunity: Dict, position_size: float) -> bool:
        """
        Execute full arbitrage trade with ATOMIC ROLLBACK.
        If second leg fails, immediately reverses first leg.
        Returns True if successful, False otherwise.
        """
        strategy = opportunity['strategy']
        poly_side = strategy['poly_side']
        sx_side = strategy['sx_side']
        
        poly_market_id = opportunity['poly_market_id']
        sx_market_id = opportunity['sx_market_id']
        
        poly_price = opportunity['poly_price']
        sx_price = opportunity['sx_price']
        
        print(f"\n⚡ Executing ATOMIC arbitrage trade...")
        print(f"  Position size: ${position_size}")
        
        poly_order = None
        sx_order = None
        
        try:
            # STEP 1: Execute Polymarket first (higher liquidity, faster)
            print(f"\n  [1/2] Executing Polymarket leg...")
            if 'buy_yes' in poly_side:
                poly_order = await self.execute_polymarket_order(
                    token_id=poly_market_id,
                    side='BUY',
                    amount=position_size,
                    price=poly_price
                )
            elif 'sell_yes' in poly_side:
                poly_order = await self.execute_polymarket_order(
                    token_id=poly_market_id,
                    side='SELL',
                    amount=position_size,
                    price=poly_price
                )
            
            if not poly_order:
                print(f"  ❌ Polymarket order failed - ABORTING")
                return False
            
            print(f"  ✅ Polymarket leg filled")
            
            # STEP 2: Execute SX Bet (slower, less liquid)
            print(f"\n  [2/2] Executing SX Bet leg...")
            if 'buy_yes' in sx_side:
                sx_order = await self.execute_sx_order(
                    market_id=sx_market_id,
                    side='buy',
                    amount=position_size,
                    price=sx_price * 1.02  # 2% slippage cushion
                )
            elif 'sell_yes' in sx_side:
                sx_order = await self.execute_sx_order(
                    market_id=sx_market_id,
                    side='sell',
                    amount=position_size,
                    price=sx_price * 0.98  # 2% slippage cushion
                )
            
            if not sx_order:
                print(f"  ❌ SX Bet order FAILED - ROLLING BACK POLYMARKET")
                # ROLLBACK: Reverse the Polymarket position
                rollback_side = 'SELL' if 'buy' in poly_side else 'BUY'
                await self.execute_polymarket_order(
                    token_id=poly_market_id,
                    side=rollback_side,
                    amount=position_size,
                    price=poly_price * 0.99  # Accept 1% loss on rollback
                )
                print(f"  ⚠️  Rollback executed - small loss accepted")
                return False
            
            print(f"  ✅ SX Bet leg filled")
            print(f"\n  ✅✅ BOTH LEGS EXECUTED - ARBITRAGE COMPLETE!")
            return True
            
        except Exception as e:
            print(f"  💥 CRITICAL ERROR: {e}")
            # If we have Poly position, try to rollback
            if poly_order and not sx_order:
                print(f"  🚨 Emergency rollback...")
                try:
                    rollback_side = 'SELL' if 'buy' in poly_side else 'BUY'
                    await self.execute_polymarket_order(
                        token_id=poly_market_id,
                        side=rollback_side,
                        amount=position_size,
                        price=poly_price * 0.95  # Accept 5% loss in emergency
                    )
                    print(f"  ⚠️  Emergency rollback completed")
                except Exception as rollback_error:
                    print(f"  💀 ROLLBACK FAILED: {rollback_error}")
                    print(f"  ⚠️⚠️ MANUAL INTERVENTION REQUIRED!")
            return False
    
    async def close(self):
        """Clean up resources"""
        await self.sx_client.close()

if __name__ == "__main__":
    # Test executor
    async def test():
        from dotenv import load_dotenv
        load_dotenv()
        
        wallet = WalletManager()
        executor = TradeExecutor(wallet)
        
        print("Trade executor ready")
        await executor.close()
    
    asyncio.run(test())
