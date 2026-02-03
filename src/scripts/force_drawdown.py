import sys
import os
import logging

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.risk.circuit_breaker import CircuitBreaker

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ForceDrawdown")

def main():
    logger.info("😈 SIMULATING CATASTROPHIC MARKET EVENT...")
    
    # Initialize Breaker (loads existing state)
    breaker = CircuitBreaker()
    
    logger.info(f"Initial Balance: ${breaker.state['current_balance']}")
    
    # Force Drop
    # Max DD is 5%. We burn 6%.
    # If start is 1000, we need to drop to 940.
    start_bal = breaker.state['start_day_balance']
    target_bal = start_bal * 0.94 # -6%
    
    logger.info(f"Forcing balance to ${target_bal}...")
    breaker.update_balance(target_bal)
    
    if not breaker.can_trade():
        logger.info("✅ SUCCESS: Circuit Breaker TRIPPED!")
        logger.info(f"Reason: {breaker.state['broken_reason']}")
    else:
        logger.error("❌ FAILURE: Circuit Breaker DID NOT TRIP!")
        sys.exit(1)

if __name__ == "__main__":
    main()
