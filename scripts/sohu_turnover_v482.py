from __future__ import annotations

import json
import math
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

EXPECTED_SYMBOL_LIST_N = 847
EXPECTED_TURNOVER_SYMBOL_N = 844
EXPECTED_TRADE_ROWS = 1_011_607


def normalize_symbol(symbol: str) -> str:
    text = str(symbol or '').strip().upper()
    if '.' not in text:
        raise ValueError(f'exchange-qualified symbol required: {symbol!r}')
    code, exchange = text.split('.', 1)
    if exchange not in {'SZ', 'SH'} or not code.isdigit():
        raise ValueError(f'unsupported symbol: {symbol!r}')
    return f'{code.zfill(6)}.{exchange}'


def build_request_params(symbol: str, start: str, end: str) -> dict:
    normalized = normalize_symbol(symbol)
    start_date = date.fromisoformat(str(start)[:10])
    end_date = date.fromisoformat(str(end)[:10])
    if end_date < start_date:
        raise ValueError('Sohu turnover request range reversed')
    return {
        'code': f"cn_{normalized.split('.', 1)[0]}",
        'start': start_date.strftime('%Y%m%d'),
        'end': end_date.strftime('%Y%m%d'),
        'stat': '1',
        'order': 'A',
        'period': 'd',
        'callback': 'historySearchHandler',
        'rt': 'jsonp',
    }


def plan_chunks(start: str, end: str, *, max_calendar_days: int = 90) -> list[tuple[str, str]]:
    if int(max_calendar_days) <= 0:
        raise ValueError('max_calendar_days must be positive')
    cursor = date.fromisoformat(str(start)[:10])
    stop = date.fromisoformat(str(end)[:10])
    if stop < cursor:
        raise ValueError('chunk range reversed')
    chunks = []
    while cursor <= stop:
        chunk_end = min(stop, cursor + timedelta(days=int(max_calendar_days) - 1))
        chunks.append((cursor.isoformat(), chunk_end.isoformat()))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def _decode(raw: bytes) -> str:
    for encoding in ('utf-8-sig', 'gb18030'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ValueError('Sohu turnover payload decode failed')


def _parse_turnover_percent(value: object) -> float:
    text = str(value or '').strip()
    if text.endswith('%'):
        text = text[:-1].strip()
    if not text or text == '-':
        raise ValueError('turnover is missing')
    try:
        percent = float(text)
    except ValueError as exc:
        raise ValueError(f'invalid turnover: {value!r}') from exc
    if not math.isfinite(percent) or percent < 0:
        raise ValueError(f'invalid turnover: {value!r}')
    return percent / 100.0


def parse_hishq_turnover_bytes(symbol: str, raw: bytes) -> list[dict]:
    normalized = normalize_symbol(symbol)
    text = _decode(raw).strip()
    match = re.match(r'^\s*historySearchHandler\((.*)\)\s*;?\s*$', text, re.S)
    if not match:
        raise ValueError('Sohu JSONP wrapper mismatch')
    payload = json.loads(match.group(1))
    if not isinstance(payload, list) or not payload:
        return []
    block = payload[0]
    if not isinstance(block, dict) or int(block.get('status', -1)) != 0:
        return []
    hq = block.get('hq') or []
    if not isinstance(hq, list):
        return []

    rows = []
    for row in hq:
        if not isinstance(row, list) or len(row) < 10:
            raise ValueError('turnover column is missing from Sohu trade row')
        row_date = str(row[0] or '')[:10]
        if len(row_date) != 10:
            raise ValueError('invalid Sohu turnover date')
        rows.append({
            'symbol': normalized,
            'date': row_date,
            'turnover_ratio': _parse_turnover_percent(row[9]),
            'source': 'SOHU_HISHQ_TURNOVER',
        })
    rows.sort(key=lambda item: item['date'])
    if len({row['date'] for row in rows}) != len(rows):
        raise ValueError(f'duplicate Sohu turnover dates: {normalized}')
    return rows


def merge_turnover_rows_unique(symbol: str, *chunks: list[dict]) -> list[dict]:
    normalized = normalize_symbol(symbol)
    by_date: dict[str, dict] = {}
    for chunk in chunks:
        for raw_row in chunk or []:
            row = dict(raw_row)
            if normalize_symbol(row.get('symbol')) != normalized:
                raise ValueError(f'turnover symbol mismatch: {normalized}')
            row_date = str(row.get('date') or '')[:10]
            prior = by_date.get(row_date)
            if prior is not None and prior != row:
                raise ValueError(f'conflicting duplicate turnover row: {normalized}:{row_date}')
            by_date[row_date] = row
    return [by_date[row_date] for row_date in sorted(by_date)]


def _finite_decimal(value: object, label: str) -> Decimal:
    try:
        out = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'invalid {label}: {value!r}') from exc
    if not out.is_finite():
        raise ValueError(f'invalid {label}: {value!r}')
    return out


