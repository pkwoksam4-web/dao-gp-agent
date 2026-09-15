from __future__ import annotations

import math


def _date(value: object, label: str) -> str:
    text = str(value or '')[:10]
    if len(text) != 10:
        raise ValueError(f'{label} must be YYYY-MM-DD')
    return text


def _positive(value: object, label: str) -> float:
    x = float(value)
    if not math.isfinite(x) or x <= 0:
        raise ValueError(f'{label} must be positive finite')
    return x


def _event_key(row: dict) -> tuple[str, str]:
    symbol = str(row.get('symbol') or '').upper()
    ex_date = _date(row.get('ex_date'), 'ex_date')
    if not symbol:
        raise ValueError('event symbol is required')
    return symbol, ex_date


def merge_final_override_ratios(
    standard_stages: list[list[dict]],
    special_rows: list[dict],
    availability: dict[tuple[str, str], str],
    *,
    expected_standard_n: int = 270,
    expected_special_n: int = 11,
) -> dict:
    ratios: dict[tuple[str, str], float] = {}
    paired_availability: dict[tuple[str, str], str] = {}
    standard_n = 0
    for stage in standard_stages or []:
        for row in stage or []:
            key = _event_key(row)
            if key in ratios:
                raise ValueError(f'override collision: {key}')
            date = availability.get(key)
            if not date:
                raise ValueError(f'MISSING_OVERRIDE_AVAILABILITY:{key[0]}:{key[1]}')
            if _date(date, 'availability_date') > key[1]:
                raise ValueError(f'OVERRIDE_NOT_PIT_AVAILABLE:{key[0]}:{key[1]}:{date}')
            ratios[key] = _positive(row.get('corrected_event_ratio'), 'corrected_event_ratio')
            paired_availability[key] = str(date)[:10]
            standard_n += 1
    if standard_n != int(expected_standard_n):
        raise ValueError(f'expected {expected_standard_n} standard overrides; got {standard_n}')

    special_n = 0
    for row in special_rows or []:
        key = _event_key(row)
        if key in ratios:
            raise ValueError(f'override collision: {key}')
        date = availability.get(key)
        if not date:
            raise ValueError(f'MISSING_OVERRIDE_AVAILABILITY:{key[0]}:{key[1]}')
        if _date(date, 'availability_date') > key[1]:
            raise ValueError(f'OVERRIDE_NOT_PIT_AVAILABLE:{key[0]}:{key[1]}:{date}')
        ratios[key] = _positive(row.get('corrected_event_ratio'), 'corrected_event_ratio')
        paired_availability[key] = str(date)[:10]
        special_n += 1
    if special_n != int(expected_special_n):
        raise ValueError(f'expected {expected_special_n} special overrides; got {special_n}')

    return {
        'standard_n': standard_n,
        'special_n': special_n,
        'total_n': len(ratios),
        'ratios': ratios,
        'availability': paired_availability,
    }


def validate_special_prev_close(
    symbol: str,
    raw_rows: list[dict],
    special: dict,
    tolerance_bp: float = 0.01,
) -> dict:
    normalized_symbol = str(symbol or '').upper()
    if normalized_symbol != str(special.get('symbol') or '').upper():
        raise ValueError('special symbol mismatch')
    ex_date = _date(special.get('ex_date'), 'ex_date')
    formula_date = _date(special.get('formula_availability_date'), 'formula_availability_date')
    expected_prev = _positive(special.get('expected_prev_close'), 'expected_prev_close')
    adjusted_ref = _positive(special.get('adjusted_reference_price'), 'adjusted_reference_price')
    corrected_ratio = _positive(special.get('corrected_event_ratio'), 'corrected_event_ratio')

    prior = []
    for row in raw_rows or []:
        d = _date(row.get('date'), 'raw date')
        if d < ex_date:
            prior.append((d, _positive(row.get('close'), 'raw close'))
    if not prior:
        raise ValueError(f'SPECIAL_PREV_CLOSE_MISSING:{normalized_symbol}:{ex_date}')
    previous_trade_date, previous_close = max(prior, key=lambda item: item[0])
    if formula_date > previous_trade_date:
        raise ValueError(
            f'SPECIAL_FORMULA_NOT_AVAILABLE_BY_PREV_CLOSE:{normalized_symbol}:{ex_date}:{formula_date}:{previous_trade_date}'
        )

    previous_close_diff_bp = abs(previous_close / expected_prev - 1.0) * 10000.0
    if previous_close_diff_bp > float(tolerance_bp):
        raise ValueError(
            f'SPECIAL_PREV_CLOSE_MISMATCH:{normalized_symbol}:{ex_date}:{previous_close_diff_bp}'
        )
    derived_ratio = adjusted_ref / expected_prev
    ratio_diff_bp = abs(corrected_ratio / derived_ratio - 1.0) * 10000.0
    if ratio_diff_bp > 1e-8:
        raise ValueError(f'SPECIAL_RATIO_MISMATCH:{normalized_symbol}:{ex_date}:{ratio_diff_bp}')

    return {
        'symbol': normalized_symbol,
        'ex_date': ex_date,
        'status': 'PASS_SPECIAL_PREV_CLOSE_PIT',
        'formula_availability_date': formula_date,
        'previous_trade_date': previous_trade_date,
        'previous_close': previous_close,
        'expected_prev_close': expected_prev,
        'previous_close_diff_bp': previous_close_diff_bp,
        'derived_event_ratio': derived_ratio,
        'corrected_event_ratio': corrected_ratio,
        'ratio_diff_bp': ratio_diff_bp,
    }
