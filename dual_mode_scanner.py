#!/usr/bin/env python3
"""
Dual-Mode Arbitrage Scanner for Spanish Accounts.

This script provides two arbitrage modes:

MODE A: SPORTS ARBITRAGE (Polymarket Sports ↔ Betfair España)
========================================================
- Uses your existing Betfair España account (only has sports)
- Matches sports prediction markets on Polymarket with Betfair events
- Categories: Soccer, NBA, NFL, Tennis, etc.
- Now uses LLM (MiMo-V2-Flash) for intelligent matching!

MODE B: CRYPTO/POLITICS ARBITRAGE (Polymarket ↔ SX Bet)  
========================================================
- Uses SX Bet (blockchain exchange) instead of Betfair
- No KYC/jurisdiction restrictions (wallet-based)
- Categories: Politics, Crypto, Entertainment
- Same USDC currency as Polymarket (no conversion)

Usage:
    python dual_mode_scanner.py --mode sports    # Sports only
    python dual_mode_scanner.py --mode politics  # Politics/Crypto via SX Bet
    python dual_mode_scanner.py --mode both      # Scan both
    python dual_mode_scanner.py --mode sports --use-llm  # With LLM matching

Author: APU Arbitrage Bot
"""

import os
import sys
import asyncio
import argparse
import logging
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass

from dotenv import load_dotenv
load_dotenv()

# Configure logging - CLEAN output without HTTP spam
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s │ %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Silence noisy HTTP loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Import clients
from src.data.gamma_client import GammaAPIClient, MarketFilters
from src.data.betfair_client import BetfairClient, BetfairEndpoint
from src.data.sx_bet_client import SXBetClient, SXBetCategory
from config.betfair_event_types import SPORTS_EVENT_TYPES, SPORTS_KEYWORDS

# Import LLM matcher
from src.arbitrage.sports_matcher import SportsMarketMatcher, SportsMatch
from src.data.dual_lane_resolver import SlowLaneWorker
from src.utils.audit_logger import AuditLogger
from src.ui import TerminalDashboard


@dataclass
class ArbitrageOpportunity:
    """Represents an arbitrage opportunity."""
    platform_a: str  # 'polymarket'
    platform_b: str  # 'betfair' or 'sxbet'
    market_a_id: str
    market_b_id: str
    market_name: str
    category: str
    
    # Prices
    price_a: float  # Buy price on platform A
    price_b: float  # Sell price on platform B
    
    # Analysis
    spread_pct: float
    net_spread_pct: float
    direction: str  # 'buy_a_sell_b' or 'buy_b_sell_a'
    is_profitable: bool
    
    # Metadata
    detected_at: datetime
    notes: str = ""
    
    def __str__(self):
        emoji = "🟢" if self.is_profitable else "🔴"
        return (
            f"{emoji} {self.market_name}\n"
            f"   Category: {self.category}\n"
            f"   {self.platform_a}: {self.price_a:.4f} → {self.platform_b}: {self.price_b:.4f}\n"
            f"   Spread (Gross): {self.spread_pct:.2f}% | Net: {self.net_spread_pct:.2f}%\n"
            f"   Direction: {self.direction}"
        )


