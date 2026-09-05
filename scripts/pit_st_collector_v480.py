#!/usr/bin/env python3
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

FORMAL_START = '2020-06-01'
FORMAL_END = '2026-04-17'
FIELDS = ['date', 'code', 'tradestatus', 'isST']


def to_baostock_code(symbol: str) -> str:
    symbol = str(symbol).strip().upper()
    if len(symbol) != 9 or symbol[6] != '.':
        raise ValueError(f'invalid exchange-qualified symbol: {symbol}')
    code, exch = symbol.split('.')
    if not (len(code) == 6 and code.isdigit()):
        raise ValueError(f'invalid stock code: {symbol}')
    if exch == 'SZ':
        return f'sz.{code}'
    if exch == 'SH':
        return f'sh.{code}'
    raise ValueError(f'unsupported exchange: {symbol}')


def audit_materialized_rows(symbol, rows, query_error_code='0', query_error_msg=''):
    base = {
        'symbol': symbol,
        'query_error_code': str(query_error_code),
        'query_error_msg': str(query_error_msg or ''),
        'rows': len(rows or []),
        'st_rows': 0,
        'not_st_rows': 0,
        'transition_count': 0,
        'transitions': [],
        'first_date': None,
        'last_date': None,
        'formal_admission': False,
    }
    if str(query_error_code) != '0':
        return {**base, 'status': 'FAILED_QUERY'}
    if not rows:
        return {**base, 'status': 'UNKNOWN_EMPTY_RESPONSE'}

    expected_code = to_baostock_code(symbol)
    clean = []
    try:
        for r in rows:
            date = str(r['date']).strip()
            code = str(r['code']).strip().lower()
            tradestatus = str(r['tradestatus']).strip()
            is_st = str(r['isST']).strip()
            if code != expected_code:
                raise ValueError(f'code mismatch {code} != {expected_code}')
            if tradestatus not in {'0', '1'}:
                raise ValueError(f'invalid tradestatus {tradestatus!r}')
            if is_st not in {'0', '1'}:
                raise ValueError(f'invalid isST {is_st!r}')
            if not (FORMAL_START <= date <= FORMAL_END):
                raise ValueError(f'date outside formal window {date}')
            clean.append({'date': date, 'code': code, 'tradestatus': tradestatus, 'isST': is_st})
    except (KeyError, ValueError, TypeError) as exc:
        return {**base, 'status': 'UNKNOWN_INVALID_RESPONSE', 'validation_error': str(exc)}

    clean.sort(key=lambda r: r['date'])
    seen = set()
    for r in clean:
        if r['date'] in seen:
            return {**base, 'status': 'UNKNOWN_INVALID_RESPONSE', 'validation_error': f'duplicate date {r["date"]}'}
        seen.add(r['date'])

    transitions = []
    prev = clean[0]
    for cur in clean[1:]:
        if cur['isST'] != prev['isST']:
            transitions.append({
                'from_date': prev['date'],
                'effective_observed_date': cur['date'],
                'from_isST': prev['isST'],
                'to_isST': cur['isST'],
            })
        prev = cur

    return {
        **base,
        'status': 'MATERIALIZED_CANDIDATE_AUDIT_PENDING',
        'rows': len(clean),
        'st_rows': sum(r['isST'] == '1' for r in clean),
        'not_st_rows': sum(r['isST'] == '0' for r in clean),
        'transition_count': len(transitions),
        'transitions': transitions,
        'first_date': clean[0]['date'],
        'last_date': clean[-1]['date'],
    }


