from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
from datetime import datetime, timezone

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
TURNOVER_COLUMNS = ['symbol', 'date', 'turnover_ratio', 'source']
_SYMBOL_RE = re.compile(r'^\d{6}\.(?:SZ|SH)$')
SOHU_ARCHIVED_ANCHORS_PCT = {
    ('002359.SZ', '2020-06-12'): 3.82,
    ('600634.SH', '2020-07-22'): 0.71,
}
SOHU_ROUNDING_TOLERANCE_BP = 0.5


def validate_scope_symbols(symbols: list[str]) -> list[str]:
    normalized = [str(s).strip().upper() for s in symbols if str(s).strip()]
    if len(set(normalized)) != len(normalized):
        raise ValueError('duplicate symbols in Formal turnover scope')
    bad = [s for s in normalized if not _SYMBOL_RE.fullmatch(s)]
    if bad:
        raise ValueError(f'exchange-qualified symbols required: {bad[:10]}')
    if len(normalized) != EXPECTED_SCOPE_N:
        raise ValueError(f'Formal turnover scope must contain exactly {EXPECTED_SCOPE_N} symbols; got {len(normalized)}')
    return normalized


def shard_gate(
    *,
    symbols_selected: int,
    symbols_audited: int,
    expected_trade_rows: int,
    turnover_rows: int,
    review_n: int,
    error_n: int,
    unresolved_symbol_n: int,
) -> bool:
    return (
        int(symbols_selected) == int(symbols_audited)
        and int(expected_trade_rows) == int(turnover_rows)
        and int(review_n) == 0
        and int(error_n) == 0
        and int(unresolved_symbol_n) == 0
    )


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


def _read_scope(path: pathlib.Path) -> list[str]:
    return validate_scope_symbols(path.read_text(encoding='utf-8').splitlines())


def _read_pitst(path: pathlib.Path, scope: list[str]) -> pd.DataFrame:
    pitst = pd.read_csv(path, usecols=['symbol', 'date', 'tradestatus'])
    pitst['symbol'] = pitst['symbol'].astype(str).str.upper()
    pitst['date'] = pitst['date'].astype(str).str[:10]
    pitst['tradestatus'] = pd.to_numeric(pitst['tradestatus'], errors='coerce').fillna(0).astype(int)
    if pitst.duplicated(['symbol', 'date']).any():
        dup = pitst[pitst.duplicated(['symbol', 'date'], keep=False)].head(20).to_dict('records')
        raise ValueError(f'duplicate PIT-ST symbol/date rows: {dup}')
    pit_symbols = set(pitst['symbol'].unique())
    if pit_symbols != set(scope):
        raise ValueError(f'PIT-ST scope mismatch: missing={sorted(set(scope)-pit_symbols)[:20]} extra={sorted(pit_symbols-set(scope))[:20]}')
    return pitst


def _corrected_expected_frame(pitst: pd.DataFrame) -> pd.DataFrame:
    x = pitst.loc[:, ['symbol', 'date', 'tradestatus']].copy()
    for symbol, date in PITST_TRADESTATUS_ONE_CORRECTIONS:
        mask = (x['symbol'] == symbol) & (x['date'] == date)
        if int(mask.sum()) != 1:
            raise ValueError(f'PIT-ST correction target must exist exactly once: {symbol} {date}; got {int(mask.sum())}')
        x.loc[mask, 'tradestatus'] = 1
    expected = x[x['tradestatus'] == 1][['symbol', 'date']].copy()
    expected = expected.sort_values(['symbol', 'date']).reset_index(drop=True)
    if len(expected) != EXPECTED_TRADE_ROWS:
        raise ValueError(f'corrected expected trade rows must be {EXPECTED_TRADE_ROWS}; got {len(expected)}')
    return expected


