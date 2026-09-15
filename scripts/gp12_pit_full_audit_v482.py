from __future__ import annotations

import math

from gp12_pit_adjusted_close_audit_v482 import audit_symbol_path


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
            prior.append((d, _positive(row.get('close'), 'raw close')))
    if not prior:
        raise ValueError(f'SPECIAL_PREV_CLOSE_MISSING:{normalized_symbol}:{ex_date}')
    previous_trade_date, previous_close = max(prior, key=lambda item: item[0])
    ratio_availability_date = max(formula_date, previous_trade_date)
    if ratio_availability_date >= ex_date:
        raise ValueError(
            f'SPECIAL_RATIO_NOT_AVAILABLE_BEFORE_EX_DATE:{normalized_symbol}:{ex_date}:{ratio_availability_date}'
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
        'ratio_availability_date': ratio_availability_date,
        'previous_close': previous_close,
        'expected_prev_close': expected_prev,
        'previous_close_diff_bp': previous_close_diff_bp,
        'derived_event_ratio': derived_ratio,
        'corrected_event_ratio': corrected_ratio,
        'ratio_diff_bp': ratio_diff_bp,
    }


def audit_universe(
    *,
    raw_by_symbol: dict[str, list[dict]],
    factors_by_symbol: dict[str, list[dict]],
    frozen_records: list[dict],
    standard_stages: list[list[dict]],
    special_rows: list[dict],
    manifest: dict,
    na_symbols: list[str],
    expected_standard_n: int = 270,
    expected_special_n: int = 11,
    threshold_bp: float = 5.0,
) -> dict:
    nominal_availability = {
        _event_key(row): _date(row.get('availability_date'), 'availability_date')
        for row in manifest.get('nominal_events') or []
    }
    final_availability = {
        _event_key(row): _date(row.get('availability_date'), 'availability_date')
        for row in manifest.get('standard_overrides') or []
    }
    for row in manifest.get('special_overrides') or []:
        key = _event_key(row)
        if key in final_availability:
            raise ValueError(f'override collision: {key}')
        final_availability[key] = _date(row.get('formula_availability_date'), 'formula_availability_date')

    merged = merge_final_override_ratios(
        standard_stages,
        special_rows,
        final_availability,
        expected_standard_n=expected_standard_n,
        expected_special_n=expected_special_n,
    )
    na = sorted(str(symbol).upper() for symbol in na_symbols)
    records_by_symbol = {}
    for record in frozen_records or []:
        symbol = str(record.get('symbol') or '').upper()
        if not symbol or symbol in records_by_symbol:
            raise ValueError(f'duplicate/missing frozen symbol: {symbol}')
        records_by_symbol[symbol] = record
    if sorted(records_by_symbol) != sorted(set(records_by_symbol)):
        raise ValueError('frozen symbol partition is not unique')

    path_records = []
    failures = []
    for symbol, record in sorted(records_by_symbol.items()):
        if symbol in na:
            continue
        raw_rows = raw_by_symbol.get(symbol)
        factor_rows = factors_by_symbol.get(symbol)
        if not raw_rows:
            raise ValueError(f'MISSING_RAW_SYMBOL:{symbol}')
        if not factor_rows:
            raise ValueError(f'MISSING_QFQ_FACTOR_SYMBOL:{symbol}')
        result = audit_symbol_path(
            symbol=symbol,
            raw_rows=raw_rows,
            qfq_factors=factor_rows,
            frozen_events=record.get('events') or [],
            nominal_availability=nominal_availability,
            overrides=merged['ratios'],
            override_availability=merged['availability'],
            threshold_bp=threshold_bp,
        )
        path_records.append(result)
        if result.get('status') != 'PASS_CONSTANT_SCALE':
            failures.append(result)

    special_checks = []
    for row in special_rows or []:
        symbol = str(row.get('symbol') or '').upper()
        raw_rows = raw_by_symbol.get(symbol)
        if not raw_rows:
            raise ValueError(f'MISSING_SPECIAL_RAW_SYMBOL:{symbol}')
        special_checks.append(validate_special_prev_close(symbol, raw_rows, row))

    formal_n = len(path_records)
    max_diff = max((float(row.get('max_diff_bp') or 0.0) for row in path_records), default=0.0)
    verified = bool(not failures and len(special_checks) == int(expected_special_n))
    return {
        'artifact': 'GP12_PIT_ADJUSTED_CLOSE_FULL_AUDIT_V482',
        'version': 'V4.82',
        'universe_n': len(records_by_symbol),
        'formal_symbol_n': formal_n,
        'na_symbols': na,
        'nominal_event_n': len(manifest.get('nominal_events') or []),
        'standard_override_n': merged['standard_n'],
        'special_override_n': merged['special_n'],
        'total_override_n': merged['total_n'],
        'special_prev_close_pass_n': sum(row.get('status') == 'PASS_SPECIAL_PREV_CLOSE_PIT' for row in special_checks),
        'constant_scale_pass_n': sum(row.get('status') == 'PASS_CONSTANT_SCALE' for row in path_records),
        'constant_scale_fail_n': len(failures),
        'max_constant_scale_diff_bp': max_diff,
        'adjusted_close_pit_verified': verified,
        'candidate_approval': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
        'records': path_records,
        'failures': failures,
        'special_checks': special_checks,
    }
