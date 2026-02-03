"""
Tests for Circuit Breaker with Type Guard and Fail-Closed behavior.
"""

import pytest
import os
import json
import math
from unittest.mock import MagicMock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.risk.circuit_breaker import CircuitBreaker


class TestCircuitBreakerTypeGuard:
    """Test the balance validation and fail-closed behavior."""
    
    @pytest.fixture
    def breaker(self, tmp_path):
        """Create a CircuitBreaker with temp state file."""
        state_file = str(tmp_path / "test_breaker.json")
        return CircuitBreaker(state_file=state_file, initial_capital=1000.0)
    
    def test_validate_balance_normal(self, breaker):
        """Normal float balance should pass through."""
        assert breaker._validate_balance(500.0) == 500.0
        assert breaker._validate_balance(0.01) == 0.01
        assert breaker._validate_balance(999999.99) == 999999.99
    
    def test_validate_balance_none_returns_zero(self, breaker):
        """None balance should return 0.0 (fail-closed)."""
        result = breaker._validate_balance(None)
        assert result == 0.0
    
    def test_validate_balance_nan_returns_zero(self, breaker):
        """NaN balance should return 0.0 (fail-closed)."""
        result = breaker._validate_balance(float('nan'))
        assert result == 0.0
    
    def test_validate_balance_inf_returns_zero(self, breaker):
        """Infinity balance should return 0.0 (fail-closed)."""
        result = breaker._validate_balance(float('inf'))
        assert result == 0.0
        result = breaker._validate_balance(float('-inf'))
        assert result == 0.0
    
    def test_validate_balance_string_returns_zero(self, breaker):
        """String balance should return 0.0 (fail-closed)."""
        result = breaker._validate_balance("invalid")
        assert result == 0.0
    
    def test_validate_balance_numeric_string_converts(self, breaker):
        """Numeric string should convert successfully."""
        result = breaker._validate_balance("100.50")
        assert result == 100.50


class TestCircuitBreakerFailClosed:
    """Test that system fails closed (stops trading) when balance is invalid."""
    
    @pytest.fixture
    def breaker(self, tmp_path):
        state_file = str(tmp_path / "test_breaker.json")
        return CircuitBreaker(state_file=state_file, initial_capital=1000.0)
    
    def test_update_balance_with_none_triggers_shutdown(self, breaker):
        """Updating with None should trigger emergency shutdown."""
        breaker.update_balance(None)
        
        # Should be tripped due to balance < min_safe_balance (10)
        # Note: drawdown check runs after and may overwrite reason
        assert breaker.state['is_broken'] == True
        assert breaker.can_trade() == False
    
    def test_update_balance_with_nan_triggers_shutdown(self, breaker):
        """Updating with NaN should trigger emergency shutdown."""
        breaker.update_balance(float('nan'))
        
        assert breaker.state['is_broken'] == True
        assert breaker.can_trade() == False
    
    def test_can_trade_returns_false_for_low_balance(self, breaker):
        """can_trade() should return False when balance is too low."""
        breaker.update_balance(5.0)  # Below min_safe_balance of 10
        
        assert breaker.can_trade() == False
    
    def test_can_trade_returns_true_for_valid_balance(self, tmp_path):
        """can_trade() should return True for valid balance above threshold."""
        # Fresh breaker to avoid drawdown trigger
        state_file = str(tmp_path / "fresh_breaker.json")
        breaker = CircuitBreaker(state_file=state_file, initial_capital=500.0)
        
        # Update with same starting balance (no drawdown)
        breaker.update_balance(500.0)
        
        assert breaker.can_trade() == True


class TestCircuitBreakerHeartbeat:
    """Test the heartbeat mechanism."""
    
    @pytest.fixture
    def breaker(self, tmp_path):
        state_file = str(tmp_path / "test_breaker.json")
        return CircuitBreaker(state_file=state_file, initial_capital=1000.0)
    
    def test_heartbeat_updates_timestamp(self, breaker):
        """Heartbeat should update the last_heartbeat timestamp."""
        old_heartbeat = breaker.state.get('last_heartbeat')
        
        breaker.heartbeat()
        
        new_heartbeat = breaker.state.get('last_heartbeat')
        assert new_heartbeat is not None
        # Should have changed (or been set)
        assert new_heartbeat != old_heartbeat or old_heartbeat is None
    
    def test_heartbeat_with_fetcher_updates_balance(self, breaker):
        """Heartbeat with balance_fetcher should update balance."""
        mock_fetcher = MagicMock(return_value=750.0)
        
        breaker.heartbeat(balance_fetcher=mock_fetcher)
        
        assert breaker.state['current_balance'] == 750.0
        mock_fetcher.assert_called_once()
    
    def test_heartbeat_with_failing_fetcher_fails_closed(self, breaker):
        """If fetcher raises exception, should fail closed (set balance to 0)."""
        def failing_fetcher():
            raise Exception("API Error")
        
        breaker.heartbeat(balance_fetcher=failing_fetcher)
        
        # Should have set balance to 0 and tripped
        assert breaker.state['current_balance'] == 0.0
        assert breaker.state['is_broken'] == True


class TestCircuitBreakerStateRecovery:
    """Test state persistence and recovery."""
    
    def test_load_state_fixes_nan_balance(self, tmp_path):
        """Loading state with NaN balance should fix it."""
        state_file = str(tmp_path / "test_breaker.json")
        
        # Create state file with NaN
        from datetime import datetime, timezone
        bad_state = {
            "date": datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            "start_day_balance": 1000.0,
            "current_balance": None,  # Will become NaN-like
            "total_tx_attempts": 0,
            "failed_tx_attempts": 0,
            "is_broken": False,
            "broken_reason": None
        }
        
        with open(state_file, 'w') as f:
            json.dump(bad_state, f)
        
        # Load it
        breaker = CircuitBreaker(state_file=state_file, initial_capital=1000.0)
        
        # Balance should be fixed to 0.0
        assert breaker.state['current_balance'] == 0.0
    
    def test_get_safe_balance_always_returns_valid(self, tmp_path):
        """get_safe_balance() should always return a usable float."""
        state_file = str(tmp_path / "test_breaker.json")
        breaker = CircuitBreaker(state_file=state_file, initial_capital=1000.0)
        
        # Force invalid balance
        breaker.state['current_balance'] = float('nan')
        
        # Should return 0.0, not NaN
        result = breaker.get_safe_balance()
        assert result == 0.0
        assert not math.isnan(result)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
