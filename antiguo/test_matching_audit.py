import asyncio
import os
from src.core.arbitrage_detector import ArbitrageDetector
from dotenv import load_dotenv

load_dotenv()

async def audit_matching():
    # Set ROI to 0 to see EVERYTHING
    detector = ArbitrageDetector(min_profit_percent=0.0)
    
    print("--- Audit: High Sensitivity Matching ---")
    poly_markets, sx_markets = await detector.fetch_all_markets()
    
    print(f"Polymarket: {len(poly_markets)} events")
    print(f"SX Bet: {len(sx_markets)} markets")
    
    matches = detector.match_events(poly_markets, sx_markets)
    print(f"\nMatches Found with 82% Threshold: {len(matches)}")
    
    for poly, sx in matches[:15]:
        p_title = poly.get('title', 'N/A')
        s_title = sx.get('label', 'N/A')
        print(f"  Match: [P] {p_title[:40]} <-> [S] {s_title[:40]}")
    
    # Calculate one arbitrage to test robust mapping
    if matches:
        print("\nTesting Arbitrage Calculation Mapping...")
        opp = await detector.calculate_arbitrage(matches[0][0], matches[0][1])
        if opp:
            print(f"  Mapping success! Strategy: {opp['strategy']['name']}")
            print(f"  Poly Token: {opp['poly_token']}")
        else:
            print("  No opportunity (or depth issues) in sample match.")

if __name__ == "__main__":
    asyncio.run(audit_matching())
