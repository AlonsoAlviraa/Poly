
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any

@dataclass
class MarketMapping:
    polymarket_id: str
    polymarket_question: str
    betfair_event_id: str
    betfair_market_id: str
    betfair_event_name: str
    confidence: float
    mapped_at: datetime
    source: str  # 'static', 'vector', 'ai', 'cache'
    polymarket_slug: Optional[str] = None
    sx_market_id: Optional[str] = None
    bf_selection_id: Optional[str] = None
    bf_runner_name: Optional[str] = None
    exchange: str = 'bf'
    sport: str = 'unknown'
    
    def __post_init__(self):
        if isinstance(self.mapped_at, str):
            try:
                self.mapped_at = datetime.fromisoformat(self.mapped_at)
            except:
                self.mapped_at = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            'polymarket_id': self.polymarket_id,
            'polymarket_question': self.polymarket_question,
            'betfair_event_id': self.betfair_event_id,
            'betfair_market_id': self.betfair_market_id,
            'betfair_event_name': self.betfair_event_name,
            'confidence': self.confidence,
            'source': self.source,
            'mapped_at': self.mapped_at.isoformat() if isinstance(self.mapped_at, datetime) else self.mapped_at,
            'polymarket_slug': self.polymarket_slug,
            'bf_selection_id': self.bf_selection_id,
            'bf_runner_name': self.bf_runner_name,
            'exchange': self.exchange
        }

@dataclass
class ArbOpportunity:
    mapping: MarketMapping
    poly_yes_price: float
    poly_no_price: float
    betfair_back_odds: float
    betfair_lay_odds: float
    ev_net: float
    is_profitable: bool
    direction: str  # 'buy_poly_back_bf' or 'buy_poly_lay_bf'
    detected_at: datetime
    betfair_delayed: bool = True 
    
    def to_alert(self) -> str:
        return f"{self.mapping.betfair_event_name} ({getattr(self.mapping, 'market_type', 'MATCH_ODDS')}) (EV: {self.ev_net:.2f}%)"