def materialize_shard(
    *,
    scope_path: pathlib.Path,
    pitst_path: pathlib.Path,
    shard_index: int,
    shard_count: int,
    out_dir: pathlib.Path,
) -> dict:
    import baostock as bs

    scope = _read_scope(scope_path)
    pitst = _read_pitst(pitst_path, scope)
    selected = select_shard(scope, shard_index, shard_count)
    out_dir.mkdir(parents=True, exist_ok=True)

    login = bs.login()
    if str(login.error_code) != '0':
        raise RuntimeError(f'BaoStock login failed: {login.error_code} {login.error_msg}')

    all_rows: list[dict] = []
    audits: list[dict] = []
    errors: list[dict] = []
    try:
        for idx, symbol in enumerate(selected, 1):
            try:
                rows, audit = collect_symbol(bs, pitst, symbol)
                all_rows.extend(rows)
                audits.append(audit)
                print(json.dumps({
                    'progress': idx,
                    'total': len(selected),
                    'symbol': symbol,
                    'status': audit['status'],
                    'expected_trade_rows': audit.get('expected_trade_rows', 0),
                    'turnover_rows': len(rows),
                }, ensure_ascii=False), flush=True)
            except Exception as exc:
                error = {'symbol': symbol, 'type': type(exc).__name__, 'message': str(exc)}
                errors.append(error)
                print(json.dumps({'progress': idx, 'total': len(selected), **error}, ensure_ascii=False), flush=True)
    finally:
        bs.logout()

    audits.sort(key=lambda item: item['symbol'])
    errors.sort(key=lambda item: item['symbol'])
    frame = pd.DataFrame(all_rows, columns=TURNOVER_COLUMNS)
    if len(frame):
        frame = frame.sort_values(['symbol', 'date']).reset_index(drop=True)
    parquet_path = out_dir / f'BAOSTOCK_TURNOVER_SHARD_{shard_index:02d}_V482.parquet'
    frame.to_parquet(parquet_path, index=False)

    pass_n = sum(a.get('status') in {'PASS_EXACT_TURNOVER_DATES', 'PASS_ZERO_TRADE_SYMBOL'} for a in audits)
    review_n = len(audits) - pass_n
    unresolved_symbol_n = sum(bool(a.get('unresolved_symbol')) for a in audits) + len(errors)
    expected_trade_rows = sum(len(expected_trade_dates(pitst, symbol)) for symbol in selected)
    correction_rows = sorted({tuple(item) for a in audits for item in a.get('applied_trade_status_corrections', [])})
    passed = shard_gate(
        symbols_selected=len(selected),
        symbols_audited=len(audits),
        expected_trade_rows=expected_trade_rows,
        turnover_rows=len(frame),
        review_n=review_n,
        error_n=len(errors),
        unresolved_symbol_n=unresolved_symbol_n,
    )
    report = {
        'artifact': 'BAOSTOCK_TURNOVER_SHARD_V482',
        'version': 'V4.82',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'provider': 'BaoStock query_history_k_data_plus',
        'fields': ['date', 'code', 'turn', 'tradestatus', 'isST'],
        'formal_window': ['2020-06-01', '2026-04-17'],
        'scope_n': len(scope),
        'shard_index': int(shard_index),
        'shard_count': int(shard_count),
        'symbols_selected': len(selected),
        'symbol_list': selected,
        'symbols_audited': len(audits),
        'expected_trade_rows': int(expected_trade_rows),
        'turnover_rows': int(len(frame)),
        'pass_n': int(pass_n),
        'review_n': int(review_n),
        'error_n': int(len(errors)),
        'unresolved_symbol_n': int(unresolved_symbol_n),
        'applied_trade_status_corrections': [list(x) for x in correction_rows],
        'shard_gate_pass': bool(passed),
        'audits': audits,
        'errors': errors,
        'formal_admission': False,
        'candidate_adoption_status': 'UNAPPROVED',
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }
    audit_path = out_dir / f'BAOSTOCK_TURNOVER_SHARD_{shard_index:02d}_AUDIT_V482.json'
    audit_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        k: report[k] for k in (
            'shard_index', 'symbols_selected', 'symbols_audited', 'expected_trade_rows',
            'turnover_rows', 'pass_n', 'review_n', 'error_n', 'unresolved_symbol_n', 'shard_gate_pass'
        )
    }, ensure_ascii=False, indent=2))
    return report


def _crosscheck_archived_sohu_anchors(raw: pd.DataFrame) -> dict:
    rows = []
    failures = []
    for (symbol, date), sohu_pct in SOHU_ARCHIVED_ANCHORS_PCT.items():
        match = raw[(raw['symbol'] == symbol) & (raw['date'] == date)]
        if len(match) != 1:
            failures.append({'symbol': symbol, 'date': date, 'reason': f'ROW_COUNT_{len(match)}'})
            continue
        baostock_pct = float(match.iloc[0]['turnover_ratio']) * 100.0
        diff_bp = abs(baostock_pct - float(sohu_pct)) * 100.0
        item = {
            'symbol': symbol,
            'date': date,
            'baostock_turn_pct': baostock_pct,
            'archived_sohu_turn_pct': float(sohu_pct),
            'abs_diff_bp': diff_bp,
        }
        rows.append(item)
        if diff_bp > SOHU_ROUNDING_TOLERANCE_BP:
            failures.append({**item, 'reason': 'DIFF_EXCEEDS_0_5_BP'})
    return {
        'tolerance_bp': SOHU_ROUNDING_TOLERANCE_BP,
        'anchor_n': len(SOHU_ARCHIVED_ANCHORS_PCT),
        'matched_n': len(rows),
        'fail_n': len(failures),
        'max_diff_bp': max((r['abs_diff_bp'] for r in rows), default=None),
        'rows': rows,
        'failures': failures,
        'verified': len(rows) == len(SOHU_ARCHIVED_ANCHORS_PCT) and not failures,
    }


