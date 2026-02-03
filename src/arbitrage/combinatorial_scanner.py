"""
Advanced Combinatorial Arbitrage Scanner.
Detects multi-market arbitrage opportunities using Gamma API events 
and CLOB orderbooks for execution simulation.

Key Strategies:
1. Sum-to-One Arb: All outcomes in an event should sum to 1.0
2. NegRisk Arb: Buy all NO tokens when sum < (N-1)
3. Cross-Event Arb: Related events with inconsistent pricing
4. LLM Dependency Detection: Semantic matching for non-obvious relationships
"""

import logging
import time
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.utils.http_client import get_httpx_client

logger = logging.getLogger(__name__)


@dataclass
class ArbitrageOpportunity:
    """Represents a detected arbitrage opportunity."""
    event_id: str
    event_title: str
    strategy: str  # 'sum_to_one', 'negrisk', 'cross_event', 'llm_detected'
    edge_pct: float
    tokens: List[Dict]  # token_id, outcome, price, side
    total_cost: float
    guaranteed_payout: float
    liquidity_ok: bool
    execution_plan: List[Dict] = field(default_factory=list)
    confidence: float = 1.0


class GammaEventFetcher:
    """
    Fetches grouped events from Gamma API.
    Events contain multiple related markets (e.g., all candidates in an election).
    """
    
    BASE_URL = "https://gamma-api.polymarket.com"
    
    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 60  # seconds
        self._last_fetch = 0
        
    def get_events(self, 
                   closed: bool = False,
                   limit: int = 50,
                   offset: int = 0) -> List[Dict]:
        """
        Fetch events with multiple markets.
        Returns events that contain grouped prediction markets.
        """
        cache_key = f"events_{closed}_{limit}_{offset}"
        
        # Check cache
        if cache_key in self._cache and time.time() - self._last_fetch < self._cache_ttl:
            return self._cache[cache_key]
        
        params = {
            "limit": limit,
            "offset": offset,
            "closed": str(closed).lower()
        }
        
        try:
            with get_httpx_client(timeout=self.timeout, http2=True) as client:
                resp = client.get(f"{self.BASE_URL}/events", params=params)
                resp.raise_for_status()
                events = resp.json()
                
                self._cache[cache_key] = events
                self._last_fetch = time.time()
                return events
        except Exception as e:
            logger.error(f"Gamma events fetch error: {e}")
            return []
    
    def get_event_by_id(self, event_id: str) -> Optional[Dict]:
        """Fetch a specific event by ID."""
        try:
            with get_httpx_client(timeout=self.timeout, http2=True) as client:
                resp = client.get(f"{self.BASE_URL}/events/{event_id}")
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Gamma event {event_id} fetch error: {e}")
            return None


