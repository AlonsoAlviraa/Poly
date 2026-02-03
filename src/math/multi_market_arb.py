"""
Multi-Market Arbitrage Detector.
Finds arbitrage opportunities across related markets using logical constraints.

Key Concepts:
1. Cross-Market Arbitrage: Markets with overlapping outcomes
2. Negative Correlation: When sum of related outcomes should equal 1 but prices don't
3. Conditional Markets: "Team X wins" vs "Team X wins by +10" 
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MarketOutcome:
    """Single outcome within a market."""
    token_id: str
    outcome_name: str
    price: float
    market_id: str
    
@dataclass
class LogicalConstraint:
    """
    Represents a logical relationship between outcomes.
    Example: P(Team X wins) >= P(Team X wins by +10)
    """
    outcome_a: str  # token_id
    outcome_b: str  # token_id
    relation: str   # 'implies', 'exclusive', 'sums_to_one'
    expected_diff: float = 0.0  # For implies: min(P(A) - P(B))


@dataclass  
class ArbitrageOpportunity:
    """Detected cross-market arbitrage."""
    markets: List[str]  # condition_ids involved
    tokens: List[str]   # token_ids to trade
    sides: List[str]    # 'buy' or 'sell' for each
    expected_profit_pct: float
    constraint_violated: str
    confidence: float


class MultiMarketArbitrageDetector:
    """
    Detects arbitrage across related Polymarket markets.
    
    Strategies:
    1. Sum-to-One: Markets where outcomes should sum to 1.0
    2. Implication: P(A implies B) means P(B) >= P(A), violation = arb
    3. Exclusive: P(A) + P(B) <= 1 for mutually exclusive events
    """
    
    def __init__(self, min_profit_threshold: float = 0.01):
        self.min_profit_threshold = min_profit_threshold
        self.market_graph: Dict[str, List[MarketOutcome]] = defaultdict(list)
        self.constraints: List[LogicalConstraint] = []
        
    def add_market(self, condition_id: str, tokens: List[Dict]):
        """
        Register a market and its outcomes.
        
        Args:
            condition_id: Unique market identifier
            tokens: List of token dicts with token_id, outcome, price
        """
        for t in tokens:
            outcome = MarketOutcome(
                token_id=t.get('token_id', ''),
                outcome_name=t.get('outcome', ''),
                price=float(t.get('price', 0)),
                market_id=condition_id
            )
            self.market_graph[condition_id].append(outcome)
            
    def add_constraint(self, constraint: LogicalConstraint):
        """Add a logical constraint between markets."""
        self.constraints.append(constraint)
        
    def detect_sum_to_one_violations(self) -> List[ArbitrageOpportunity]:
        """
        Find markets where Yes/No prices don't sum to ~1.0
        This is the most common arb in binary markets.
        """
        opportunities = []
        
        for market_id, outcomes in self.market_graph.items():
            if len(outcomes) != 2:
                continue  # Only binary markets
                
            yes_price = None
            no_price = None
            yes_token = None
            no_token = None
            
            for o in outcomes:
                if o.outcome_name.lower() in ['yes', 'true', 'win']:
                    yes_price = o.price
                    yes_token = o.token_id
                elif o.outcome_name.lower() in ['no', 'false', 'lose']:
                    no_price = o.price
                    no_token = o.token_id
                    
            if yes_price is None or no_price is None:
                # Try first/second
                yes_price = outcomes[0].price
                no_price = outcomes[1].price
                yes_token = outcomes[0].token_id
                no_token = outcomes[1].token_id
                
            total = yes_price + no_price
            deviation = abs(total - 1.0)
            
            if deviation > self.min_profit_threshold:
                if total > 1.0:
                    # Sell both (overpriced)
                    profit = (total - 1.0) / total
                    opp = ArbitrageOpportunity(
                        markets=[market_id],
                        tokens=[yes_token, no_token],
                        sides=['sell', 'sell'],
                        expected_profit_pct=profit,
                        constraint_violated='sum_exceeds_one',
                        confidence=min(1.0, profit / 0.05)
                    )
                    opportunities.append(opp)
                else:
                    # Buy both (underpriced)
                    profit = (1.0 - total)
                    opp = ArbitrageOpportunity(
                        markets=[market_id],
                        tokens=[yes_token, no_token],
                        sides=['buy', 'buy'],
                        expected_profit_pct=profit,
                        constraint_violated='sum_below_one',
                        confidence=min(1.0, profit / 0.05)
                    )
                    opportunities.append(opp)
                    
        return opportunities
    
    def detect_cross_market_implication_violations(self) -> List[ArbitrageOpportunity]:
        """
        Find violations where P(A) should be >= P(B) but isn't.
        Example: "Lakers win" should be >= "Lakers win by +10 points"
        """
        opportunities = []
        
        for constraint in self.constraints:
            if constraint.relation != 'implies':
                continue
                
            # Find the outcomes
            outcome_a = self._find_outcome_by_token(constraint.outcome_a)
            outcome_b = self._find_outcome_by_token(constraint.outcome_b)
            
            if not outcome_a or not outcome_b:
                continue
                
            # Implication violation: P(B) > P(A)
            if outcome_b.price > outcome_a.price + constraint.expected_diff:
                profit = outcome_b.price - outcome_a.price
                
                opp = ArbitrageOpportunity(
                    markets=[outcome_a.market_id, outcome_b.market_id],
                    tokens=[outcome_a.token_id, outcome_b.token_id],
                    sides=['buy', 'sell'],  # Buy cheap implicant, sell expensive
                    expected_profit_pct=profit,
                    constraint_violated=f'implication_violated:{outcome_a.outcome_name}->{outcome_b.outcome_name}',
                    confidence=min(1.0, profit / 0.03)
                )
                opportunities.append(opp)
                
        return opportunities
    
    def detect_exclusive_violations(self) -> List[ArbitrageOpportunity]:
        """
        Find violations where exclusive events sum to > 1.0
        Example: "Trump wins" + "Harris wins" > 1.0
        """
        opportunities = []
        
        for constraint in self.constraints:
            if constraint.relation != 'exclusive':
                continue
                
            outcome_a = self._find_outcome_by_token(constraint.outcome_a)
            outcome_b = self._find_outcome_by_token(constraint.outcome_b)
            
            if not outcome_a or not outcome_b:
                continue
                
            total = outcome_a.price + outcome_b.price
            
            if total > 1.0 + self.min_profit_threshold:
                profit = total - 1.0
                
                opp = ArbitrageOpportunity(
                    markets=[outcome_a.market_id, outcome_b.market_id],
                    tokens=[outcome_a.token_id, outcome_b.token_id],
                    sides=['sell', 'sell'],
                    expected_profit_pct=profit,
                    constraint_violated=f'exclusive_overpriced:{outcome_a.outcome_name}+{outcome_b.outcome_name}',
                    confidence=min(1.0, profit / 0.05)
                )
                opportunities.append(opp)
                
        return opportunities
    
    def find_related_markets(self, keyword: str) -> List[str]:
        """
        Find markets that might be logically related based on keywords.
        Useful for auto-discovering constraint opportunities.
        """
        related = []
        keyword_lower = keyword.lower()
        
        for market_id, outcomes in self.market_graph.items():
            for o in outcomes:
                if keyword_lower in o.outcome_name.lower():
                    related.append(market_id)
                    break
                    
        return related
    
    def scan_all(self) -> List[ArbitrageOpportunity]:
        """Run all arbitrage detection strategies."""
        all_opps = []
        
        all_opps.extend(self.detect_sum_to_one_violations())
        all_opps.extend(self.detect_cross_market_implication_violations())
        all_opps.extend(self.detect_exclusive_violations())
        
        # Sort by profit
        all_opps.sort(key=lambda x: x.expected_profit_pct, reverse=True)
        
        return all_opps
    
    def _find_outcome_by_token(self, token_id: str) -> Optional[MarketOutcome]:
        """Lookup outcome by token ID."""
        for outcomes in self.market_graph.values():
            for o in outcomes:
                if o.token_id == token_id:
                    return o
        return None


# Extended MarginalPolytope for cross-market constraints
class CrossMarketPolytope:
    """
    Extends MarginalPolytope to handle constraints across multiple markets.
    
    For N binary markets, the joint probability space is 2^N dimensions.
    We use sparse representations and only model interactions between
    markets we suspect have logical relationships.
    """
    
    def __init__(self, market_tokens: Dict[str, List[str]]):
        """
        Args:
            market_tokens: Dict mapping market_id -> [token_id_yes, token_id_no]
        """
        self.market_tokens = market_tokens
        self.n_markets = len(market_tokens)
        self.token_to_idx: Dict[str, int] = {}
        
        idx = 0
        for market_id, tokens in market_tokens.items():
            for t in tokens:
                self.token_to_idx[t] = idx
                idx += 1
                
        self.n_tokens = idx
        self.constraints: List[Dict] = []
        
    def add_sum_constraint(self, token_ids: List[str], target: float = 1.0):
        """
        Add constraint: sum of prices for tokens should equal target.
        Example: P(Yes) + P(No) = 1.0 for a single market
        """
        indices = [self.token_to_idx[t] for t in token_ids if t in self.token_to_idx]
        self.constraints.append({
            'type': 'sum',
            'indices': indices,
            'target': target
        })
        
    def add_implication_constraint(self, token_a: str, token_b: str, min_diff: float = 0.0):
        """
        Add constraint: P(A) >= P(B) + min_diff
        """
        if token_a in self.token_to_idx and token_b in self.token_to_idx:
            self.constraints.append({
                'type': 'implication',
                'idx_a': self.token_to_idx[token_a],
                'idx_b': self.token_to_idx[token_b],
                'min_diff': min_diff
            })
            
    def project(self, prices: np.ndarray, max_iters: int = 100) -> np.ndarray:
        """
        Project prices onto the feasible polytope defined by constraints.
        Uses iterative projection (Dykstra's algorithm).
        """
        x = prices.copy()
        
        for _ in range(max_iters):
            prev = x.copy()
            
            for c in self.constraints:
                if c['type'] == 'sum':
                    # Project onto simplex-like constraint
                    indices = c['indices']
                    target = c['target']
                    current_sum = sum(x[i] for i in indices)
                    if abs(current_sum - target) > 1e-6:
                        adjustment = (target - current_sum) / len(indices)
                        for i in indices:
                            x[i] += adjustment
                            
                elif c['type'] == 'implication':
                    # P(A) >= P(B) + min_diff
                    ia, ib = c['idx_a'], c['idx_b']
                    min_diff = c['min_diff']
                    if x[ia] < x[ib] + min_diff:
                        # Average to satisfy constraint
                        avg = (x[ia] + x[ib] + min_diff) / 2
                        x[ia] = avg
                        x[ib] = avg - min_diff
                        
            # Bound to [0, 1]
            x = np.clip(x, 0.001, 0.999)
            
            # Check convergence
            if np.max(np.abs(x - prev)) < 1e-6:
                break
                
        return x
    
    def find_arbitrage(self, prices: np.ndarray) -> Optional[Dict]:
        """
        Find the optimal arbitrage given current prices and constraints.
        Returns None if prices are already feasible.
        """
        projected = self.project(prices)
        diff = projected - prices
        
        # Significant deviation = arbitrage opportunity
        max_diff_idx = np.argmax(np.abs(diff))
        max_diff = diff[max_diff_idx]
        
        if abs(max_diff) < 0.01:
            return None  # No arb
            
        # Find token for this index
        token_id = None
        for t, idx in self.token_to_idx.items():
            if idx == max_diff_idx:
                token_id = t
                break
                
        return {
            'token_id': token_id,
            'current_price': prices[max_diff_idx],
            'fair_price': projected[max_diff_idx],
            'recommended_side': 'buy' if max_diff > 0 else 'sell',
            'expected_edge': abs(max_diff)
        }


def demo():
    """Demonstrate multi-market arbitrage detection."""
    detector = MultiMarketArbitrageDetector(min_profit_threshold=0.005)
    
    # Add sample markets
    detector.add_market('market_1', [
        {'token_id': 'yes_1', 'outcome': 'Yes', 'price': 0.55},
        {'token_id': 'no_1', 'outcome': 'No', 'price': 0.48}  # Sum = 1.03 -> arb!
    ])
    
    detector.add_market('market_2', [
        {'token_id': 'yes_2', 'outcome': 'Yes', 'price': 0.30},
        {'token_id': 'no_2', 'outcome': 'No', 'price': 0.65}  # Sum = 0.95 -> arb!
    ])
    
    # Add constraint: market_1 implies market_2 (e.g., "win by 10" implies "win")
    detector.add_constraint(LogicalConstraint(
        outcome_a='yes_2',  # "win"
        outcome_b='yes_1',  # "win by 10" 
        relation='implies',
        expected_diff=0.0
    ))
    
    opps = detector.scan_all()
    
    print("=" * 60)
    print("MULTI-MARKET ARBITRAGE SCAN")
    print("=" * 60)
    
    for i, opp in enumerate(opps):
        print(f"\n[{i+1}] {opp.constraint_violated}")
        print(f"    Tokens: {opp.tokens}")
        print(f"    Sides: {opp.sides}")
        print(f"    Expected Profit: {opp.expected_profit_pct*100:.2f}%")
        print(f"    Confidence: {opp.confidence:.2f}")


if __name__ == '__main__':
    demo()
