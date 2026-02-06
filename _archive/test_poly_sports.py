#!/usr/bin/env python3
"""Quick check for sports markets on Polymarket."""

from src.data.gamma_client import GammaAPIClient

SPORTS_KEYWORDS = [
    'nba', 'nfl', 'soccer', 'football', 'champion', 'premier', 
    'la liga', 'super bowl', 'tennis', 'wimbledon', 'mlb', 
    'hockey', 'ufc', 'mma', 'world cup', 'euro 2026', 'bundesliga',
    'serie a', 'ligue 1', 'playoffs', 'finals', 'mvp', 'heisman',
    'olympics', 'medal'
]

def main():
    print("=" * 60)
    print("POLYMARKET SPORTS MARKETS CHECK")
    print("=" * 60)
    
    client = GammaAPIClient()
    
    # Get top markets by volume
    markets = client.get_markets(closed=False, limit=100, order='volume')
    print(f"\nTotal markets fetched: {len(markets)}")
    
    # Filter for sports
    sports_markets = []
    
    for m in markets:
        question = m.get('question', '').lower()
        if any(kw in question for kw in SPORTS_KEYWORDS):
            sports_markets.append(m)
    
    print(f"Sports markets found: {len(sports_markets)}")
    
    if sports_markets:
        print("\n⚽ Sports Markets on Polymarket:")
        print("-" * 50)
        
        for m in sports_markets[:15]:
            q = m.get('question', '')[:65]
            vol = float(m.get('volume', 0) or 0)
            tokens = m.get('tokens', [])
            yes_price = float(tokens[0].get('price', 0.5)) if tokens else 0.5
            
            print(f"\n  📊 {q}...")
            print(f"     Volume: ${vol:,.0f} | YES: {yes_price:.2%}")
    else:
        print("\n⚠️ No sports markets found on Polymarket right now.")
        print("   This could mean:")
        print("   1. Sports markets have low volume (not in top 100)")
        print("   2. No active sports prediction questions")
        print("\n   Let's check ALL categories...")
        
        # Show some sample markets
        print("\n📋 Sample Polymarket Markets (by volume):")
        for m in markets[:10]:
            q = m.get('question', '')[:60]
            print(f"   - {q}...")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