def read_scope(path: Path):
    symbols = [line.strip().upper() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if len(symbols) != 847 or len(set(symbols)) != 847:
        raise RuntimeError(f'V4.80 frozen scope must be 847 unique symbols, got rows={len(symbols)} unique={len(set(symbols))}')
    for symbol in symbols:
        to_baostock_code(symbol)
    return symbols


def query_rows(bs, symbol):
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
            values = rs.get_row_data()
            rows.append(dict(zip(rs.fields, values)))
    return rows, str(rs.error_code), str(rs.error_msg or '')


def query_basic(bs, symbol):
    code = to_baostock_code(symbol)
    try:
        rs = bs.query_stock_basic(code=code)
        rows = []
        if str(rs.error_code) == '0':
            while rs.next():
                rows.append(dict(zip(rs.fields, rs.get_row_data())))
        return {'error_code': str(rs.error_code), 'error_msg': str(rs.error_msg or ''), 'rows': rows}
    except Exception as exc:
        return {'error_code': 'EXCEPTION', 'error_msg': repr(exc), 'rows': []}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--scope', required=True)
    p.add_argument('--out-dir', required=True)
    args = p.parse_args()

    import baostock as bs

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    symbols = read_scope(Path(args.scope))

    login = bs.login()
    if str(login.error_code) != '0':
        raise RuntimeError(f'BaoStock login failed: {login.error_code} {login.error_msg}')

    all_rows = []
    audits = []
    try:
        for idx, symbol in enumerate(symbols, 1):
            try:
                rows, ec, em = query_rows(bs, symbol)
                audit = audit_materialized_rows(symbol, rows, ec, em)
                basic = query_basic(bs, symbol)
                audit['basic'] = basic
                audit['lifecycle_metadata_materialized'] = basic['error_code'] == '0' and len(basic['rows']) > 0
                audits.append(audit)
                if audit['status'] == 'MATERIALIZED_CANDIDATE_AUDIT_PENDING':
                    for r in rows:
                        all_rows.append({
                            'symbol': symbol,
                            'date': str(r['date']).strip(),
                            'code': str(r['code']).strip(),
                            'tradestatus': str(r['tradestatus']).strip(),
                            'isST': str(r['isST']).strip(),
                        })
            except Exception as exc:
                audits.append({
                    'symbol': symbol,
                    'status': 'FAILED_EXCEPTION',
                    'error': repr(exc),
                    'rows': 0,
                    'st_rows': 0,
                    'not_st_rows': 0,
                    'formal_admission': False,
                })
            if idx % 25 == 0:
                print(f'progress {idx}/{len(symbols)}', flush=True)
    finally:
        bs.logout()

    with (out_dir / 'PIT_ST_DAILY_V480.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['symbol', 'date', 'code', 'tradestatus', 'isST'])
        w.writeheader()
        w.writerows(sorted(all_rows, key=lambda r: (r['symbol'], r['date'])))

    unresolved = [a['symbol'] for a in audits if a.get('status') != 'MATERIALIZED_CANDIDATE_AUDIT_PENDING']
    lifecycle_unresolved = [a['symbol'] for a in audits if not a.get('lifecycle_metadata_materialized', False)]
    transition_symbols = [a['symbol'] for a in audits if int(a.get('transition_count', 0)) > 0]
    report = {
        'artifact': 'GP_PIT_ST_MATERIALIZATION_V480',
        'version': 'V4.80',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'formal_window': [FORMAL_START, FORMAL_END],
        'provider': 'BaoStock query_history_k_data_plus',
        'fields': FIELDS,
        'scope_n': len(symbols),
        'materialized_symbol_n': len(symbols) - len(unresolved),
        'unresolved_symbol_n': len(unresolved),
        'unresolved_symbols': unresolved,
        'lifecycle_unresolved_n': len(lifecycle_unresolved),
        'lifecycle_unresolved_symbols': lifecycle_unresolved,
        'transition_symbol_n': len(transition_symbols),
        'transition_symbols': transition_symbols,
        'daily_rows': len(all_rows),
        'formal_admission': False,
        'pit_st_gate_closed': False,
        'independent_transition_audit': 'PENDING',
        'rule': 'UNKNOWN/FAILED never defaults to NOT_ST',
        'audits': audits,
    }
    (out_dir / 'PIT_ST_AUDIT_V480.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    checkpoint = {
        'artifact': 'FORMAL_GATE_CHECKPOINT_V480',
        'version': 'V4.80',
        'formal_ready': False,
        'oos_metrics_allowed': False,
        'pit_st': {
            'status': 'MATERIALIZED_AUDIT_PENDING' if not unresolved else 'MATERIALIZATION_INCOMPLETE',
            'scope_n': len(symbols),
            'materialized_symbol_n': len(symbols) - len(unresolved),
            'unresolved_symbol_n': len(unresolved),
            'lifecycle_unresolved_n': len(lifecycle_unresolved),
            'daily_rows': len(all_rows),
            'independent_transition_audit': 'PENDING',
            'formal_admission': False,
        },
        'adjustment_provenance': 'SAMPLE50_CLOSED_V479__GLOBAL_847_OPEN',
        'locked_rule': 'No Formal OOS until PIT-ST and global 847 adjustment provenance close.',
    }
    (out_dir / 'FORMAL_GATE_CHECKPOINT_V480.json').write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding='utf-8')

    print(json.dumps({k: report[k] for k in ['scope_n','materialized_symbol_n','unresolved_symbol_n','lifecycle_unresolved_n','transition_symbol_n','daily_rows']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
