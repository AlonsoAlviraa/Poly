"""
Betfair-Polymarket Mapping Prerequisites Checker.

This script diagnoses the compatibility between your Betfair account
and Polymarket's market categories.

Key Finding:
- Betfair SPAIN (.es) = ONLY Sports (Soccer, Basketball, etc.)
- Betfair GLOBAL (.com) = Has Politics, Specials, Financial (for Polymarket arbitrage)
"""

import os
import asyncio
from dotenv import load_dotenv
from src.data.betfair_client import BetfairClient, BetfairEndpoint
from config.betfair_event_types import (
    POLYMARKET_COMPATIBLE_EVENT_TYPES,
    SPORTS_EVENT_TYPES,
    get_event_type_name,
)

load_dotenv()

def print_header(text: str):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)

def print_warning(text: str):
    print(f"\n⚠️  WARNING: {text}")

def print_success(text: str):
    print(f"✅ {text}")

def print_error(text: str):
    print(f"❌ {text}")


async def check():
    print_header("BETFAIR-POLYMARKET COMPATIBILITY CHECK")
    
    # 1. Check basic credentials
    print("\n📋 [1/4] Checking Credentials...")
    
    llm_key = os.getenv('API_LLM') or os.getenv('OPENROUTER_API_KEY')
    betfair_user = os.getenv('BETFAIR_USERNAME') or os.getenv('BETFAIR_USER')
    betfair_pass = os.getenv('BETFAIR_PASSWORD') or os.getenv('BETFAIR_PASS')
    betfair_key = os.getenv('BETFAIR_APP_KEY_DELAY') or os.getenv('BETFAIR_APP_KEY')
    
    print(f"  LLM API Key: {'✅ Present' if llm_key else '❌ Missing'}")
    print(f"  Betfair Username: {'✅ ' + betfair_user[:10] + '...' if betfair_user else '❌ Missing'}")
    print(f"  Betfair Password: {'✅ Present' if betfair_pass else '❌ Missing'}")
    print(f"  Betfair App Key: {'✅ Present' if betfair_key else '❌ Missing'}")
    
    # 2. Detect jurisdiction from username
    print("\n📍 [2/4] Detecting Betfair Jurisdiction...")
    
    is_spanish_account = betfair_user and (".es" in betfair_user.lower() or "@" in betfair_user)
    endpoint = BetfairEndpoint.SPAIN  # TODO: Make configurable via .env
    
    print(f"  Using endpoint: {endpoint.name} ({endpoint.value})")
    
    # 3. Test Connection and List Event Types
    print("\n🔌 [3/4] Connecting to Betfair API...")
    
    client = BetfairClient(endpoint=endpoint)
    
    if not await client.login():
        print_error("Login Failed!")
        print("  Check your credentials in .env file.")
        return
    
    print_success("Login Successful!")
    
    # List available event types
    print("\n📊 [4/4] Analyzing Available Markets...")
    
    event_types = await client.list_event_types()
    
    print(f"\n  Found {len(event_types)} event types on Betfair {endpoint.name}:")
    
    has_politics = False
    has_specials = False
    has_financial = False
    
    for et in sorted(event_types, key=lambda x: x.get('market_count', 0), reverse=True):
        et_id = et['id']
        et_name = et['name']
        count = et.get('market_count', 0)
        
        marker = ""
        if et_id == "2378961":
            marker = " ⭐ POLITICS"
            has_politics = True
        elif et_id == "10":
            marker = " ⭐ SPECIALS"
            has_specials = True
        elif et_id == "6231":
            marker = " ⭐ FINANCIAL"
            has_financial = True
        
        print(f"    {et_id}: {et_name} ({count} markets){marker}")
    
    # Diagnosis
    print_header("DIAGNOSIS")
    
    if has_politics or has_specials or has_financial:
        print_success("Your Betfair account has access to Polymarket-compatible categories!")
        print("\n  You can proceed with cross-platform arbitrage between:")
        print("    • Polymarket (Politics/Crypto questions)")
        print("    • Betfair (Politics/Special Bets)")
    else:
        print_warning("Your Betfair account does NOT have Politics/Specials/Financial markets!")
        print("""
  This is a JURISDICTIONAL LIMITATION, not a bug:
  
  🇪🇸 Betfair.es (Spain): ONLY allows sports betting (Soccer, Basketball, etc.)
  🇬🇧 Betfair.com (UK/Global): Has Politics, Specials, Financial Bets
  
  Your account is registered on Betfair Spain, which is legally restricted
  to sports markets only by Spanish gambling regulations (DGOJ).
""")
        
        print_header("YOUR OPTIONS")
        print("""
  OPTION 1: Create a Betfair UK/Global Account
  ─────────────────────────────────────────────
  • Requires non-Spanish residence or VPN (Terms of Service violation)
  • Register at betfair.com (not .es)
  • Will have access to Politics, Specials, Financial markets
  
  OPTION 2: Use Sports Arbitrage Instead
  ───────────────────────────────────────
  • Compare Polymarket sports predictions with Betfair sports odds
  • Limited to questions like "Will X team win the championship?"
  • Fewer opportunities but works with your current account
  
  OPTION 3: Use Alternative Prediction Markets
  ─────────────────────────────────────────────
  • Kalshi (US-based, regulated) - Has Politics, Crypto, Events
  • PredictIt (US-based) - Politics focus
  • These can be compared with Polymarket for arbitrage
  
  OPTION 4: Sports-Only Mode (Recommended for Spain)
  ──────────────────────────────────────────────────
  • Use this bot for Polymarket vs Betfair SPORTS arbitrage
  • Focus on sports prediction markets on Polymarket
  • Run: python -m src.arbitrage.cross_platform_mapper --sports-mode
""")
        
        # Check if there are sports events
        print("\n📋 Available Sports Markets for Arbitrage:")
        sports_events = await client.list_events(event_type_ids=SPORTS_EVENT_TYPES[:3])
        print(f"  Found {len(sports_events)} upcoming sports events.")
        if sports_events:
            for e in sports_events[:5]:
                print(f"    • {e['name']}")


async def check_global_endpoint():
    """Try to connect to Betfair Global (may fail for Spanish accounts)."""
    print_header("TESTING BETFAIR GLOBAL ENDPOINT")
    
    print("  Attempting connection to api.betfair.com...")
    
    client = BetfairClient(endpoint=BetfairEndpoint.GLOBAL)
    
    if await client.login():
        print_success("Connected to Betfair Global!")
        
        event_types = await client.list_event_types()
        political_types = [et for et in event_types if et['id'] in ['2378961', '10', '6231']]
        
        if political_types:
            print_success("Politics/Specials/Financial categories are available!")
            for et in political_types:
                print(f"    {et['id']}: {et['name']} ({et.get('market_count', 0)} markets)")
        else:
            print_warning("No Politics categories found on Global either.")
    else:
        print_error("Cannot connect to Betfair Global.")
        print("  Your account may be geo-restricted to Spain only.")


if __name__ == "__main__":
    asyncio.run(check())
    
    # Optionally try Global endpoint
    print("\n")
    user_input = input("Try Betfair Global endpoint? (y/n): ").strip().lower()
    if user_input == 'y':
        asyncio.run(check_global_endpoint())