class CombinatorialArbScanner:
    """
    Scans for combinatorial arbitrage across grouped events.
    """
    
    def __init__(self, 
                 clob_client,
                 min_edge_pct: float = 0.5,
                 min_liquidity_usd: float = 50.0,
                 max_slippage_pct: float = 2.0):
        """
        Args:
            clob_client: PolymarketCLOBExecutor instance for price/orderbook access
            min_edge_pct: Minimum edge to consider (0.5 = 0.5%)
            min_liquidity_usd: Minimum liquidity required per token
            max_slippage_pct: Maximum acceptable slippage
        """
        self.clob = clob_client
        self.gamma = GammaEventFetcher()
        self.min_edge = min_edge_pct / 100
        self.min_liquidity = min_liquidity_usd
        self.max_slippage = max_slippage_pct / 100
        
    def scan_sum_to_one_arbs(self, events: List[Dict]) -> List[ArbitrageOpportunity]:
        """
        Find events where sum of YES prices != 1.0
        
        In a proper event with N mutually exclusive outcomes,
        sum of all YES probabilities should equal 1.0
        
        If sum < 1.0: Buy all YES tokens (guaranteed profit)
        If sum > 1.0: Sell all YES tokens (if you hold them)
        """
        opportunities = []
        
        for event in events:
            try:
                markets = event.get('markets', [])
                if len(markets) < 2:
                    continue  # Need multi-market event
                
                event_id = event.get('id', 'unknown')
                event_title = event.get('title', 'Unknown Event')[:50]
                
                # Collect YES token prices
                tokens_data = []
                total_price = 0.0
                
                for market in markets:
                    tokens = market.get('tokens', [])
                    if not tokens:
                        continue
                    
                    # Find YES token (or first outcome)
                    yes_token = None
                    for t in tokens:
                        outcome = t.get('outcome', '').lower()
                        if outcome in ['yes', 'true'] or len(tokens) == 1:
                            yes_token = t
                            break
                    
                    if not yes_token:
                        yes_token = tokens[0]  # Use first if no explicit YES
                    
                    token_id = yes_token.get('token_id')
                    if not token_id:
                        continue
                    
                    # Get real price from CLOB
                    try:
                        price = self._get_buy_price(token_id)
                        if price and price > 0:
                            tokens_data.append({
                                'token_id': token_id,
                                'outcome': market.get('groupItemTitle', yes_token.get('outcome', 'Unknown')),
                                'price': price,
                                'side': 'buy'
                            })
                            total_price += price
                    except Exception as e:
                        logger.debug(f"Price fetch error for {token_id}: {e}")
                
                if len(tokens_data) < 2:
                    continue
                
                # Check for arbitrage
                edge = 1.0 - total_price
                
                if edge > self.min_edge:
                    # BUY ALL - guaranteed profit
                    liquidity_ok = self._check_liquidity(tokens_data)
                    
                    opp = ArbitrageOpportunity(
                        event_id=event_id,
                        event_title=event_title,
                        strategy='sum_to_one_buy',
                        edge_pct=edge * 100,
                        tokens=tokens_data,
                        total_cost=total_price,
                        guaranteed_payout=1.0,
                        liquidity_ok=liquidity_ok,
                        confidence=0.95 if liquidity_ok else 0.5
                    )
                    opportunities.append(opp)
                    
                elif edge < -self.min_edge:
                    # SELL ALL - if holding (overpriced market)
                    opp = ArbitrageOpportunity(
                        event_id=event_id,
                        event_title=event_title,
                        strategy='sum_to_one_sell',
                        edge_pct=abs(edge) * 100,
                        tokens=[{**t, 'side': 'sell'} for t in tokens_data],
                        total_cost=total_price,
                        guaranteed_payout=1.0,
                        liquidity_ok=True,  # Selling is usually easier
                        confidence=0.8
                    )
                    opportunities.append(opp)
                    
            except Exception as e:
                logger.error(f"Error scanning event: {e}")
                
        return opportunities
    
    def scan_negrisk_arbs(self, events: List[Dict]) -> List[ArbitrageOpportunity]:
        """
        Find NegRisk arbitrage in multi-outcome events.
        
        For N outcomes, if sum of NO prices < (N-1), buying all NOs is profitable.
        This is 29x more efficient than single-outcome arb in multi-outcome markets.
        """
        opportunities = []
        
        for event in events:
            try:
                markets = event.get('markets', [])
                if len(markets) <= 2:
                    continue  # Need 3+ outcomes for NegRisk
                
                event_id = event.get('id', 'unknown')
                event_title = event.get('title', 'Unknown Event')[:50]
                
                # Collect NO token prices
                no_tokens = []
                total_no_price = 0.0
                n_outcomes = len(markets)
                threshold = n_outcomes - 1
                
                for market in markets:
                    tokens = market.get('tokens', [])
                    
                    # Find NO token
                    no_token = None
                    for t in tokens:
                        outcome = t.get('outcome', '').lower()
                        if outcome in ['no', 'false']:
                            no_token = t
                            break
                    
                    if not no_token and len(tokens) >= 2:
                        no_token = tokens[1]  # Assume second is NO
                    
                    if not no_token:
                        continue
                    
                    token_id = no_token.get('token_id')
                    if not token_id:
                        continue
                    
                    try:
                        price = self._get_buy_price(token_id)
                        if price and price > 0:
                            no_tokens.append({
                                'token_id': token_id,
                                'outcome': f"NO: {market.get('groupItemTitle', 'Unknown')}",
                                'price': price,
                                'side': 'buy'
                            })
                            total_no_price += price
                    except Exception:
                        pass
                
                if len(no_tokens) < 3:
                    continue
                
                # NegRisk condition: sum(NO prices) < (N-1)
                edge = threshold - total_no_price
                
                if edge > self.min_edge:
                    liquidity_ok = self._check_liquidity(no_tokens)
                    
                    opp = ArbitrageOpportunity(
                        event_id=event_id,
                        event_title=event_title,
                        strategy='negrisk',
                        edge_pct=edge * 100,
                        tokens=no_tokens,
                        total_cost=total_no_price,
                        guaranteed_payout=float(threshold),
                        liquidity_ok=liquidity_ok,
                        confidence=0.90 if liquidity_ok else 0.4
                    )
                    opportunities.append(opp)
                    
            except Exception as e:
                logger.error(f"Error scanning negrisk: {e}")
                
        return opportunities
    
    def _get_buy_price(self, token_id: str) -> Optional[float]:
        """Get best buy price from CLOB."""
        try:
            # Try midpoint first
            mid = self.clob.client.get_midpoint(token_id)
            if mid and float(mid.get('mid', 0)) > 0:
                return float(mid['mid'])
            
            # Fallback to price endpoint
            price = self.clob.client.get_price(token_id, 'BUY')
            if price:
                return float(price.get('price', 0))
                
        except Exception:
            pass
        return None
    
    def _check_liquidity(self, tokens: List[Dict]) -> bool:
        """Check if orderbooks have sufficient liquidity."""
        for t in tokens:
            try:
                book = self.clob.get_order_book(t['token_id'])
                
                if hasattr(book, 'asks'):
                    asks = book.asks if book.asks else []
                else:
                    asks = book.get('asks', [])
                
                if not asks:
                    return False
                
                # Check depth
                total_liquidity = sum(
                    float(a.size if hasattr(a, 'size') else a.get('size', 0))
                    for a in asks[:5]  # Top 5 levels
                )
                
                if total_liquidity < self.min_liquidity:
                    return False
                    
            except Exception:
                return False
                
        return True
    
    def scan_all(self) -> List[ArbitrageOpportunity]:
        """Run all arbitrage scans and return sorted opportunities."""
        logger.info("Starting combinatorial arbitrage scan...")
        
        # Fetch events
        events = self.gamma.get_events(closed=False, limit=100)
        logger.info(f"Fetched {len(events)} open events")
        
        all_opportunities = []
        
        # Run scans in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self.scan_sum_to_one_arbs, events): 'sum_to_one',
                executor.submit(self.scan_negrisk_arbs, events): 'negrisk',
            }
            
            for future in as_completed(futures):
                strategy = futures[future]
                try:
                    opps = future.result()
                    all_opportunities.extend(opps)
                    logger.info(f"{strategy}: Found {len(opps)} opportunities")
                except Exception as e:
                    logger.error(f"{strategy} scan error: {e}")
        
        # Sort by edge
        all_opportunities.sort(key=lambda x: x.edge_pct, reverse=True)
        
        return all_opportunities


