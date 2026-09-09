#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pit_st_collector_v480 import to_baostock_code

FORMAL_START = '2020-06-01'
FORMAL_END = '2026-04-17'
ADJUSTFLAG = '3'
FIXED5_SYMBOLS = (
    '000001.SZ',
    '000014.SZ',
    '001201.SZ',
    '002001.SZ',
    '002002.SZ',
)
FIELDS = (
    'date', 'code', 'open', 'high', 'low', 'close', 'preclose',
    'volume', 'amount', 'adjustflag', 'turn', 'tradestatus', 'pctChg', 'isST',
)


def _base_audit(symbol, rows, query_error_code, query_error_msg):
    return {
        'symbol': symbol,
        'query_error_code': str(query_error_code),
        'query_error_msg': str(query_error_msg or ''),
        'rows': len(rows or []),
        'raw_traded_rows': 0,
        'suspended_rows': 0,
        'st_rows': 0,
        'not_st_rows': 0,
        'first_date': None,
        'last_date': None,
        'formal_admission': False,
        'oos_metrics_allowed': False,
    }


def _float_required(row, field):
    text = str(row.get(field, '')).strip()
    if text == '':
        raise ValueError(f'missing {field} on traded row')
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f'invalid {field}={text!r} on traded row') from exc


def audit_probe_rows(symbol, rows, query_error_code='0', query_error_msg=''):
    base = _base_audit(symbol, rows, query_error_code, query_error_msg)
    if str(query_error_code) != '0':
        return {**base, 'status': 'FAILED_QUERY'}
    if not rows:
        return {**base, 'status': 'UNKNOWN_EMPTY_RESPONSE'}

    expected_code = to_baostock_code(symbol)
    clean = []
    try:
        for raw in rows:
            date = str(raw.get('date', '')).strip()
            code = str(raw.get('code', '')).strip().lower()
            tradestatus = str(raw.get('tradestatus', '')).strip()
            is_st = str(raw.get('isST', '')).strip()
            adjustflag = str(raw.get('adjustflag', '')).strip()

            if not date or not (FORMAL_START <= date <= FORMAL_END):
                raise ValueError(f'date outside formal window {date!r}')
            if code != expected_code:
                raise ValueError(f'code mismatch {code!r} != {expected_code!r}')
            if tradestatus not in {'0', '1'}:
                raise ValueError(f'invalid tradestatus {tradestatus!r}')
            if is_st not in {'0', '1'}:
                raise ValueError(f'invalid isST {is_st!r}')
            if adjustflag != ADJUSTFLAG:
                raise ValueError(f'adjustflag mismatch {adjustflag!r} != {ADJUSTFLAG!r}')

            normalized = {field: str(raw.get(field, '')).strip() for field in FIELDS}
            normalized['code'] = code

            if tradestatus == '1':
                open_ = _float_required(raw, 'open')
                high = _float_required(raw, 'high')
                low = _float_required(raw, 'low')
                close = _float_required(raw, 'close')
                preclose = _float_required(raw, 'preclose')
                volume = _float_required(raw, 'volume')
                amount = _float_required(raw, 'amount')
                if min(open_, high, low, close, preclose) <= 0:
                    raise ValueError('nonpositive price on traded row')
                if volume < 0:
                    raise ValueError('negative volume on traded row')
                if amount < 0:
                    raise ValueError('negative amount on traded row')
                if high < max(open_, low, close) or low > min(open_, high, close):
                    raise ValueError('invalid OHLC geometry on traded row')

            clean.append(normalized)
    except (TypeError, ValueError) as exc:
        return {**base, 'status': 'UNKNOWN_INVALID_RESPONSE', 'validation_error': str(exc)}

    clean.sort(key=lambda row: row['date'])
    seen = set()
    for row in clean:
        if row['date'] in seen:
            return {
                **base,
                'status': 'UNKNOWN_INVALID_RESPONSE',
                'validation_error': f'duplicate date {row["date"]}',
            }
        seen.add(row['date'])

    raw_traded_rows = sum(row['tradestatus'] == '1' for row in clean)
    suspended_rows = sum(row['tradestatus'] == '0' for row in clean)
    return {
        **base,
        'status': 'PASS_PROBE_CANDIDATE',
        'rows': len(clean),
        'raw_traded_rows': raw_traded_rows,
        'suspended_rows': suspended_rows,
        'st_rows': sum(row['isST'] == '1' for row in clean),
        'not_st_rows': sum(row['isST'] == '0' for row in clean),
        'first_date': clean[0]['date'],
        'last_date': clean[-1]['date'],
    }


def query_rows(bs, symbol):
    rs = bs.query_history_k_data_plus(
        to_baostock_code(symbol),
        ','.join(FIELDS),
        start_date=FORMAL_START,
        end_date=FORMAL_END,
        frequency='d',
        adjustflag=ADJUSTFLAG,
    )
    rows = []
    if str(rs.error_code) == '0':
        while rs.next():
            rows.append(dict(zip(rs.fields, rs.get_row_data())))
    return rows, str(rs.error_code), str(rs.error_msg or '')


