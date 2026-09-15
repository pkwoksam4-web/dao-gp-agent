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


def _positive(value, label: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f'{label} must be positive finite')
    return number


def validate_event_availability(event: dict) -> dict:
    if not isinstance(event, dict):
        raise ValueError('event must be an object')
    symbol = str(event.get('symbol') or '').upper()
    if not symbol:
        raise ValueError('event symbol is required')
    ex_date = _date(event.get('ex_date'), 'ex_date')
    availability_date = _date(event.get('availability_date'), 'availability_date')
    ratio = _positive(event.get('event_ratio'), 'event_ratio')
    if availability_date > ex_date:
        raise ValueError(f'EVENT_NOT_PIT_AVAILABLE:{symbol}:{ex_date}:{availability_date}')
    return {
        'symbol': symbol,
        'ex_date': ex_date,
        'availability_date': availability_date,
        'event_ratio': ratio,
    }


def build_forward_pit_adjusted_path(raw_rows: list[dict], events: list[dict]) -> list[dict]:
    normalized_events = sorted(
        (validate_event_availability(event) for event in events or []),
        key=lambda event: event['ex_date'],
    )
    rows = []
    previous_date = None
    for raw in raw_rows or []:
        date = _date(raw.get('date'), 'raw date')
        if previous_date is not None and date <= previous_date:
            raise ValueError('raw rows must be strictly increasing by date')
        previous_date = date
        close = _positive(raw.get('close'), 'raw close')
        cumulative = 1.0
        for event in normalized_events:
            if event['ex_date'] <= date:
                cumulative *= event['event_ratio']
        rows.append({
            'date': date,
            'raw_close': close,
            'cumulative_event_ratio': cumulative,
            'adjusted_close': close / cumulative,
        })
    return rows
