from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class ExchangeSelection:
    selection_id: str
    name: str
    price: Optional[float] = None


@dataclass
class ExchangeMarket:
    market_id: str
    event_id: str
    name: str
    market_type: str
    open_date: Optional[datetime]
    competition: Optional[str] = None
    exchange: str = "unknown"
    runners: List[ExchangeSelection] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