class DualArbitrageScanner:
    """
    Main scanner that coordinates both arbitrage modes.
    Now with LLM-powered intelligent matching!
    """
    
    def __init__(self,
                 min_spread_pct: float = 1.0,
                 min_liquidity: float = 500.0,
                 use_llm: bool = False,
                 skip_prefilter: bool = False,
                 debug_math: bool = False,
                 force_match_team: Optional[str] = None,
                 poly_fee_pct: float = 0.5,
                 betfair_commission_pct: float = 6.5,
                 gas_fee_pct: float = 0.0,
                 slippage_pct: float = 0.0,
                 dashboard: Optional[TerminalDashboard] = None):
        """
        Args:
            min_spread_pct: Minimum spread % to report
            min_liquidity: Minimum market liquidity ($)
            use_llm: Use LLM (MiMo-V2-Flash) for intelligent matching
            skip_prefilter: Skip keyword pre-filtering, send ALL events to LLM
            debug_math: Show spread calculations for all matches
            force_match_team: Ignore filters for this specific team name
        """
        self.min_spread = min_spread_pct
        self.min_liquidity = min_liquidity
        self.use_llm = use_llm
        self.skip_prefilter = skip_prefilter
        self.debug_math = debug_math
        self.force_match_team = force_match_team
        self.poly_fee_pct = poly_fee_pct
        self.betfair_commission_pct = betfair_commission_pct
        self.gas_fee_pct = gas_fee_pct
        self.slippage_pct = slippage_pct
        self.dashboard = dashboard
        self.recent_events: List[str] = []
        
        # Initialize Mega Debugger
        self.audit = AuditLogger()
        
        # Clients
        self.polymarket = GammaAPIClient()
        self.betfair: Optional[BetfairClient] = None
        self.sxbet: Optional[SXBetClient] = None
        
        # LLM Sports Matcher (only if enabled)
        self.sports_matcher: Optional[SportsMarketMatcher] = None
        self.slow_lane_task: Optional[asyncio.Task] = None
        
        if use_llm:
            self.sports_matcher = SportsMarketMatcher(skip_prefilter=skip_prefilter)
            if self.sports_matcher.api_key:
                mode = "FULL LLM (no filter)" if skip_prefilter else "LLM + keyword filter"
                logger.info(f"🧠 LLM Matching ENABLED: {mode}")
                # Start Slow Lane Worker
                worker = SlowLaneWorker(self.sports_matcher.resolver)
                self.slow_lane_task = asyncio.create_task(self._run_slow_lane(worker))
            else:
                logger.warning("⚠️ LLM requested but no API key - using keyword matching")
                self.use_llm = False
        
        # Results
        self.sports_opportunities: List[ArbitrageOpportunity] = []
        self.politics_opportunities: List[ArbitrageOpportunity] = []
        
        # Stats
        self.stats = {
            'scans': 0,
            'poly_markets_checked': 0,
            'betfair_events_checked': 0,
            'sxbet_markets_checked': 0,
            'sports_opportunities': 0,
            'politics_opportunities': 0,
            'llm_matches': 0,
            'keyword_matches': 0
        }

    def _apply_fee_stripping(self, spread_signed_pct: float) -> Dict[str, Decimal]:
        try:
            spread_signed = Decimal(str(spread_signed_pct))
            total_fees_pct = (
                Decimal(str(self.poly_fee_pct))
                + Decimal(str(self.betfair_commission_pct))
                + Decimal(str(self.gas_fee_pct))
                + Decimal(str(self.slippage_pct))
            )
        except (InvalidOperation, ValueError):
            logger.warning("Invalid fee inputs; defaulting to zero fees.")
            spread_signed = Decimal(str(spread_signed_pct))
            total_fees_pct = Decimal("0")

        net_signed = spread_signed - total_fees_pct
        net_abs = abs(net_signed)
        return {
            "total_fees_pct": total_fees_pct,
            "net_signed": net_signed,
            "net_abs": net_abs
        }

    def _record_event(self, message: str) -> None:
        self.recent_events.append(message)
        self.recent_events = self.recent_events[-5:]
        if self.dashboard:
            self.dashboard.update_events(self.recent_events)

    async def run_force_test(self):
        """Run a forced test scenario to validate math without external APIs."""
        logger.info("\n" + "=" * 60)
        logger.info("FORCE TEST MODE: Injected scenarios (no external calls)")
        logger.info("=" * 60)

        scenarios = [
            {
                "poly_id": "force_poly_osasuna",
                "poly_question": "Will Osasuna win?",
                "poly_yes": 0.42,
                "bf_odds": 2.70,
                "category": "Sports",
                "notes": "Forced Test: Match Odds"
            },
            {
                "poly_id": "force_poly_over_25",
                "poly_question": "Over 2.5 goals?",
                "poly_yes": 0.78,
                "bf_odds": 1.55,
                "category": "Sports",
                "notes": "Forced Test: Totals (Over/Under)"
            }
        ]

        opportunities = []

        for scenario in scenarios:
            poly_question = scenario["poly_question"]
            poly_yes = scenario["poly_yes"]
            bf_odds = scenario["bf_odds"]
            bf_implied_prob = 1.0 / bf_odds
            spread_signed = (bf_implied_prob - poly_yes) * 100
            spread_pct = abs(spread_signed)
            fee_strip = self._apply_fee_stripping(spread_signed)
            net_signed = fee_strip["net_signed"]
            net_spread_pct = fee_strip["net_abs"]
            threshold = Decimal(str(self.min_spread))

            trace = self.audit.get_event(scenario["poly_id"], poly_question)
            trace.category = scenario.get("category", "unknown")
            trace.add_step("ForceTest", "PASS", scenario["notes"])
            trace.add_step(
                "MathCalc",
                "PASS" if net_spread_pct >= threshold else "FAIL",
                " | ".join([
                    f"Gross {spread_signed:+.2f}% (Abs {spread_pct:.2f}%)",
                    f"Net {float(net_signed):+.2f}% (Abs {float(net_spread_pct):.2f}%)",
                    f"Fees {float(fee_strip['total_fees_pct']):.2f}% | Threshold {self.min_spread:.2f}%"
                ])
            )

            logger.info(f"\n[MATH CHECK] {poly_question}")
            logger.info(f"--- Polymarket (Yes): Price {poly_yes:.3f} (${1.0/poly_yes:.2f})")
            logger.info(f"--- Betfair (BACK): Odds {bf_odds:.2f}")
            logger.info(f"--- Spread Gross: {spread_signed:+.2f}% | Abs: {spread_pct:.2f}%")
            logger.info(
                f"--- Spread Net: {float(net_signed):+.2f}% | Abs: {float(net_spread_pct):.2f}% "
                f"(Fees {float(fee_strip['total_fees_pct']):.2f}%)"
            )
            self._record_event(f"{poly_question[:32]} | Net {float(net_signed):+.2f}%")

            direction = "buy_poly_sell_bf" if poly_yes < bf_implied_prob else "buy_bf_sell_poly"
            opp = ArbitrageOpportunity(
                platform_a='polymarket',
                platform_b='betfair',
                market_a_id=scenario["poly_id"],
                market_b_id="force_bf_market",
                market_name=poly_question[:60],
                category=scenario.get("category", "Sports"),
                price_a=poly_yes,
                price_b=bf_implied_prob,
                spread_pct=spread_pct,
                net_spread_pct=float(net_spread_pct),
                direction=direction,
                is_profitable=net_spread_pct >= threshold,
                detected_at=datetime.now(),
                notes=scenario["notes"]
            )
            opportunities.append(opp)
            self._record_event(f"FORCE OPPORTUNITY {poly_question[:24]} | Net {float(net_spread_pct):.2f}%")

        self.sports_opportunities = opportunities
        self.stats['sports_opportunities'] = len(opportunities)
    
    async def init_betfair(self) -> bool:
        """Initialize Betfair client."""
        self.betfair = BetfairClient(endpoint=BetfairEndpoint.SPAIN, use_delay=True)
        
        if await self.betfair.login():
            logger.info("✅ Betfair España connected")
            return True
        else:
            logger.error("❌ Betfair login failed")
            return False
    
    async def init_sxbet(self) -> bool:
        """Initialize SX Bet client."""
        self.sxbet = SXBetClient()
        
        # Test connection by fetching markets
        try:
            markets = await self.sxbet.get_active_markets()
            if markets:
                logger.info(f"✅ SX Bet connected ({len(markets)} markets)")
                return True
        except Exception as e:
            logger.error(f"❌ SX Bet connection error: {e}")
        
        return False
    
    def is_sports_market(self, question: str) -> bool:
        """Check if a Polymarket question is about sports."""
        question_lower = question.lower()
        
        for keyword in SPORTS_KEYWORDS:
            if keyword in question_lower:
                return True
        
        return False
    
    async def get_polymarket_sports(self) -> List[Dict]:
        """Get sports-related markets from Polymarket using combined sources."""
        # Source 1: Standard filtered markets
        filters = MarketFilters(
            min_volume_24h=0,
            min_liquidity=100,
            max_spread_pct=20.0
        )
        all_markets = self.polymarket.get_filtered_markets(filters, limit=400)
        
        # Source 2: Game Bets (The "Pro" filter for individual matches)
        game_bets = self.polymarket.get_all_match_markets(limit=200)
        
        # Combine and de-duplicate by condition_id
        seen_ids = set()
        combined = []
        
        # Priority to Game Bets
        for m in game_bets:
            c_id = m.get('conditionId') or m.get('condition_id') or m.get('id')
            if c_id not in seen_ids:
                combined.append(m)
                seen_ids.add(c_id)
        
        # Add standard markets if they are sports and not already added
        for m in all_markets:
            c_id = m.get('conditionId') or m.get('condition_id') or m.get('id')
            if c_id not in seen_ids and self.is_sports_market(m.get('question', '')):
                combined.append(m)
                seen_ids.add(c_id)
        
        logger.info(f"[Polymarket] Found {len(combined)} sports markets ({len(game_bets)} Game Bets)")
        return combined

    def _identify_market_requirements(self, poly_question: str) -> Dict:
        """
        Identify Betfair market type and runner target from Polymarket question.
        Returns requirements or None if untrackable.
        """
        q = poly_question.lower()
        req = {
            'market_types': ['MATCH_ODDS'],
            'runner_pattern': None,  # Keyword to find runner
            'target_is_yes': True    # Polymarket YES = Betfair runner
        }

        # Draw market
        if 'draw' in q:
            req['market_types'] = ['MATCH_ODDS']
            req['runner_pattern'] = 'draw'
            return req

        # Over/Under markets (regex detection)
        totals_match = re.search(r"(over|under)\s+(\d+(?:[.,]\d+)?)", q)
        if totals_match:
            direction = totals_match.group(1)
            line_value = float(totals_match.group(2).replace(",", "."))
            suffix = int(round(line_value * 10))
            req['market_types'] = [f"OVER_UNDER_{suffix:02d}"]
            req['runner_pattern'] = direction
            return req

        # Both Teams to Score
        if 'both teams to score' in q or 'btts' in q:
            req['market_types'] = ['BOTH_TEAMS_TO_SCORE']
            req['runner_pattern'] = 'yes' if 'yes' in q else ('no' if 'no' in q else 'yes')
            return req

        # Match Winner (Specific team) - default
        # If the question is "Will Team A win on Date?", we look for Team A in MATCH_ODDS
        return req
    
    async def get_polymarket_politics(self) -> List[Dict]:
        """Get politics/crypto markets from Polymarket."""
        filters = MarketFilters(
            min_volume_24h=self.min_liquidity,
            min_liquidity=self.min_liquidity / 2,
            max_spread_pct=10.0
        )
        
        all_markets = self.polymarket.get_filtered_markets(filters, limit=200)
        
        # Filter for politics/crypto (NOT sports)
        politics_markets = [
            m for m in all_markets 
            if not self.is_sports_market(m.get('question', ''))
        ]
        
        logger.info(f"[Polymarket] Found {len(politics_markets)} politics/crypto markets")
        
        return politics_markets
    
    async def scan_sports_arbitrage(self) -> List[ArbitrageOpportunity]:
        """
        Scan for sports arbitrage: Polymarket ↔ Betfair España
        Uses LLM matching when enabled for better accuracy.
        """
        logger.info("\n" + "=" * 60)
        if self.use_llm:
            logger.info("MODE A: SPORTS ARBITRAGE (Polymarket ↔ Betfair España) + 🧠 LLM")
        else:
            logger.info("MODE A: SPORTS ARBITRAGE (Polymarket ↔ Betfair España)")
        logger.info("=" * 60)
        
        if not self.betfair or not self.betfair.is_authenticated:
            if not await self.init_betfair():
                return []
        
        # Get Polymarket sports markets
        poly_sports = await self.get_polymarket_sports()
        
        if not poly_sports:
            logger.warning("No sports markets found on Polymarket")
            return []
        
        # Get Betfair sports events
        bf_events = await self.betfair.list_events(event_type_ids=SPORTS_EVENT_TYPES)
        logger.info(f"[Betfair] Found {len(bf_events)} sports events")
        
        # Convert to list of dicts for matching
        bf_events_list = [
            {
                'id': e.get('id', ''),
                'name': e.get('name', ''),
                'market_id': e.get('market_id', '')
            }
            for e in bf_events
        ]
        
        self.stats['poly_markets_checked'] += len(poly_sports)
        self.stats['betfair_events_checked'] += len(bf_events)
        
        opportunities = []
        
        # === LLM MATCHING MODE ===
        if self.use_llm and self.sports_matcher:
            logger.info(f"\n🧠 Using LLM matching for {len(poly_sports)} markets...")
            
            matches = await self.sports_matcher.batch_match(
                poly_markets=poly_sports,
                bf_events=bf_events_list,
                max_concurrent=10  # Increased for speed
            )
            
            logger.info(f"   Found {len(matches)} matches via LLM")
            
            # Show matches found
            if matches:
                print("\n" + "=" * 60)
                print("🎯 MATCHES FOUND BY LLM:")
                print("=" * 60)
                for i, m in enumerate(matches[:15]):  # Show top 15
                    print(f"{i+1}. Poly: {m.poly_question[:50]}...")
                    print(f"   → BF: {m.betfair_event_name}")
                    print(f"   Confidence: {m.confidence:.0%} | Reason: {m.reasoning}")
                    print()
                print("=" * 60 + "\n")
            
            # Update stats
            for match in matches:
                if match.source == 'llm':
                    self.stats['llm_matches'] += 1
                else:
                    self.stats['keyword_matches'] += 1
            
            # Analyze each match for arbitrage
            for match in matches:
                # Find Polymarket prices
                poly_market = next(
                    (p for p in poly_sports 
                     if (p.get('conditionId') or p.get('condition_id') or p.get('id')) == match.poly_id),
                    None
                )
                
                if not poly_market:
                    continue
                
                tokens = poly_market.get('tokens', [])
                if len(tokens) < 2:
                    continue
                
                # Verify tokens[0] is a dict with price
                if not isinstance(tokens[0], dict) or 'price' not in tokens[0]:
                    logger.warning(f"Invalid token format for {poly_question[:30]}: {tokens[0]}")
                    continue
                
                poly_yes = float(tokens[0].get('price', 0.5))
                
                # Identify what type of market we need
                req = self._identify_market_requirements(poly_question)
                logger.debug(f"[Arb] Requirements for {poly_question[:30]}: Types={req['market_types']}, Pattern={req['runner_pattern']}")
                
                # Get Betfair prices for matched event
                try:
                    bf_markets = await self.betfair.list_markets(
                        event_ids=[match.betfair_event_id],
                        market_types=req['market_types'],
                        max_results=10
                    )
                    
                    logger.debug(f"[Arb] Found {len(bf_markets)} Betfair markets for event {match.betfair_event_id}")
                    
                    if not bf_markets:
                        # Fallback if specific type failed, try all
                        bf_markets = await self.betfair.list_markets(
                            event_ids=[match.betfair_event_id],
                            max_results=5
                        )
                        logger.debug(f"[Arb] Fallback: Found {len(bf_markets)} markets")
                    
                    for bf_market in bf_markets:
                        prices = await self.betfair.get_prices([bf_market.market_id])
                        
                        if not prices:
                            logger.debug(f"[Arb] No prices for market {bf_market.market_name}")
                            continue
                        
                        # Find the correct runner within the market
                        target_price = None
                        
                        # 1. Use mapping from OutcomeMapper (NEW)
                        runner_target = ""
                        if hasattr(match, 'mapping') and match.mapping:
                            runner_target = match.mapping.get('runner', '').lower()
                            # side_target = match.mapping.get('side', 'BACK') # Side used in execute_order later
                            
                            for p in prices:
                                if runner_target and (runner_target in p.runner_name.lower() or p.runner_name.lower() in runner_target):
                                    target_price = p
                                    break
                        
                        # Fallback for manual matching
                        if not target_price and runner_target:
                            # 2. Try Fuzzy Match (if precision required)
                            if FUZZY_AVAILABLE:
                                best_fuzz = 0
                                for p in prices:
                                    score = fuzz.token_set_ratio(runner_target, p.runner_name.lower())
                                    if score >= 85 and score > best_fuzz:
                                        target_price = p
                                        best_fuzz = score
                            
                            # 3. Last resort: simple inclusion
                            if not target_price:
                                for p in prices:
                                    # Simple inclusion check
                                    if any(word in p.runner_name.lower() for word in poly_question.lower().split() if len(word) > 4):
                                        target_price = p
                                        break
                        
                        if not target_price:
                            logger.debug(f"[Arb] Could not find target runner for {poly_question[:30]} in {bf_market.market_name}")
                            continue
                            
                        best_back = target_price.back_price
                        logger.debug(f"[Arb] Matched: {poly_question[:20]}... YES={poly_yes:.3f} ↔ {bf_market.market_name} | {target_price.runner_name} Back={best_back}")

                        if best_back <= 1.0:
                            continue

                        bf_implied_prob = 1.0 / best_back
                        spread_signed = (bf_implied_prob - poly_yes) * 100
                        spread_pct = abs(spread_signed)
                        fee_strip = self._apply_fee_stripping(spread_signed)
                        net_signed = fee_strip["net_signed"]
                        net_spread_pct = fee_strip["net_abs"]
                        threshold = Decimal(str(self.min_spread))
                        threshold = Decimal(str(self.min_spread))

                        logger.info(f"\n[MATH CHECK] {poly_question[:60]}")
                        logger.info(f"--- Polymarket (Yes): Price {poly_yes:.3f} (${1.0/poly_yes:.2f})")
                        logger.info(f"--- Betfair ({match.mapping.get('side', 'BACK') if match.mapping else 'BACK'}): Odds {best_back:.2f}")
                        logger.info(f"--- Spread Gross: {spread_signed:+.2f}% | Abs: {spread_pct:.2f}%")
                        logger.info(
                            f"--- Spread Net: {float(net_signed):+.2f}% | Abs: {float(net_spread_pct):.2f}% "
                            f"(Fees {float(fee_strip['total_fees_pct']):.2f}%)"
                        )

                        trace.add_step(
                            "MathCalc",
                            "PASS" if net_spread_pct >= threshold else "FAIL",
                            " | ".join([
                                f"Gross {spread_signed:+.2f}% (Abs {spread_pct:.2f}%)",
                                f"Net {float(net_signed):+.2f}% (Abs {float(net_spread_pct):.2f}%)",
                                f"Fees {float(fee_strip['total_fees_pct']):.2f}% | Threshold {self.min_spread:.2f}%"
                            ])
                        )

                        if net_spread_pct >= threshold:
                            direction = "buy_poly_sell_bf" if poly_yes < bf_implied_prob else "buy_bf_sell_poly"

                            opp = ArbitrageOpportunity(
                                platform_a='polymarket',
                                platform_b='betfair',
                                market_a_id=match.poly_id,
                                market_b_id=bf_market.market_id,
                                market_name=match.poly_question[:60],
                                category=match.mapping.get('category', 'Sports') if match.mapping else 'Sports',
                                price_a=poly_yes,
                                price_b=bf_implied_prob,
                                spread_pct=spread_pct,
                                net_spread_pct=float(net_spread_pct),
                                direction=direction,
                                is_profitable=net_spread_pct >= threshold,
                                detected_at=datetime.now(),
                                notes=f"LLM Match ({match.source}): {match.betfair_event_name}, Conf: {match.confidence:.0%}"
                            )

                            opportunities.append(opp)
                            logger.info(f"\n🎯 OPPORTUNITY via {match.source.upper()}:")
                            logger.info(f"{opp}")
                            self._record_event(f"OPP {match.poly_question[:24]} | Net {float(net_spread_pct):.2f}%")
                            trace.final_status = "PASS"
                        else:
                            logger.info("--- Status: REJECTED (Min profit not met)")
                            if net_spread_pct > Decimal("0.01"):
                                logger.debug(
                                    f"[Arb] Narrow net spread ({float(net_spread_pct):.2f}%): "
                                    f"{match.poly_question[:30]}... Poly={poly_yes:.3f} BF={bf_implied_prob:.3f} Odd={best_back:.2f}"
                                )
                            
                except Exception as e:
                    logger.debug(f"Error getting prices for matched event: {e}")
                    continue
        
        # === KEYWORD MATCHING MODE (fallback) ===
        else:
            logger.info("\n📝 Using keyword matching...")
            
            for poly in poly_sports[:20]:  # Limit for demo
                poly_question = poly.get('question', '')
                
                tokens = poly.get('tokens', [])
                if len(tokens) < 2:
                    continue
                    
                poly_yes = float(tokens[0].get('price', 0.5))
                poly_no = float(tokens[1].get('price', 0.5))
                
                for bf_event in bf_events:
                    bf_name = bf_event.get('name', '').lower()
                    
                    poly_terms = set(poly_question.lower().split())
                    bf_terms = set(bf_name.split())
                    
                    common = {t for t in poly_terms.intersection(bf_terms) if len(t) > 3}
                    
                    if len(common) >= 2:
                        self.stats['keyword_matches'] += 1
                        
                        bf_markets = await self.betfair.list_markets(
                            event_ids=[bf_event.get('id')],
                            max_results=5
                        )
                        
                        if not bf_markets:
                            continue
                        
                        for bf_market in bf_markets:
                            prices = await self.betfair.get_prices([bf_market.market_id])
                            
                            if not prices:
                                continue
                            
                            best_back = max((p.back_price for p in prices), default=0)
                            
                            if best_back <= 0:
                                continue
                            
                            bf_implied_prob = 1.0 / best_back
                            
                            spread_signed = (bf_implied_prob - poly_yes) * 100
                            spread_pct = abs(spread_signed)
                            fee_strip = self._apply_fee_stripping(spread_signed)
                            net_signed = fee_strip["net_signed"]
                            net_spread_pct = fee_strip["net_abs"]
                            threshold = Decimal(str(self.min_spread))

                            logger.info(f"\n[MATH CHECK] {poly_question[:60]}")
                            logger.info(f"--- Polymarket (Yes): Price {poly_yes:.3f} (${1.0/poly_yes:.2f})")
                            logger.info(f"--- Betfair (BACK): Odds {best_back:.2f}")
                            logger.info(f"--- Spread Gross: {spread_signed:+.2f}% | Abs: {spread_pct:.2f}%")
                            logger.info(
                                f"--- Spread Net: {float(net_signed):+.2f}% | Abs: {float(net_spread_pct):.2f}% "
                                f"(Fees {float(fee_strip['total_fees_pct']):.2f}%)"
                            )
                            
                            if net_spread_pct >= threshold:
                                direction = "buy_poly_sell_bf" if poly_yes < bf_implied_prob else "buy_bf_sell_poly"
                                
                                opp = ArbitrageOpportunity(
                                    platform_a='polymarket',
                                    platform_b='betfair',
                                    market_a_id=poly.get('condition_id', ''),
                                    market_b_id=bf_market.market_id,
                                    market_name=poly_question[:60],
                                    category='Sports',
                                    price_a=poly_yes,
                                    price_b=bf_implied_prob,
                                    spread_pct=spread_pct,
                                    net_spread_pct=float(net_spread_pct),
                                    direction=direction,
                                    is_profitable=net_spread_pct >= threshold,
                                    detected_at=datetime.now(),
                                    notes=f"Keyword match: {common}, BF Odds: {best_back:.2f}"
                                )
                                
                                opportunities.append(opp)
                                logger.info(f"\n{opp}")
                                self._record_event(f"OPP {poly_question[:24]} | Net {float(net_spread_pct):.2f}%")
                            else:
                                logger.info("--- Status: REJECTED (Min profit not met)")
        
        self.sports_opportunities = opportunities
        self.stats['sports_opportunities'] = len(opportunities)
        
        # Show matcher stats if LLM was used
        if self.use_llm and self.sports_matcher:
            matcher_stats = self.sports_matcher.get_stats()
            logger.info(f"\n📊 LLM Matcher Stats: {matcher_stats}")
        
        return opportunities
    
    async def scan_politics_arbitrage(self) -> List[ArbitrageOpportunity]:
        """
        Scan for politics/crypto arbitrage: Polymarket ↔ SX Bet
        """
        logger.info("\n" + "=" * 60)
        logger.info("MODE B: POLITICS/CRYPTO ARBITRAGE (Polymarket ↔ SX Bet)")
        logger.info("=" * 60)
        
        if not self.sxbet:
            if not await self.init_sxbet():
                return []
        
        # Get Polymarket politics/crypto markets
        poly_politics = await self.get_polymarket_politics()
        
        if not poly_politics:
            logger.warning("No politics/crypto markets found on Polymarket")
            return []
        
        # Get SX Bet markets with liquidity
        sx_markets = await self.sxbet.get_markets_with_liquidity(min_liquidity=50.0)
        logger.info(f"[SX Bet] Found {len(sx_markets)} markets with liquidity")
        
        self.stats['poly_markets_checked'] += len(poly_politics)
        self.stats['sxbet_markets_checked'] += len(sx_markets)
        
        opportunities = []
        
        # Match and analyze
        for poly in poly_politics[:30]:  # Limit for demo
            poly_question = poly.get('question', '')
            
            tokens = poly.get('tokens', [])
            if len(tokens) < 2:
                continue
            
            poly_yes = float(tokens[0].get('price', 0.5))
            
            for sx_market, sx_orderbook in sx_markets:
                sx_label = sx_market.label.lower()
                
                # Simple matching
                poly_terms = set(poly_question.lower().split())
                sx_terms = set(sx_label.split())
                
                common = {t for t in poly_terms.intersection(sx_terms) if len(t) > 3}
                
                if len(common) >= 1:
                    # Get SX prices
                    sx_bid = sx_orderbook.best_bid
                    sx_ask = sx_orderbook.best_ask
                    
                    # Check for arbitrage
                    # Scenario 1: Buy on Poly (cheaper) → Sell on SX
                    if poly_yes < sx_bid and sx_bid > 0:
                        spread_signed = (sx_bid - poly_yes) * 100
                        spread_pct = abs(spread_signed)
                        fee_strip = self._apply_fee_stripping(spread_signed)
                        net_signed = fee_strip["net_signed"]
                        net_spread_pct = fee_strip["net_abs"]

                        logger.info(f"\n[MATH CHECK] {poly_question[:60]}")
                        logger.info(f"--- Polymarket (Yes): Price {poly_yes:.3f}")
                        logger.info(f"--- SX Bet (Bid): {sx_bid:.3f}")
                        logger.info(f"--- Spread Gross: {spread_signed:+.2f}% | Abs: {spread_pct:.2f}%")
                        logger.info(
                            f"--- Spread Net: {float(net_signed):+.2f}% | Abs: {float(net_spread_pct):.2f}% "
                            f"(Fees {float(fee_strip['total_fees_pct']):.2f}%)"
                        )

                        if net_spread_pct >= threshold:
                            opp = ArbitrageOpportunity(
                                platform_a='polymarket',
                                platform_b='sxbet',
                                market_a_id=poly.get('condition_id', ''),
                                market_b_id=sx_market.market_hash,
                                market_name=poly_question[:60],
                                category=sx_market.sport_label or 'Politics/Crypto',
                                price_a=poly_yes,
                                price_b=sx_bid,
                                spread_pct=spread_pct,
                                net_spread_pct=float(net_spread_pct),
                                direction='buy_poly_sell_sx',
                                is_profitable=net_spread_pct >= threshold,
                                detected_at=datetime.now(),
                                notes=f"Matched: {common}"
                            )
                            opportunities.append(opp)
                            logger.info(f"\n{opp}")
                            self._record_event(f"SX OPP {poly_question[:24]} | Net {float(net_spread_pct):.2f}%")
                        else:
                            logger.info("--- Status: REJECTED (Min profit not met)")
                    
                    # Scenario 2: Buy on SX (cheaper) → Sell on Poly
                    elif sx_ask < poly_yes and sx_ask > 0:
                        spread_signed = (poly_yes - sx_ask) * 100
                        spread_pct = abs(spread_signed)
                        fee_strip = self._apply_fee_stripping(spread_signed)
                        net_signed = fee_strip["net_signed"]
                        net_spread_pct = fee_strip["net_abs"]
                        threshold = Decimal(str(self.min_spread))

                        logger.info(f"\n[MATH CHECK] {poly_question[:60]}")
                        logger.info(f"--- Polymarket (Yes): Price {poly_yes:.3f}")
                        logger.info(f"--- SX Bet (Ask): {sx_ask:.3f}")
                        logger.info(f"--- Spread Gross: {spread_signed:+.2f}% | Abs: {spread_pct:.2f}%")
                        logger.info(
                            f"--- Spread Net: {float(net_signed):+.2f}% | Abs: {float(net_spread_pct):.2f}% "
                            f"(Fees {float(fee_strip['total_fees_pct']):.2f}%)"
                        )

                        if net_spread_pct >= threshold:
                            opp = ArbitrageOpportunity(
                                platform_a='sxbet',
                                platform_b='polymarket',
                                market_a_id=sx_market.market_hash,
                                market_b_id=poly.get('condition_id', ''),
                                market_name=poly_question[:60],
                                category=sx_market.sport_label or 'Politics/Crypto',
                                price_a=sx_ask,
                                price_b=poly_yes,
                                spread_pct=spread_pct,
                                net_spread_pct=float(net_spread_pct),
                                direction='buy_sx_sell_poly',
                                is_profitable=net_spread_pct >= threshold,
                                detected_at=datetime.now(),
                                notes=f"Matched: {common}"
                            )
                            opportunities.append(opp)
                            logger.info(f"\n{opp}")
                            self._record_event(f"SX OPP {poly_question[:24]} | Net {float(net_spread_pct):.2f}%")
                        else:
                            logger.info("--- Status: REJECTED (Min profit not met)")
        
        self.politics_opportunities = opportunities
        self.stats['politics_opportunities'] = len(opportunities)
        
        return opportunities
    
    async def scan_all(self) -> Dict:
        """Run both scans."""
        self.stats['scans'] += 1
        
        sports = await self.scan_sports_arbitrage()
        politics = await self.scan_politics_arbitrage()
        
        return {
            'sports': sports,
            'politics': politics,
            'total': len(sports) + len(politics),
            'stats': self.stats
        }
    
    def print_report(self):
        """Print summary report."""
        print("\n" + "=" * 70)
        print("📊 DUAL-MODE ARBITRAGE SCAN REPORT")
        print("=" * 70)
        
        print(f"\n📈 Statistics:")
        print(f"   Total Scans: {self.stats['scans']}")
        print(f"   Polymarket Markets Checked: {self.stats['poly_markets_checked']}")
        print(f"   Betfair Events Checked: {self.stats['betfair_events_checked']}")
        print(f"   SX Bet Markets Checked: {self.stats['sxbet_markets_checked']}")
        
        # LLM stats
        if self.use_llm:
            print(f"\n🧠 LLM Matching Stats:")
            print(f"   LLM Matches: {self.stats['llm_matches']}")
            print(f"   Keyword Matches: {self.stats['keyword_matches']}")
            if self.sports_matcher:
                matcher_stats = self.sports_matcher.get_stats()
                print(f"   LLM Calls: {matcher_stats.get('llm_calls', 0)}")
                print(f"   Tokens Used: {matcher_stats.get('tokens_used', 0)}")
                print(f"   Guardrail Rejections: {matcher_stats.get('guardrail_rejections', 0)} (false positives caught)")
                print(f"   Cache Hit Rate: {matcher_stats.get('cache', {}).get('hit_rate', '0%')}")
        
        print(f"\n🎯 Opportunities Found:")
        print(f"   Sports (Poly ↔ Betfair): {self.stats['sports_opportunities']}")
        print(f"   Politics/Crypto (Poly ↔ SX Bet): {self.stats['politics_opportunities']}")
        print(f"   TOTAL: {self.stats['sports_opportunities'] + self.stats['politics_opportunities']}")
        
        if self.sports_opportunities:
            print(f"\n⚽ Top Sports Opportunities:")
            for opp in sorted(self.sports_opportunities, key=lambda x: x.spread_pct, reverse=True)[:3]:
                print(f"   {opp}")
        
        if self.politics_opportunities:
            print(f"\n🏛️ Top Politics/Crypto Opportunities:")
            for opp in sorted(self.politics_opportunities, key=lambda x: x.spread_pct, reverse=True)[:3]:
                print(f"   {opp}")
        
        # Tips if no opportunities
        if not self.sports_opportunities and not self.politics_opportunities:
            print(f"\n💡 Tips:")
            print(f"   - Sports: Polymarket has long-term predictions (World Cup, Super Bowl)")
            print(f"   - Betfair: Has individual match betting")
            print(f"   - Best opportunities occur during major events")
        
        print("\n" + "=" * 70)
    
    async def _run_slow_lane(self, worker: SlowLaneWorker):
        """Background task for Slow Lane (Learning)."""
        logger.info("🐢 Slow Lane Learner started in background.")
        while True:
            try:
                # Process a batch every 30 seconds
                enriched = await worker.process_pending()
                if enriched > 0:
                    logger.info(f"🐢 Slow Lane: Learned {enriched} new mapping(s).")
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Slow Lane error: {e}")
                await asyncio.sleep(60)

    async def cleanup(self):
        """Cleanup resources."""
        if self.slow_lane_task:
            self.slow_lane_task.cancel()
        if self.sxbet:
            await self.sxbet.close()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Dual-Mode Arbitrage Scanner for Spanish Accounts"
    )
    parser.add_argument(
        '--mode',
        choices=['sports', 'politics', 'both'],
        default='both',
        help='Scan mode: sports (Betfair), politics (SX Bet), or both'
    )
    parser.add_argument(
        '--min-spread',
        type=float,
        default=1.0,
        help='Minimum spread %% to report (default: 1.0)'
    )
    parser.add_argument(
        '--min-liquidity',
        type=float,
        default=500.0,
        help='Minimum market liquidity in $ (default: 500)'
    )
    parser.add_argument(
        '--poly-fee-pct',
        type=float,
        default=0.5,
        help='Polymarket fee percentage (default: 0.5)'
    )
    parser.add_argument(
        '--betfair-commission-pct',
        type=float,
        default=6.5,
        help='Betfair commission percentage (default: 6.5)'
    )
    parser.add_argument(
        '--gas-fee-pct',
        type=float,
        default=0.0,
        help='Estimated gas fee percentage (default: 0.0)'
    )
    parser.add_argument(
        '--slippage-pct',
        type=float,
        default=0.0,
        help='Slippage buffer percentage (default: 0.0)'
    )
    parser.add_argument(
        '--use-llm',
        action='store_true',
        help='Enable LLM (MiMo-V2-Flash) for intelligent market matching'
    )
    parser.add_argument(
        '--no-filter',
        action='store_true',
        help='Disable keyword pre-filter - LLM checks ALL Betfair events (more expensive but more thorough)'
    )
    parser.add_argument(
        '--debug-math',
        '--show-negative', # Alias for user request
        action='store_true',
        help='Show all matched market prices even if not profitable'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable Mega Debugger (Full Traceability)'
    )
    parser.add_argument(
        '--force-test',
        action='store_true',
        help='Inject forced test scenarios (skip external APIs)'
    )
    parser.add_argument(
        '--force-match',
        type=str,
        help='Force matching for a specific team name (ignores common filters)'
    )
    parser.add_argument(
        '--tui',
        action='store_true',
        help='Enable real-time terminal dashboard (Rich)'
    )
    
    args = parser.parse_args()
    
    # --no-filter implies --use-llm
    if args.no_filter:
        args.use_llm = True
    
    print("\n" + "=" * 70)
    print("🤖 APU DUAL-MODE ARBITRAGE SCANNER")
    print("=" * 70)
    print(f"   Mode: {args.mode.upper()}")
    print(f"   Min Spread: {args.min_spread}%")
    print(f"   Min Liquidity: ${args.min_liquidity}")
    print(
        "   Fees: Poly "
        f"{args.poly_fee_pct:.2f}% | Betfair {args.betfair_commission_pct:.2f}% | "
        f"Gas {args.gas_fee_pct:.2f}% | Slippage {args.slippage_pct:.2f}%"
    )
    if args.use_llm:
        if args.no_filter:
            print(f"   🧠 LLM Matching: FULL MODE (no pre-filter)")
        else:
            print(f"   🧠 LLM Matching: ENABLED (with keyword pre-filter)")
    print("=" * 70)
    
    dashboard = TerminalDashboard() if args.tui else None
    if dashboard:
        dashboard.start()
        dashboard.update_summary(balance=0.0, pnl_daily=0.0, exposure=0.0)
        dashboard.update_websocket_status("unknown")

    scanner = DualArbitrageScanner(
        min_spread_pct=args.min_spread,
        min_liquidity=args.min_liquidity,
        use_llm=args.use_llm,
        skip_prefilter=args.no_filter,
        debug_math=args.debug_math,
        force_match_team=args.force_match,
        poly_fee_pct=args.poly_fee_pct,
        betfair_commission_pct=args.betfair_commission_pct,
        gas_fee_pct=args.gas_fee_pct,
        slippage_pct=args.slippage_pct,
        dashboard=dashboard
    )
    
    try:
        if args.force_test:
            await scanner.run_force_test()
        else:
            if args.mode == 'sports':
                await scanner.scan_sports_arbitrage()
            elif args.mode == 'politics':
                await scanner.scan_politics_arbitrage()
            else:
                await scanner.scan_all()
        
        scanner.print_report()
        
    finally:
        await scanner.cleanup()
        if dashboard:
            dashboard.stop()
        
        # FINAL MEGA DEBUGGER REPORT (NEW)
        if args.debug:
            report_path = scanner.audit.generate_html_report()
            if report_path:
                print(f"\n📊 MEGA DEBUGGER: Final report generated at {os.path.abspath(report_path)}")
                # On Windows, we could try opening it automatically, but let's just print the path.


if __name__ == "__main__":
    asyncio.run(main())

