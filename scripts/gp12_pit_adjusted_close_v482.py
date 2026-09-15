from __future__ import annotations

import datetime as dt
import math


def _date(value, label: str) -> str:
    text = str(value or '')[:10]
    try:
        dt.date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f'{label} must be YYYY-MM-DD') from exc
    return text


def validate_event_availability(event: dict) -> dict:
    if not isinstance(event, dict):
        raise ValueError('event must be an object')
    symbol = str(event.get('symbol') or '').upper()
    if not symbol:
        raise ValueError('event symbol is required')
    ex_date = _date(event.get('ex_date'), 'ex_date')
    availability_date = _date(event.get('availability_date'), 'availability_date')
    ratio = float(event.get('event_ratio'))
    if not math.isfinite(ratio) or ratio <= 0:
        raise ValueError('event_ratio must be positive finite')
    if availability_date > ex_date:
        raise ValueError(f'EVENT_NOT_PIT_AVAILABLE:{symbol}:{ex_date}:{availability_date}')
    return {
        'symbol': symbol,
        'ex_date': ex_date,
        'availability_date': availability_date,
        'event_ratio': ratio,
    }