def _write_csv(path, fieldnames, rows):
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description='GP V4.82 fixed-five BaoStock source probe')
    p.add_argument('--out-dir', required=True)
    args = p.parse_args()

    import baostock as bs

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    login = bs.login()
    login_code = str(login.error_code)
    login_msg = str(login.error_msg or '')
    if login_code != '0':
        report = {
            'artifact': 'BAOSTOCK_FIXED5_PROBE_AUDIT_V482',
            'version': 'V4.82',
            'status': 'FAILED_LOGIN',
            'provider': 'BaoStock query_history_k_data_plus',
            'login_error_code': login_code,
            'login_error_msg': login_msg,
            'fixed5_symbols': list(FIXED5_SYMBOLS),
            'formal_admission': False,
            'oos_metrics_allowed': False,
        }
        (out_dir / 'BAOSTOCK_FIXED5_PROBE_AUDIT_V482.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        print(json.dumps(report, ensure_ascii=False))
        return 2

    all_rows = []
    raw_rows = []
    audits = []
    try:
        for idx, symbol in enumerate(FIXED5_SYMBOLS, 1):
            try:
                rows, ec, em = query_rows(bs, symbol)
                audit = audit_probe_rows(symbol, rows, ec, em)
            except Exception as exc:
                rows = []
                audit = {
                    **_base_audit(symbol, [], 'EXCEPTION', repr(exc)),
                    'status': 'FAILED_EXCEPTION',
                    'error': repr(exc),
                }
            audits.append(audit)
            for row in rows:
                normalized = {'symbol': symbol}
                normalized.update({field: str(row.get(field, '')).strip() for field in FIELDS})
                all_rows.append(normalized)
                if str(row.get('tradestatus', '')).strip() == '1':
                    raw_rows.append(normalized)
            print(
                f'[{idx}/{len(FIXED5_SYMBOLS)}] {symbol} '
                f'status={audit["status"]} rows={audit.get("rows", 0)} '
                f'first={audit.get("first_date")} last={audit.get("last_date")}',
                flush=True,
            )
    finally:
        bs.logout()

    daily_path = out_dir / 'BAOSTOCK_FIXED5_DAILY_V482.csv'
    raw_path = out_dir / 'BAOSTOCK_FIXED5_RAW_TRADED_V482.csv'
    fieldnames = ['symbol', *FIELDS]
    _write_csv(daily_path, fieldnames, sorted(all_rows, key=lambda r: (r['symbol'], r['date'])))
    _write_csv(raw_path, fieldnames, sorted(raw_rows, key=lambda r: (r['symbol'], r['date'])))

    passing = [a['symbol'] for a in audits if a.get('status') == 'PASS_PROBE_CANDIDATE']
    failing = [a['symbol'] for a in audits if a.get('status') != 'PASS_PROBE_CANDIDATE']
    report = {
        'artifact': 'BAOSTOCK_FIXED5_PROBE_AUDIT_V482',
        'version': 'V4.82',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'PASS_FIXED5_SOURCE_PROBE' if not failing else 'PARTIAL_OR_FAILED_FIXED5_SOURCE_PROBE',
        'purpose': 'isolated BaoStock source capability probe; no Formal/OOS promotion',
        'fixed5_source_contract': 'V3.73 PILOT_SYMBOLS',
        'fixed5_symbols': list(FIXED5_SYMBOLS),
        'provider': 'BaoStock query_history_k_data_plus',
        'formal_window': [FORMAL_START, FORMAL_END],
        'fields': list(FIELDS),
        'frequency': 'd',
        'adjustflag': ADJUSTFLAG,
        'price_basis': 'RAW_UNADJUSTED_CANDIDATE',
        'login_error_code': login_code,
        'login_error_msg': login_msg,
        'pass_symbol_n': len(passing),
        'pass_symbols': passing,
        'fail_symbol_n': len(failing),
        'fail_symbols': failing,
        'daily_rows': len(all_rows),
        'raw_traded_rows': len(raw_rows),
        'daily_csv_sha256': _sha256(daily_path),
        'raw_traded_csv_sha256': _sha256(raw_path),
        'audits': audits,
        'formal_admission': False,
        'oos_metrics_allowed': False,
        'locked_interpretation': [
            'Probe PASS proves executable BaoStock retrieval and field-level integrity only.',
            'No probe row is promoted into the sealed Formal dataset by this workflow.',
            'Suspended rows are retained as PIT/ST evidence but are not treated as RAW traded bars.',
            'UNKNOWN/FAILED never defaults to valid RAW or NOT_ST.',
        ],
    }
    audit_path = out_dir / 'BAOSTOCK_FIXED5_PROBE_AUDIT_V482.json'
    audit_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'status': report['status'],
        'pass_symbol_n': report['pass_symbol_n'],
        'fail_symbol_n': report['fail_symbol_n'],
        'daily_rows': report['daily_rows'],
        'raw_traded_rows': report['raw_traded_rows'],
    }, ensure_ascii=False))
    return 0 if not failing else 1


if __name__ == '__main__':
    raise SystemExit(main())
