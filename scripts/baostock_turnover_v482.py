from __future__ import annotations

import math

from pit_st_collector_v480 import FORMAL_END, FORMAL_START, to_baostock_code

FIELDS = ['date', 'code', 'turn', 'tradestatus', 'isST']
SOURCE = 'BAOSTOCK_QUERY_HISTORY_K_DATA_PLUS_TURN_V482'
EXPECTED_SCOPE_N = 847
EXPECTED_TURNOVER_SYMBOL_N = 844
EXPECTED_TRADE_ROWS = 1_011_607
PITST_TRADESTATUS_ONE_CORRECTIONS = {
    ('002087.SZ', '2024-06-13'),
    ('300356.SZ', '2023-06-20'),
    ('600647.SH', '2024-06-13'),
    ('600766.SH', '2024-06-13'),
    ('603133.SH', '2024-06-13'),
}


def query_rows(bs, symbol: str):
    code = to_baostock_code(symbol)
    rs = bs.query_history_k_data_plus(
        code,
        ','.join(FIELDS),
        start_date=FORMAL_START,
        end_date=FORMAL_END,
        frequency='d',
        adjustflag='3',
    )
    rows = []
    if str(rs.error_code) == '0':
        while rs.next():
            rows.append(dict(zip(rs.fields, rs.get_row_data())))
    return rows, str(rs.error_code), str(rs.error_msg or '')


def apply_trade_status_corrections(symbol: str, rows: list[dict]) -> tuple[list[dict], list[tuple[str, str]]]:
    normalized = str(symbol).strip().upper()
    corrected = [dict(row) for row in (rows or [])]
    applied = []
    for row in corrected:
        date = str(row.get('date') or '').strip()[:10]
        key = (normalized, date)
        if key in PITST_TRADESTATUS_ONE_CORRECTIONS:
            row['tradestatus'] = '1'
            applied.append(key)
    return corrected, applied


def _base(symbol: str, rows, query_error_code='0', query_error_msg='') -> dict:
    return {
        'symbol': str(symbol).strip().upper(),
        'query_error_code': str(query_error_code),
        'query_error_msg': str(query_error_msg or ''),
        'response_rows': len(rows or []),
        'trade_rows': 0,
        'nontrade_rows': 0,
        'bad_turnover_n': 0,
        'turnover_rows': [],
        'turnover_pit_verified': False,
        'formal_admission': False,
        'oos_metrics_allowed': False,
    }


def audit_and_extract(symbol: str, rows: list[dict], query_error_code='0', query_error_msg='') -> dict:
    base = _base(symbol, rows, query_error_code, query_error_msg)
    if str(query_error_code) != '0':
        return {**base, 'status': 'FAILED_QUERY'}

    expected_code = to_baostock_code(symbol)
    seen = set()
    extracted = []
    trade_rows = 0
    nontrade_rows = 0
    bad_turnover_n = 0

    for row in rows or []:
        try:
            date = str(row['date']).strip()
            code = str(row['code']).strip().lower()
            tradestatus = str(row['tradestatus']).strip()
            is_st = str(row['isST']).strip()
        except (KeyError, TypeError):
            return {**base, 'status': 'REVIEW_INVALID_RESPONSE'}

        if code != expected_code or tradestatus not in {'0', '1'} or is_st not in {'0', '1'}:
            return {**base, 'status': 'REVIEW_INVALID_RESPONSE'}
        if not (FORMAL_START <= date <= FORMAL_END):
            return {**base, 'status': 'REVIEW_INVALID_RESPONSE'}
        if date in seen:
            return {**base, 'status': 'REVIEW_DUPLICATE_DATE'}
        seen.add(date)

        if tradestatus == '0':
            nontrade_rows += 1
            continue

        trade_rows += 1
        text = str(row.get('turn', '')).strip()
        try:
            percent = float(text)
        except (TypeError, ValueError):
            bad_turnover_n += 1
            continue
        if not math.isfinite(percent) or percent < 0:
            bad_turnover_n += 1
            continue
        extracted.append({
            'symbol': str(symbol).strip().upper(),
            'date': date,
            'turnover_ratio': percent / 100.0,
            'source': SOURCE,
        })

    if bad_turnover_n:
        return {
            **base,
            'status': 'REVIEW_BAD_TURNOVER',
            'trade_rows': trade_rows,
            'nontrade_rows': nontrade_rows,
            'bad_turnover_n': bad_turnover_n,
            'turnover_rows': [],
        }

    extracted.sort(key=lambda r: r['date'])
    return {
        **base,
        'status': 'PASS_TURNOVER_ROWS',
        'trade_rows': trade_rows,
        'nontrade_rows': nontrade_rows,
        'bad_turnover_n': 0,
        'turnover_rows': extracted,
    }


def full_turnover_global_gate(
    *,
    scope_n: int,
    turnover_symbol_n: int,
    turnover_rows: int,
    missing_n: int,
    extra_n: int,
    duplicate_n: int,
    bad_turnover_n: int,
    unresolved_symbol_n: int,
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
    )
