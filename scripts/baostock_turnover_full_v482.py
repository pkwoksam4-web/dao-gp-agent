from __future__ import annotations

import math

import pandas as pd

from baostock_turnover_v482 import (
    EXPECTED_SCOPE_N,
    EXPECTED_TRADE_ROWS,
    EXPECTED_TURNOVER_SYMBOL_N,
    PITST_TRADESTATUS_ONE_CORRECTIONS,
    apply_trade_status_corrections,
    audit_and_extract,
    query_rows,
)

ZERO_TRADE_SYMBOLS = {'600074.SH', '600485.SH', '600677.SH'}


def select_shard(symbols: list[str], shard_index: int, shard_count: int) -> list[str]:
    if int(shard_count) <= 0 or not (0 <= int(shard_index) < int(shard_count)):
        raise ValueError('invalid shard index/count')
    return list(symbols)[int(shard_index)::int(shard_count)]


def expected_trade_dates(pitst: pd.DataFrame, symbol: str) -> list[str]:
    normalized = str(symbol).strip().upper()
    required = {'symbol', 'date', 'tradestatus'}
    if not required.issubset(pitst.columns):
        raise ValueError(f'PIT-ST columns missing: {sorted(required - set(pitst.columns))}')
    x = pitst.loc[:, ['symbol', 'date', 'tradestatus']].copy()
    x['symbol'] = x['symbol'].astype(str).str.upper()
    x['date'] = x['date'].astype(str).str[:10]
    x['tradestatus'] = pd.to_numeric(x['tradestatus'], errors='coerce').fillna(0).astype(int)
    for correction_symbol, correction_date in PITST_TRADESTATUS_ONE_CORRECTIONS:
        mask = (x['symbol'] == correction_symbol) & (x['date'] == correction_date)
        x.loc[mask, 'tradestatus'] = 1
    g = x[(x['symbol'] == normalized) & (x['tradestatus'] == 1)]
    return sorted(g['date'].drop_duplicates().tolist())


def audit_exact_dates(symbol: str, expected_dates: list[str], rows: list[dict]) -> dict:
    normalized = str(symbol).strip().upper()
    expected = sorted(set(str(d)[:10] for d in expected_dates))
    actual_dates = [str(r.get('date') or '')[:10] for r in (rows or [])]
    unique_actual = sorted(set(actual_dates))
    missing = sorted(set(expected) - set(unique_actual))
    extra = sorted(set(unique_actual) - set(expected))
    duplicate_n = len(actual_dates) - len(unique_actual)
    bad_turnover_n = 0
    for row in rows or []:
        if str(row.get('symbol') or '').strip().upper() != normalized:
            bad_turnover_n += 1
            continue
        try:
            value = float(row.get('turnover_ratio'))
        except (TypeError, ValueError):
            bad_turnover_n += 1
            continue
        if not math.isfinite(value) or value < 0:
            bad_turnover_n += 1

    if bad_turnover_n:
        status = 'REVIEW_BAD_TURNOVER'
    elif missing or extra or duplicate_n:
        status = 'REVIEW_TURNOVER_DATES'
    else:
        status = 'PASS_EXACT_TURNOVER_DATES'
    return {
        'symbol': normalized,
        'expected_trade_rows': len(expected),
        'turnover_rows': len(rows or []),
        'missing_dates_n': len(missing),
        'extra_dates_n': len(extra),
        'duplicate_dates_n': duplicate_n,
        'bad_turnover_n': bad_turnover_n,
        'missing_dates': missing,
        'extra_dates': extra,
        'status': status,
    }


def collect_symbol(bs, pitst: pd.DataFrame, symbol: str) -> tuple[list[dict], dict]:
    normalized = str(symbol).strip().upper()
    expected = expected_trade_dates(pitst, normalized)
    raw_rows, error_code, error_msg = query_rows(bs, normalized)
    if str(error_code) != '0':
        core = audit_and_extract(
            normalized,
            [],
            query_error_code=error_code,
            query_error_msg=error_msg,
        )
        return [], {
            **core,
            'expected_trade_rows': len(expected),
            'missing_dates_n': len(expected),
            'extra_dates_n': 0,
            'duplicate_dates_n': 0,
            'applied_trade_status_corrections': [],
            'unresolved_symbol': True,
        }

    corrected_rows, applied = apply_trade_status_corrections(normalized, raw_rows)
    core = audit_and_extract(normalized, corrected_rows)
    applied_json = [list(item) for item in applied]
    if core['status'] != 'PASS_TURNOVER_ROWS':
        return [], {
            **core,
            'expected_trade_rows': len(expected),
            'missing_dates_n': len(expected),
            'extra_dates_n': 0,
            'duplicate_dates_n': 0,
            'applied_trade_status_corrections': applied_json,
            'unresolved_symbol': False,
        }

    turnover_rows = core['turnover_rows']
    exact = audit_exact_dates(normalized, expected, turnover_rows)
    if normalized in ZERO_TRADE_SYMBOLS:
        if not expected and not turnover_rows and exact['status'] == 'PASS_EXACT_TURNOVER_DATES':
            status = 'PASS_ZERO_TRADE_SYMBOL'
        else:
            status = 'REVIEW_ZERO_TRADE_SYMBOL'
    else:
        status = exact['status']

    audit = {
        **core,
        **exact,
        'status': status,
        'applied_trade_status_corrections': applied_json,
        'unresolved_symbol': False,
        'formal_admission': False,
        'oos_metrics_allowed': False,
    }
    return turnover_rows if status.startswith('PASS_') else [], audit


def full_global_gate(
    *,
    scope_n: int,
    turnover_symbol_n: int,
    turnover_rows: int,
    missing_n: int,
    extra_n: int,
    duplicate_n: int,
    bad_turnover_n: int,
    unresolved_symbol_n: int,
    zero_trade_symbols,
) -> bool:
    return (
        int(scope_n) == EXPECTED_SCOPE_N
        and int(turnover_symbol_n) == EXPECTED_TURNOVER_SYMBOL_N
        and int(turnover_rows) == EXPECTED_TRADE_ROWS
        and int(missing_n) == 0
        and int(extra_n) == 0
        and int(duplicate_n) == 0
        and int(bad_turnover_n) == 0
        and int(unresolved_symbol_n) == 0
        and set(zero_trade_symbols) == ZERO_TRADE_SYMBOLS
    )