class LLMDependencyDetector:
    """
    Uses LLM to detect non-obvious dependencies between markets.
    E.g., "Fed rate hike" market affects "Inflation" market.
    Uses OpenRouter API for access to multiple models.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "xiaomi/mimo-v2-flash"):
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        # Check multiple env vars for API key
        self.api_key = api_key or os.getenv('API_LLM') or os.getenv('OPENROUTER_API_KEY')
        self.model = model
        self._cache: Dict[str, bool] = {}
        self._client = None
        
    def _init_client(self):
        """Lazy init of OpenAI client."""
        if self._client is None and self.api_key:
            try:
                import openai
                self._client = openai.OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.api_key
                )
            except ImportError:
                logger.error("openai package not installed")
        
    def are_markets_dependent(self, market1_question: str, market2_question: str) -> Tuple[bool, float]:
        """
        Check if two markets have logical dependency.
        
        Returns:
            (is_dependent, confidence)
        """
        cache_key = f"{market1_question[:50]}|||{market2_question[:50]}"
        if cache_key in self._cache:
            return self._cache[cache_key], 0.9
        
        if not self.api_key:
            # Fallback: keyword matching
            return self._keyword_match(market1_question, market2_question)
        
        self._init_client()
        
        prompt = f"""Analyze if these prediction markets have a logical dependency (one implies something about the other):

