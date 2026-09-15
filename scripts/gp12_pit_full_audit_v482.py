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
            prior.append((d, _positive(row.get('close'), 'raw close')))
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
