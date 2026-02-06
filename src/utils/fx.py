
from decimal import Decimal

def convert_amount(amount: float, from_currency: str, to_currency: str) -> float:
    """
    Simulates FX conversion. 
    In usage, this would query an oracle. For now, fixed rates.
    """
    if from_currency == to_currency:
        return amount
        
    # Fixed illustrative rates
    rates = {
        "USD": 1.0,
        "EUR": 0.92,
        "GBP": 0.78
    }
    
    # Base USD conversion
    usd_val = amount / rates.get(from_currency, 1.0)
    target_val = usd_val * rates.get(to_currency, 1.0)
    
    return round(target_val, 2)
