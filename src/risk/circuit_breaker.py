import json
import os
import logging
import math
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """
    Capital Protection System (Fail-Closed Design).
    Stops trading if:
    1. Daily Drawdown > 5%
    2. RPC Error Rate > 20%
    3. Balance cannot be verified (NaN/None -> assumes 0, triggers shutdown)
    """
    
    def __init__(self, state_file: str = "breaker_state.json", initial_capital: float = 1000.0):
        self.state_file = state_file
        self.initial_capital = initial_capital
        self.max_drawdown_pct = 0.05 # 5%
        self.max_error_rate_pct = 0.20 # 20%
        self.min_safe_balance = 10.0  # Hard stop threshold
        
        self.state = self._load_state()
        
    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    # Reset if new day
                    if data.get('date') != datetime.now(timezone.utc).strftime('%Y-%m-%d'):
                        return self._reset_state()
                    # Validate loaded balance (fix NaN issue)
                    data['current_balance'] = self._validate_balance(data.get('current_balance'))
                    return data
            except:
                return self._reset_state()
        else:
            return self._reset_state()
            
    def _reset_state(self):
        return {
            "date": datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            "start_day_balance": self.initial_capital,
            "current_balance": self.initial_capital,
            "total_tx_attempts": 0,
            "failed_tx_attempts": 0,
            "is_broken": False,
            "broken_reason": None,
            "last_heartbeat": datetime.now(timezone.utc).isoformat()
        }

    def _save_state(self):
        # Validate before saving
        self.state['current_balance'] = self._validate_balance(self.state.get('current_balance'))
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f)

    def _validate_balance(self, balance: Optional[float]) -> float:
        """
        Type Guard: Ensures balance is always a valid float.
        FAIL-CLOSED: Invalid balance -> 0.0 (triggers safety shutdown)
        """
        if balance is None:
            logger.warning("⚠️ Balance is None - assuming 0.0 (FAIL-CLOSED)")
            return 0.0
        
        try:
            bal = float(balance)
            if math.isnan(bal) or math.isinf(bal):
                logger.warning(f"⚠️ Balance is {balance} (invalid) - assuming 0.0 (FAIL-CLOSED)")
                return 0.0
            return bal
        except (TypeError, ValueError):
            logger.warning(f"⚠️ Balance '{balance}' cannot be converted - assuming 0.0 (FAIL-CLOSED)")
            return 0.0

    def update_balance(self, new_balance: Optional[float]):
        """Update balance with validation."""
        validated = self._validate_balance(new_balance)
        self.state['current_balance'] = validated
        self.state['last_heartbeat'] = datetime.now(timezone.utc).isoformat()
        
        # Check for critical low balance
        if validated < self.min_safe_balance:
            self.trip(f"EMERGENCY: Balance ${validated:.2f} below minimum ${self.min_safe_balance}")
            
        self._check_drawdown()
        self._save_state()

    def heartbeat(self, balance_fetcher=None):
        """
        Periodic health check. Call every 30s.
        If balance_fetcher is provided, updates balance.
        """
        self.state['last_heartbeat'] = datetime.now(timezone.utc).isoformat()
        
        if balance_fetcher:
            try:
                new_bal = balance_fetcher()
                self.update_balance(new_bal)
            except Exception as e:
                logger.error(f"Heartbeat balance fetch failed: {e}")
                # Fail-closed: if we can't verify, assume worst case
                self.update_balance(0.0)
        
        self._save_state()

    def record_tx(self, success: bool):
        self.state['total_tx_attempts'] += 1
        if not success:
            self.state['failed_tx_attempts'] += 1
        self._check_health()
        self._save_state()
        
    def _check_drawdown(self):
        start = self._validate_balance(self.state.get('start_day_balance'))
        curr = self._validate_balance(self.state.get('current_balance'))
        
        if start <= 0:
            return  # Can't calculate drawdown without starting balance
            
        loss = start - curr
        if loss > 0 and (loss / start) > self.max_drawdown_pct:
            self.trip(f"Drawdown Limit Hit: {(loss/start)*100:.2f}% > {self.max_drawdown_pct*100}%")

    def _check_health(self):
        total = self.state['total_tx_attempts']
        if total < 10: return # Warmup
        
        rate = self.state['failed_tx_attempts'] / total
        if rate > self.max_error_rate_pct:
            self.trip(f"Error Rate Limit Hit: {rate*100:.2f}% > {self.max_error_rate_pct*100}%")

    def trip(self, reason: str):
        self.state['is_broken'] = True
        self.state['broken_reason'] = reason
        self._save_state()
        logger.critical(f"🛑 CIRCUIT BREAKER TRIPPED: {reason}")
        
    def can_trade(self) -> bool:
        # Also check if balance is valid (fail-closed)
        balance = self._validate_balance(self.state.get('current_balance'))
        if balance < self.min_safe_balance:
            return False
        return not self.state['is_broken']
    
    def get_safe_balance(self) -> float:
        """Returns validated current balance."""
        return self._validate_balance(self.state.get('current_balance'))

