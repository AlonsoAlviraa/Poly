import asyncio
import csv
import os
from datetime import datetime
from src.collectors.bookmakers import BookmakerClient
from src.collectors.polymarket import PolymarketClient
from src.core.matcher import EventMatcher
from src.core.analyzer import ArbitrageAnalyzer
from src.utils.normalization import normalize_text
from src.utils.telegram_bot import TelegramBot
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

QA_FILE = "qa_matches.csv"

# Heartbeat tracking
scan_count = 0
total_matches = 0
error_count = 0
start_time = datetime.utcnow()

async def main():
    global scan_count, total_matches, error_count
    
    print("Starting QA Sweep (Massive Ingestion)...")
    
    # Init Telegram Bot
    telegram = None
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        telegram = TelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        if scan_count == 0:  # First run
            await telegram.send_startup_message()
    
    # Init
    bookie_client = BookmakerClient()
    poly_client = PolymarketClient()
    matcher = EventMatcher()
    analyzer = ArbitrageAnalyzer()

    try:
        # Fetch Data Concurrently
        print("Fetching data...")
        fetch_start = datetime.now()
        
        results = await asyncio.gather(
            bookie_client.get_all_odds_async(),
            poly_client.search_events_async()
        )
        bookie_events, poly_events = results
        
        print(f"Fetched {len(bookie_events)} Bookmaker events and {len(poly_events)} Polymarket events in {(datetime.now() - fetch_start).total_seconds():.2f}s.")

        # Debug: Print samples
        if bookie_events:
            print(f"Sample Bookie: {bookie_events[0].get('home_team')} vs {bookie_events[0].get('away_team')} ({bookie_events[0].get('commence_time')})")
        if poly_events:
            print("Sample Poly Events:")
            for i, p in enumerate(poly_events[:5]):
                print(f" - {p.get('title')} ({p.get('startDate')})")

        # 2. Match Events & Filter High-Quality Candidates
        print("Running QA Matching (Threshold > 60)...")
        all_matches = []
        high_quality_candidates = []  # Score > 85 for orderbook fetching
        
        for b_event in bookie_events:
            b_home = b_event.get("home_team", "")
            b_away = b_event.get("away_team", "")
            b_start = b_event.get("commence_time", "")
            
            if not b_home or not b_away:
                continue
                
            b_home_clean = matcher.get_alias(b_home)
            b_away_clean = matcher.get_alias(b_away)
            
            for p_event in poly_events:
                p_title = p_event.get("title", "")
                p_start = p_event.get("startDate", "")
                
                if not p_start:
                    continue
                    
                p_title_clean = normalize_text(p_title)
                
                from thefuzz import fuzz
                score_home = fuzz.token_set_ratio(b_home_clean, p_title_clean)
                score_away = fuzz.token_set_ratio(b_away_clean, p_title_clean)
                avg_score = (score_home + score_away) / 2
                
                if avg_score > 60:
                    b_name = f"{b_home} vs {b_away}"
                    all_matches.append({
                        "bookie_event": b_event,
                        "poly_event": p_event,
                        "bookie_name": b_name,
                        "poly_title": p_title,
                        "score": avg_score,
                        "b_home_clean": b_home_clean,
                        "b_away_clean": b_away_clean,
                        "p_title_clean": p_title_clean
                    })
                    
                    # High-quality candidates for orderbook fetching (lowered from 85 to 75)
                    if avg_score > 75:
                        high_quality_candidates.append({
                            "bookie_event": b_event,
                            "poly_event": p_event,
                            "bookie_name": b_name,
                            "poly_title": p_title,
                            "score": avg_score
                        })

        print(f"Total Matches (Score > 60): {len(all_matches)}")
        print(f"High-Quality Candidates (Score > 75): {len(high_quality_candidates)}")
        
        # 3. Async Orderbook Fetching (Batching)
        print(f"Fetching orderbooks for {len(high_quality_candidates)} high-quality matches...")
        orderbook_tasks = []
        
        for candidate in high_quality_candidates:
            poly_event = candidate["poly_event"]
            # Extract token_id from first market (typically "Will X win?")
            markets = poly_event.get("markets", [])
            if markets and len(markets) > 0:
                clob_token_ids = markets[0].get("clobTokenIds", [])
                if clob_token_ids and len(clob_token_ids) > 0:
                    token_id = clob_token_ids[0]
                    # Validate token_id is a proper string, not a list
                    if token_id and isinstance(token_id, str) and len(token_id) > 10:
                        orderbook_tasks.append({
                            "candidate": candidate,
                            "token_id": token_id,
                            "task": poly_client.get_orderbook_depth_async(token_id)
                        })
        
        print(f"Fetching {len(orderbook_tasks)} orderbooks in parallel...")
        orderbook_results = await asyncio.gather(*[task["task"] for task in orderbook_tasks], return_exceptions=True)
        
        # 4. Calculate EV with Orderbook Data
        actionable_arbs = []
        
        with open(QA_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Bookie Event", "Poly Event", "Score", "EV %", "Liquidity", "Norm Bookie", "Norm Poly"])
            
            # First write all low-quality matches without EV
            for match in all_matches:
                if match["score"] <= 75:
                    writer.writerow([
                        match["bookie_name"],
                        match["poly_title"],
                        match["score"],
                        "N/A",
                        "N/A",
                        f"{match['b_home_clean']} vs {match['b_away_clean']}",
                        match["p_title_clean"]
                    ])
            
            # Now process high-quality matches with orderbook data
            for i, task_data in enumerate(orderbook_tasks):
                orderbook = orderbook_results[i]
                candidate = task_data["candidate"]
                
                if isinstance(orderbook, Exception):
                    print(f"Orderbook fetch failed for {candidate['bookie_name']}: {orderbook}")
                    continue
                
                if not orderbook or "asks" not in orderbook:
                    continue
                
                # Calculate arbitrage with orderbook depth
                arb_result = analyzer.calculate_arbitrage(
                    candidate["bookie_event"],
                    candidate["poly_event"],
                    orderbook["asks"]
                )
                
                if arb_result:
                    ev_percent = arb_result.get("ev_percent", 0)
                    liquidity = arb_result.get("poly_liquidity", 0)
                    
                    writer.writerow([
                        candidate["bookie_name"],
                        candidate["poly_title"],
                        candidate["score"],
                        f"{ev_percent:.2f}",
                        f"{liquidity:.0f}",
                        f"{candidate['bookie_event'].get('home_team')} vs {candidate['bookie_event'].get('away_team')}",
                        candidate["poly_title"]
                    ])
                    
                    # Filter for actionable arbs: EV > 1.5% AND Liquidity > $50 (lowered from 2.5%)
                    if ev_percent > 1.5 and liquidity > 50 and telegram:
                        poly_slug = candidate["poly_event"].get("slug", "")
                        
                        actionable_arbs.append({
                            "home_team": candidate["bookie_event"].get("home_team"),
                            "away_team": candidate["bookie_event"].get("away_team"),
                            "bet_team": arb_result.get("bet_team", candidate["bookie_event"].get("home_team")),
                            "ev_percent": ev_percent,
                            "poly_price": arb_result.get("poly_price", 0),
                            "bookie_odds": arb_result.get("bookie_odds", 0),
                            "liquidity": liquidity,
                            "poly_slug": poly_slug
                        })

        print(f"QA Sweep Complete. Found {len(all_matches)} potential matches. Saved to {QA_FILE}.")
        print(f"Actionable Arbs (EV > 1.5%, Liq > $50): {len(actionable_arbs)}")
        
        # Send Telegram alerts for actionable arbs (limit to top 5)
        if telegram and actionable_arbs:
            for arb in actionable_arbs[:5]:
                await telegram.send_arb_alert(arb)
        
        # Update counters
        scan_count += 1
        total_matches += len(all_matches)
        
        # Send heartbeat every 4 scans (~20 minutes at 5-min intervals)
        if telegram and scan_count % 4 == 0:
            uptime = datetime.utcnow() - start_time
            uptime_str = f"{int(uptime.total_seconds() // 3600)}h {int((uptime.total_seconds() % 3600) // 60)}m"
            
            await telegram.send_heartbeat({
                "bookie_events": len(bookie_events),
                "poly_events": len(poly_events),
                "matches": len(all_matches),
                "errors": error_count,
                "ip": "158.179.214.56",
                "uptime": uptime_str
            })
    
    except Exception as e:
        error_count += 1
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        # Send critical alert if 5+ consecutive errors
        if telegram and error_count >= 5:
            await telegram.send_error_alert(f"Script crashed: {str(e)[:200]}", critical=True)

if __name__ == "__main__":
    asyncio.run(main())
