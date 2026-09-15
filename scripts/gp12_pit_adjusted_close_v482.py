from __future__ import annotations

import bisect
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


def resolve_final_event_availability(
    *,
    ex_date: str,
    nominal_availability_date: str,
    final_override_availability_date: str | None = None,
) -> str:
    """Return the availability date for the ratio that is actually used.

    If an event ratio was corrected by later-stage official evidence, the PIT
    clock must follow that final evidence rather than the nominal source row.
    Both dates remain fail-closed against the ex-date.
    """
    ex = _date(ex_date, 'ex_date')
    nominal = _date(nominal_availability_date, 'nominal_availability_date')
    if nominal > ex:
        raise ValueError(f'EVENT_NOT_PIT_AVAILABLE:NOMINAL:{ex}:{nominal}')
    if final_override_availability_date in (None, ''):
        return nominal
    final = _date(final_override_availability_date, 'final_override_availability_date')
    if final > ex:
        raise ValueError(f'EVENT_NOT_PIT_AVAILABLE:FINAL_OVERRIDE:{ex}:{final}')
    return final


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


def build_qfq_adjusted_path(raw_rows: list[dict], factors: list[dict]) -> list[dict]:
    factor_rows = sorted(
        (_date(row.get('d'), 'factor date'), _positive(row.get('f'), 'qfq factor'))
        for row in factors or [] if row.get('d') not in (None, '')
    )
    if not factor_rows:
        raise ValueError('qfq factor series is empty')
    factor_dates = [row[0] for row in factor_rows]
    if len(set(factor_dates)) != len(factor_dates):
        raise ValueError('qfq factor dates must be unique')
    factor_values = [row[1] for row in factor_rows]

    out = []
    previous_date = None
    for index, raw in enumerate(raw_rows or []):
        date = _date(raw.get('date'), f'raw_rows[{index}].date')
        if previous_date is not None and date <= previous_date:
            raise ValueError('raw rows must be strictly increasing by date')
        previous_date = date
        close = _positive(raw.get('close'), f'raw_rows[{index}].close')
        factor_index = bisect.bisect_right(factor_dates, date) - 1
        if factor_index < 0:
            raise ValueError(f'no qfq factor covering {date}')
        factor = factor_values[factor_index]
        out.append({
            'date': date,
            'raw_close': close,
            'qfq_factor': factor,
            'adjusted_close': close / factor,
        })
    return out


def compare_constant_scale_paths(pit_rows: list[dict], qfq_rows: list[dict], threshold_bp: float = 5.0) -> dict:
    if len(pit_rows or []) != len(qfq_rows or []) or not pit_rows:
        raise ValueError('path lengths must match and be nonzero')
    threshold = float(threshold_bp)
    if not math.isfinite(threshold) or threshold < 0:
        raise ValueError('threshold_bp must be finite and nonnegative')

    scale = None
    max_diff_bp = 0.0
    worst_date = None
    for index, (pit, qfq) in enumerate(zip(pit_rows, qfq_rows)):
        pit_date = _date(pit.get('date'), f'pit_rows[{index}].date')
        qfq_date = _date(qfq.get('date'), f'qfq_rows[{index}].date')
        if pit_date != qfq_date:
            raise ValueError(f'path date mismatch at index {index}: {pit_date} != {qfq_date}')
        pit_value = _positive(pit.get('adjusted_close'), f'pit_rows[{index}].adjusted_close')
        qfq_value = _positive(qfq.get('adjusted_close'), f'qfq_rows[{index}].adjusted_close')
        if scale is None:
            scale = qfq_value / pit_value
        diff_bp = abs(qfq_value / (pit_value * scale) - 1.0) * 10000.0
        if diff_bp > max_diff_bp:
            max_diff_bp = diff_bp
            worst_date = pit_date

    return {
        'status': 'PASS_CONSTANT_SCALE' if max_diff_bp <= threshold else 'FAIL_CONSTANT_SCALE',
        'scale': scale,
        'rows': len(pit_rows),
        'threshold_bp': threshold,
        'max_diff_bp': max_diff_bp,
        'worst_date': worst_date,
    }
