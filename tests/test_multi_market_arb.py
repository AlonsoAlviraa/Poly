"""
Tests for Multi-Market Arbitrage Detection.
"""

import pytest
import numpy as np

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.math.multi_market_arb import (
    MultiMarketArbitrageDetector,
    LogicalConstraint,
    CrossMarketPolytope
)


class TestSumToOneViolations:
    """Test detection of sum-to-one arbitrage opportunities."""
    
    def test_detect_overpriced_market(self):
        """Should detect when Yes + No > 1.0"""
        detector = MultiMarketArbitrageDetector(min_profit_threshold=0.005)
        
        detector.add_market('market_1', [
            {'token_id': 'yes_1', 'outcome': 'Yes', 'price': 0.55},
            {'token_id': 'no_1', 'outcome': 'No', 'price': 0.50}  # Sum = 1.05
        ])
        
        opps = detector.detect_sum_to_one_violations()
        
        assert len(opps) == 1
        assert opps[0].constraint_violated == 'sum_exceeds_one'
        assert opps[0].sides == ['sell', 'sell']
        assert opps[0].expected_profit_pct > 0.04
    
    def test_detect_underpriced_market(self):
        """Should detect when Yes + No < 1.0"""
        detector = MultiMarketArbitrageDetector(min_profit_threshold=0.005)
        
        detector.add_market('market_1', [
            {'token_id': 'yes_1', 'outcome': 'Yes', 'price': 0.45},
            {'token_id': 'no_1', 'outcome': 'No', 'price': 0.50}  # Sum = 0.95
        ])
        
        opps = detector.detect_sum_to_one_violations()
        
        assert len(opps) == 1
        assert opps[0].constraint_violated == 'sum_below_one'
        assert opps[0].sides == ['buy', 'buy']
        assert opps[0].expected_profit_pct >= 0.05
    
    def test_no_arb_for_fair_market(self):
        """Should not detect arb when prices sum to 1.0"""
        detector = MultiMarketArbitrageDetector(min_profit_threshold=0.01)
        
        detector.add_market('market_1', [
            {'token_id': 'yes_1', 'outcome': 'Yes', 'price': 0.50},
            {'token_id': 'no_1', 'outcome': 'No', 'price': 0.50}  # Sum = 1.0
        ])
        
        opps = detector.detect_sum_to_one_violations()
        
        assert len(opps) == 0


class TestImplicationViolations:
    """Test detection of cross-market implication arbitrage."""
    
    def test_detect_implication_violation(self):
        """Should detect when P(B) > P(A) but A implies B."""
        detector = MultiMarketArbitrageDetector(min_profit_threshold=0.005)
        
        # "Team wins" (market_1) implies "Team plays" (market_2)
        # So P(wins) <= P(plays)
        detector.add_market('market_1', [
            {'token_id': 'wins', 'outcome': 'Yes', 'price': 0.60}
        ])
        
        detector.add_market('market_2', [
            {'token_id': 'plays', 'outcome': 'Yes', 'price': 0.40}  # Violation!
        ])
        
        # Add constraint: plays should imply wins
        detector.add_constraint(LogicalConstraint(
            outcome_a='plays',  # Implied by
            outcome_b='wins',   # Implies
            relation='implies',
            expected_diff=0.0
        ))
        
        opps = detector.detect_cross_market_implication_violations()
        
        assert len(opps) == 1
        assert 'implication_violated' in opps[0].constraint_violated
        assert opps[0].expected_profit_pct > 0.19  # 0.60 - 0.40 = 0.20 (with float precision)


class TestExclusiveViolations:
    """Test detection of mutually exclusive event arbitrage."""
    
    def test_detect_exclusive_overpriced(self):
        """Should detect when exclusive events sum to > 1.0"""
        detector = MultiMarketArbitrageDetector(min_profit_threshold=0.005)
        
        # "Trump wins" and "Harris wins" are exclusive
        detector.add_market('trump_market', [
            {'token_id': 'trump', 'outcome': 'Trump', 'price': 0.55}
        ])
        
        detector.add_market('harris_market', [
            {'token_id': 'harris', 'outcome': 'Harris', 'price': 0.50}
        ])
        
        detector.add_constraint(LogicalConstraint(
            outcome_a='trump',
            outcome_b='harris',
            relation='exclusive'
        ))
        
        opps = detector.detect_exclusive_violations()
        
        assert len(opps) == 1
        assert opps[0].sides == ['sell', 'sell']
        assert opps[0].expected_profit_pct >= 0.05


class TestCrossMarketPolytope:
    """Test the cross-market constraint polytope projection."""
    
    def test_project_sum_constraint(self):
        """Should project prices to satisfy sum constraint."""
        polytope = CrossMarketPolytope({
            'market_1': ['yes_1', 'no_1']
        })
        
        polytope.add_sum_constraint(['yes_1', 'no_1'], target=1.0)
        
        # Prices that don't sum to 1
        prices = np.array([0.55, 0.55])  # Sum = 1.1
        
        projected = polytope.project(prices)
        
        # Should now sum to 1.0
        assert abs(projected.sum() - 1.0) < 0.01
    
    def test_project_implication_constraint(self):
        """Should project prices to satisfy implication."""
        polytope = CrossMarketPolytope({
            'market_1': ['wins'],
            'market_2': ['wins_big']
        })
        
        # P(wins) >= P(wins_big)
        polytope.add_implication_constraint('wins', 'wins_big', min_diff=0.0)
        
        # Violation: wins_big > wins
        prices = np.array([0.40, 0.60])
        
        projected = polytope.project(prices)
        
        # Should satisfy: projected[0] >= projected[1]
        assert projected[0] >= projected[1] - 0.01
    
    def test_find_arbitrage_detects_opportunity(self):
        """Should find arbitrage opportunity from price deviation."""
        polytope = CrossMarketPolytope({
            'market_1': ['yes', 'no']
        })
        
        polytope.add_sum_constraint(['yes', 'no'], target=1.0)
        
        # Mispriced market
        prices = np.array([0.30, 0.50])  # Sum = 0.80, underpriced
        
        arb = polytope.find_arbitrage(prices)
        
        assert arb is not None
        assert arb['expected_edge'] > 0.05


class TestScanAll:
    """Test the combined scan functionality."""
    
    def test_scan_all_returns_sorted_opportunities(self):
        """Should return all opportunities sorted by profit."""
        detector = MultiMarketArbitrageDetector(min_profit_threshold=0.005)
        
        # Add two markets with different arb amounts
        detector.add_market('market_1', [
            {'token_id': 'yes_1', 'outcome': 'Yes', 'price': 0.55},
            {'token_id': 'no_1', 'outcome': 'No', 'price': 0.50}  # 5% arb
        ])
        
        detector.add_market('market_2', [
            {'token_id': 'yes_2', 'outcome': 'Yes', 'price': 0.30},
            {'token_id': 'no_2', 'outcome': 'No', 'price': 0.60}  # 10% arb
        ])
        
        opps = detector.scan_all()
        
        assert len(opps) >= 2
        # Should be sorted by profit (highest first)
        for i in range(len(opps) - 1):
            assert opps[i].expected_profit_pct >= opps[i+1].expected_profit_pct


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