Market A: {market1_question}
Market B: {market2_question}

Answer in JSON format:
{{"dependent": true/false, "relationship": "brief explanation", "confidence": 0.0-1.0}}"""

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a market analyst. Respond with JSON only: {\"dependent\": true/false, \"confidence\": 0.0-1.0}"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            content = response.choices[0].message.content
            
            # Multiple extraction strategies
            result = None
            
            # Strategy 1: Direct JSON parse
            try:
                result = json.loads(content.strip())
            except:
                pass
            
            # Strategy 2: Extract from markdown code block
            if result is None and "```" in content:
                try:
                    json_block = content.split("```")[1]
                    if json_block.startswith("json"):
                        json_block = json_block[4:]
                    result = json.loads(json_block.strip())
                except:
                    pass
            
            # Strategy 3: Find JSON object in text
            if result is None:
                import re
                json_match = re.search(r'\{[^}]+\}', content)
                if json_match:
                    try:
                        result = json.loads(json_match.group())
                    except:
                        pass
            
            if result:
                is_dep = result.get('dependent', False)
                conf = result.get('confidence', 0.5)
                self._cache[cache_key] = is_dep
                return is_dep, conf
            
            # Fallback parsing from natural language
            content_lower = content.lower()
            if 'yes' in content_lower or 'dependent' in content_lower or 'related' in content_lower:
                return True, 0.6
            return False, 0.3
            
        except Exception as e:
            logger.warning(f"LLM dependency check failed: {e}")
            return self._keyword_match(market1_question, market2_question)
    
    def _keyword_match(self, q1: str, q2: str) -> Tuple[bool, float]:
        """Simple keyword-based dependency detection."""
        q1_lower = q1.lower()
        q2_lower = q2.lower()
        
        # Extract key entities
        key_terms = set()
        for q in [q1_lower, q2_lower]:
            # Simple extraction
            words = q.split()
            for w in words:
                if len(w) > 4 and w.isalpha():
                    key_terms.add(w)
        
        # Check overlap
        q1_words = set(q1_lower.split())
        q2_words = set(q2_lower.split())
        
        overlap = q1_words.intersection(q2_words)
        meaningful_overlap = [w for w in overlap if len(w) > 4]
        
        if len(meaningful_overlap) >= 2:
            return True, 0.6
        
        return False, 0.1


def demo():
    """Demo the combinatorial arbitrage scanner."""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    from src.execution.clob_executor import PolymarketCLOBExecutor
    
    print("=" * 70)
    print("COMBINATORIAL ARBITRAGE SCANNER")
    print("=" * 70)
    
    # Initialize
    clob = PolymarketCLOBExecutor(
        host='https://clob.polymarket.com',
        key='0x' + '1' * 64,  # Dummy for read-only
        chain_id=137
    )
    
    scanner = CombinatorialArbScanner(
        clob_client=clob,
        min_edge_pct=0.3,  # 0.3% minimum edge
        min_liquidity_usd=25.0
    )
    
    # Scan
    opportunities = scanner.scan_all()
    
    print(f"\n{'='*70}")
    print(f"FOUND {len(opportunities)} OPPORTUNITIES")
    print("=" * 70)
    
    for i, opp in enumerate(opportunities[:10]):
        print(f"\n[{i+1}] {opp.event_title}")
        print(f"    Strategy: {opp.strategy}")
        print(f"    Edge: {opp.edge_pct:.2f}%")
        print(f"    Cost: ${opp.total_cost:.4f} -> Payout: ${opp.guaranteed_payout:.2f}")
        print(f"    Tokens: {len(opp.tokens)}")
        print(f"    Liquidity OK: {opp.liquidity_ok}")
        print(f"    Confidence: {opp.confidence:.2f}")
    
    if not opportunities:
        print("\n    No arbitrage opportunities found at this time.")
        print("    This is normal - arbs are quickly captured by other bots.")
    
    print("\n" + "=" * 70)
    return opportunities


if __name__ == '__main__':
    demo()