def crosscheck_eastmoney_turnover(
    sohu_rows: list[dict],
    eastmoney_rows: list[dict],
    *,
    tolerance_bp: float = 0.01,
) -> dict:
    eastmoney = {
        (normalize_symbol(row.get('symbol')), str(row.get('date') or '')[:10]): row
        for row in eastmoney_rows or []
    }
    diffs = []
    failures = []
    tolerance = _finite_decimal(tolerance_bp, 'tolerance_bp')
    for row in sohu_rows or []:
        key = (normalize_symbol(row.get('symbol')), str(row.get('date') or '')[:10])
        other = eastmoney.get(key)
        if other is None:
            failures.append({'symbol': key[0], 'date': key[1], 'reason': 'MISSING_EASTMONEY'})
            continue
        sohu_ratio = _finite_decimal(row.get('turnover_ratio'), 'Sohu turnover_ratio')
        eastmoney_ratio = _finite_decimal(other.get('turnover_pct'), 'Eastmoney turnover_pct') / Decimal('100')
        if sohu_ratio < 0 or eastmoney_ratio < 0:
            failures.append({'symbol': key[0], 'date': key[1], 'reason': 'NEGATIVE_TURNOVER'})
            continue
        diff_bp_decimal = abs(sohu_ratio - eastmoney_ratio) * Decimal('10000')
        diff_bp = float(diff_bp_decimal)
        diffs.append(diff_bp)
        if diff_bp_decimal > tolerance:
            failures.append({'symbol': key[0], 'date': key[1], 'reason': 'TURNOVER_DIFF', 'diff_bp': diff_bp})
    return {
        'matched_n': len(diffs),
        'fail_n': len(failures),
        'max_diff_bp': max(diffs, default=0.0),
        'failures': failures,
    }


def select_shard(symbols: list[str], shard_index: int, shard_count: int) -> list[str]:
    if int(shard_count) <= 0 or not (0 <= int(shard_index) < int(shard_count)):
        raise ValueError('invalid shard index/count')
    return list(symbols)[int(shard_index)::int(shard_count)]


def audit_trade_dates(symbol: str, expected_dates: list[str], rows: list[dict]) -> dict:
    normalized = normalize_symbol(symbol)
    expected = sorted(set(str(day)[:10] for day in expected_dates))
    actual_dates = [str(row.get('date') or '')[:10] for row in rows or []]
    actual_unique = sorted(set(actual_dates))
    missing = sorted(set(expected) - set(actual_unique))
    extra = sorted(set(actual_unique) - set(expected))
    duplicate_dates_n = len(actual_dates) - len(actual_unique)
    bad_turnover_n = 0
    for row in rows or []:
        if normalize_symbol(row.get('symbol')) != normalized:
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
    elif missing or extra or duplicate_dates_n:
        status = 'REVIEW_TURNOVER_DATES'
    else:
        status = 'PASS_EXACT_TURNOVER_DATES'
    return {
        'symbol': normalized,
        'expected_trade_rows': len(expected),
        'turnover_rows': len(rows or []),
        'missing_dates_n': len(missing),
        'extra_dates_n': len(extra),
        'duplicate_dates_n': duplicate_dates_n,
        'bad_turnover_n': bad_turnover_n,
        'missing_dates': missing,
        'extra_dates': extra,
        'status': status,
    }


def full_turnover_global_gate(
    *,
    unique_symbol_n: int,
    symbol_list_n: int,
    turnover_rows: int,
    duplicate_rows: int,
    missing_n: int,
    extra_n: int,
    bad_turnover_n: int,
    shard_error: int,
) -> bool:
    return (
        int(unique_symbol_n) == EXPECTED_TURNOVER_SYMBOL_N
        and int(symbol_list_n) == EXPECTED_SYMBOL_LIST_N
        and int(turnover_rows) == EXPECTED_TRADE_ROWS
        and int(duplicate_rows) == 0
        and int(missing_n) == 0
        and int(extra_n) == 0
        and int(bad_turnover_n) == 0
        and int(shard_error) == 0
    )
