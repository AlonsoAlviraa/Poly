
import asyncio
from datetime import datetime
from src.utils.telegram_bot import TelegramBot
from src.strategies.atomic_arbitrage import ArbitrageOpportunity
import sys

# Hardcoded for test
TOKEN = "8141776377:AAElO9CgQzfw3t1J_Rx0iIEVPBG6taWasps"
CHAT_ID = "1653399031"

async def force_alert():
    print("[TEST] Triggering FAKE Atomic Arbitrage Alert...")
    
    bot = TelegramBot(TOKEN, CHAT_ID)
    
    # Create Fake Opportunity
    opp = ArbitrageOpportunity(
        market_id="123456",
        market_title="TEST: Will Trump tweet about Crypto today?",
        yes_price=0.55,
        no_price=0.55,
        sum_price=1.10,
        deviation=0.10,
        direction="SPLIT_SELL",
        estimated_profit_pct=8.00,
        yes_token_id="0xFAKE1",
        no_token_id="0xFAKE2",
        timestamp=datetime.now()
    )
    opp.condition_id = "0xFAKE_CONDITION"
    
    # Send
    await bot.send_atomic_alert(opp, 10.0)
    print("[OK] Alert Sent! Check Telegram.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(force_alert())
