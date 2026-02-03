import json
from decimal import Decimal
from typing import Any


def loads_decimal(payload: str) -> Any:
    """
    Parse JSON payload using Decimal for numeric values to avoid float drift.
    """
    return json.loads(payload, parse_float=Decimal, parse_int=Decimal)