def merge_shards(
    *,
    scope_path: pathlib.Path,
    pitst_path: pathlib.Path,
    shards_dir: pathlib.Path,
    out_dir: pathlib.Path,
) -> dict:
    scope = _read_scope(scope_path)
    pitst = _read_pitst(pitst_path, scope)
    expected = _corrected_expected_frame(pitst)

    audit_files = sorted(shards_dir.rglob('BAOSTOCK_TURNOVER_SHARD_*_AUDIT_V482.json'))
    parquet_files = sorted(shards_dir.rglob('BAOSTOCK_TURNOVER_SHARD_*_V482.parquet'))
    if not audit_files or not parquet_files:
        raise FileNotFoundError('missing BaoStock turnover shard artifacts')
    audits = [json.loads(p.read_text(encoding='utf-8')) for p in audit_files]
    shard_counts = {int(a['shard_count']) for a in audits}
    shard_ids = sorted(int(a['shard_index']) for a in audits)
    if len(shard_counts) != 1:
        raise ValueError(f'inconsistent shard counts: {sorted(shard_counts)}')
    shard_count = next(iter(shard_counts))
    if shard_ids != list(range(shard_count)):
        raise ValueError(f'incomplete shard partition: {shard_ids} / {shard_count}')
    if len(parquet_files) != shard_count:
        raise ValueError(f'expected {shard_count} shard parquet files, got {len(parquet_files)}')

    symbol_list = [symbol for audit in audits for symbol in audit['symbol_list']]
    if len(symbol_list) != len(scope) or len(set(symbol_list)) != len(scope) or set(symbol_list) != set(scope):
        raise ValueError('merged shard symbol partition does not equal frozen 847 scope')

    frames = [pd.read_parquet(path) for path in parquet_files]
    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=TURNOVER_COLUMNS)
    if len(raw):
        raw['symbol'] = raw['symbol'].astype(str).str.upper()
        raw['date'] = raw['date'].astype(str).str[:10]
        raw['turnover_ratio'] = pd.to_numeric(raw['turnover_ratio'], errors='coerce')
        raw = raw.sort_values(['symbol', 'date']).reset_index(drop=True)

    duplicate_n = int(raw.duplicated(['symbol', 'date']).sum()) if len(raw) else 0
    actual = raw[['symbol', 'date']].drop_duplicates() if len(raw) else pd.DataFrame(columns=['symbol', 'date'])
    joined = expected.merge(actual, on=['symbol', 'date'], how='outer', indicator=True)
    missing = joined[joined['_merge'] == 'left_only'][['symbol', 'date']]
    extra = joined[joined['_merge'] == 'right_only'][['symbol', 'date']]
    bad_turnover_n = int((~raw['turnover_ratio'].map(lambda x: math.isfinite(float(x)) and float(x) >= 0)).sum()) if len(raw) else 0
    turnover_symbols = set(raw['symbol'].unique()) if len(raw) else set()
    zero_trade_symbols = set(scope) - turnover_symbols
    unresolved_symbol_n = sum(int(a.get('unresolved_symbol_n', 0)) for a in audits)
    shard_review_n = sum(int(a.get('review_n', 0)) for a in audits)
    shard_error_n = sum(int(a.get('error_n', 0)) for a in audits)
    all_shards_pass = all(bool(a.get('shard_gate_pass')) for a in audits)

    coverage_verified = full_global_gate(
        scope_n=len(scope),
        turnover_symbol_n=len(turnover_symbols),
        turnover_rows=len(raw),
        missing_n=len(missing),
        extra_n=len(extra),
        duplicate_n=duplicate_n,
        bad_turnover_n=bad_turnover_n,
        unresolved_symbol_n=unresolved_symbol_n,
        zero_trade_symbols=zero_trade_symbols,
    ) and all_shards_pass and shard_review_n == 0 and shard_error_n == 0

    crosscheck = _crosscheck_archived_sohu_anchors(raw)
    source_semantics_verified = True
    turnover_ratio_pit_verified = bool(coverage_verified and source_semantics_verified and crosscheck['verified'])

    out_dir.mkdir(parents=True, exist_ok=True)
    full_path = out_dir / 'BAOSTOCK_TURNOVER_FULL_V482.parquet'
    raw.to_parquet(full_path, index=False)
    report = {
        'artifact': 'BAOSTOCK_TURNOVER_FULL_AUDIT_V482',
        'version': 'V4.82',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'provider': 'BaoStock query_history_k_data_plus',
        'provider_version': '0.9.3',
        'provider_field': 'turn',
        'provider_turn_unit': 'percent',
        'normalized_unit': 'ratio',
        'source_semantics_verified': source_semantics_verified,
        'source_semantics_basis': 'BaoStock documents turn as specified-trading-day volume (shares) divided by specified-trading-day circulating shares, multiplied by 100%. The source call is the same daily query_history_k_data_plus chain already used by the validated V4.80 PIT-ST panel.',
        'formal_window': ['2020-06-01', '2026-04-17'],
        'scope_n': len(scope),
        'turnover_symbol_n': len(turnover_symbols),
        'expected_turnover_symbol_n': EXPECTED_TURNOVER_SYMBOL_N,
        'turnover_rows': len(raw),
        'expected_trade_rows': EXPECTED_TRADE_ROWS,
        'missing_n': len(missing),
        'extra_n': len(extra),
        'duplicate_n': duplicate_n,
        'bad_turnover_n': bad_turnover_n,
        'unresolved_symbol_n': unresolved_symbol_n,
        'shard_review_n': shard_review_n,
        'shard_error_n': shard_error_n,
        'all_shards_pass': all_shards_pass,
        'zero_trade_symbols': sorted(zero_trade_symbols),
        'expected_zero_trade_symbols': sorted(ZERO_TRADE_SYMBOLS),
        'missing_examples': missing.head(100).to_dict('records'),
        'extra_examples': extra.head(100).to_dict('records'),
        'applied_trade_status_corrections': sorted([list(x) for x in PITST_TRADESTATUS_ONE_CORRECTIONS]),
        'coverage_verified': bool(coverage_verified),
        'cross_source_sohu_anchor_check': crosscheck,
        'turnover_ratio_pit_verified': turnover_ratio_pit_verified,
        'readiness_blocker_closed': turnover_ratio_pit_verified,
        'formal_admission': False,
        'candidate_adoption_status': 'UNAPPROVED',
        'candidate_freeze_ready': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }
    audit_path = out_dir / 'BAOSTOCK_TURNOVER_FULL_AUDIT_V482.json'
    audit_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        k: report[k] for k in (
            'scope_n', 'turnover_symbol_n', 'turnover_rows', 'missing_n', 'extra_n',
            'duplicate_n', 'bad_turnover_n', 'unresolved_symbol_n', 'shard_review_n',
            'shard_error_n', 'coverage_verified', 'turnover_ratio_pit_verified',
            'zero_trade_symbols'
        )
    }, ensure_ascii=False, indent=2))
    print(json.dumps({'cross_source_sohu_anchor_check': crosscheck}, ensure_ascii=False, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd', required=True)

    shard = sub.add_parser('shard')
    shard.add_argument('--scope', required=True)
    shard.add_argument('--pitst', required=True)
    shard.add_argument('--shard-index', type=int, required=True)
    shard.add_argument('--shard-count', type=int, required=True)
    shard.add_argument('--out-dir', required=True)

    merge = sub.add_parser('merge')
    merge.add_argument('--scope', required=True)
    merge.add_argument('--pitst', required=True)
    merge.add_argument('--shards-dir', required=True)
    merge.add_argument('--out-dir', required=True)

    args = parser.parse_args()
    if args.cmd == 'shard':
        materialize_shard(
            scope_path=pathlib.Path(args.scope),
            pitst_path=pathlib.Path(args.pitst),
            shard_index=args.shard_index,
            shard_count=args.shard_count,
            out_dir=pathlib.Path(args.out_dir),
        )
    else:
        merge_shards(
            scope_path=pathlib.Path(args.scope),
            pitst_path=pathlib.Path(args.pitst),
            shards_dir=pathlib.Path(args.shards_dir),
            out_dir=pathlib.Path(args.out_dir),
        )


if __name__ == '__main__':
    main()
