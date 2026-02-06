from datetime import datetime
from typing import Dict, List, Optional

from src.data.exchange_contracts import ExchangeMarket, ExchangeSelection


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def adapt_betfair_market(raw: Dict) -> ExchangeMarket:
    runners = [
        ExchangeSelection(
            selection_id=str(r.get("selectionId")),
            name=r.get("runnerName", ""),
        )
        for r in raw.get("runners", [])
    ]
    return ExchangeMarket(
        market_id=str(raw.get("market_id") or raw.get("marketId") or raw.get("id") or ""),
        event_id=str(raw.get("event_id") or raw.get("eventId") or raw.get("id") or ""),
        name=raw.get("name", ""),
        market_type=raw.get("market_type", "MATCH_ODDS"),
        open_date=_parse_datetime(raw.get("open_date") or raw.get("marketStartTime")),
        competition=raw.get("competition"),
        exchange=raw.get("exchange", "bf"),
        runners=runners,
        metadata=raw,
    )


def adapt_sx_market(raw: Dict) -> ExchangeMarket:
    runners = []
    if raw.get("outcome_one"):
        runners.append(ExchangeSelection(selection_id="1", name=raw.get("outcome_one")))
    if raw.get("outcome_two"):
        runners.append(ExchangeSelection(selection_id="2", name=raw.get("outcome_two")))
    return ExchangeMarket(
        market_id=str(raw.get("market_hash") or raw.get("id") or ""),
        event_id=str(raw.get("event_id") or raw.get("id") or ""),
        name=raw.get("name", ""),
        market_type=raw.get("market_type", ""),
        open_date=_parse_datetime(raw.get("open_date")),
        competition=raw.get("competition"),
        exchange=raw.get("exchange", "sx"),
        runners=runners,
        metadata=raw,
    )


def adapt_polymarket_market(raw: Dict) -> ExchangeMarket:
    return ExchangeMarket(
        market_id=str(raw.get("id") or raw.get("condition_id") or ""),
        event_id=str(raw.get("event_id") or raw.get("id") or ""),
        name=raw.get("question", ""),
        market_type=raw.get("market_type", ""),
        open_date=_parse_datetime(raw.get("gameStartTime") or raw.get("startDate")),
        competition=raw.get("category"),
        exchange="poly",
        runners=[],
        metadata=raw,
    )
