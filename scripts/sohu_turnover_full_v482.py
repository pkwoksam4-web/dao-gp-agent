from __future__ import annotations

import argparse
import json
import pathlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

import pandas as pd
import requests

from sohu_full_panel_v482 import (
    PITST_TRADESTATUS_ONE_CORRECTIONS,
    ZERO_TRADE_SYMBOLS,
    _read_pitst,
    expected_trade_dates,
)
from sohu_raw_v482 import BASE_HTTP, BASE_HTTPS
from sohu_turnover_v482 import (
    audit_trade_dates,
    build_request_params,
    full_turnover_global_gate,
    merge_turnover_rows_unique,
    normalize_symbol,
    parse_hishq_turnover_bytes,
    plan_chunks,
    select_shard,
)

FIELDS = ['symbol', 'date', 'turnover_ratio', 'source']
EXPECTED_SYMBOL_LIST_N = 847
EXPECTED_TURNOVER_SYMBOL_N = 844
EXPECTED_TRADE_ROWS = 1_011_607


def _request_once(session: requests.Session, symbol: str, start: str, end: str, timeout: int, base: str) -> list[dict]:
    code = normalize_symbol(symbol).split('.', 1)[0]
    response = session.get(
        base,
        params=build_request_params(symbol, start, end),
        timeout=timeout,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36',
            'Referer': f'https://q.stock.sohu.com/cn/{code}/lshq.shtml',
            'Connection': 'close',
            'Accept': '*/*',
        },
    )
    response.raise_for_status()
    return parse_hishq_turnover_bytes(symbol, response.content)


def fetch_chunk(session: requests.Session, symbol: str, start: str, end: str, *, timeout: int = 20, retries: int = 3) -> list[dict]:
    last = None
    for attempt in range(1, int(retries) + 1):
        for base in (BASE_HTTPS, BASE_HTTP):
            try:
                return _request_once(session, symbol, start, end, timeout, base)
            except ValueError:
                raise
            except Exception as exc:
                last = exc
        if attempt < int(retries):
            time.sleep(0.8 * attempt)
    raise RuntimeError(f'Sohu turnover fetch failed for {normalize_symbol(symbol)} {start}..{end}: {last}')


def fetch_chunk_resilient(
    session: requests.Session,
    symbol: str,
    start: str,
    end: str,
    *,
    timeout: int = 20,
    retries: int = 3,
) -> tuple[list[dict], dict]:
    a = date.fromisoformat(start)
    b = date.fromisoformat(end)
    try:
        rows = fetch_chunk(session, symbol, start, end, timeout=timeout, retries=retries)
        return rows, {
            'split_recovery_n': 0,
            'leaf_chunk_n': 1,
            'leaf_nonempty_n': int(bool(rows)),
            'max_leaf_rows': len(rows),
        }
    except ValueError:
        raise
    except RuntimeError:
        days = (b - a).days + 1
        if days <= 1:
            raise
        mid = a + timedelta(days=(days // 2) - 1)
        right_start = mid + timedelta(days=1)
        time.sleep(0.25)
        left, lm = fetch_chunk_resilient(session, symbol, a.isoformat(), mid.isoformat(), timeout=timeout, retries=retries)
        right, rm = fetch_chunk_resilient(session, symbol, right_start.isoformat(), b.isoformat(), timeout=timeout, retries=retries)
        rows = merge_turnover_rows_unique(symbol, left, right)
        return rows, {
            'split_recovery_n': 1 + lm['split_recovery_n'] + rm['split_recovery_n'],
            'leaf_chunk_n': lm['leaf_chunk_n'] + rm['leaf_chunk_n'],
            'leaf_nonempty_n': lm['leaf_nonempty_n'] + rm['leaf_nonempty_n'],
            'max_leaf_rows': max(lm['max_leaf_rows'], rm['max_leaf_rows']),
        }


def fetch_symbol_turnover(
    symbol: str,
    start: str,
    end: str,
    *,
    max_calendar_days: int = 90,
    timeout: int = 20,
    retries: int = 3,
    delay: float = 0.05,
) -> tuple[list[dict], dict]:
    normalized = normalize_symbol(symbol)
    session = requests.Session()
    parts = []
    chunk_rows = []
    split_recovery_n = 0
    leaf_chunk_n = 0
    leaf_nonempty_n = 0
    max_leaf_rows = 0
    chunks = plan_chunks(start, end, max_calendar_days=max_calendar_days)
    try:
        for chunk_start, chunk_end in chunks:
            rows, meta = fetch_chunk_resilient(
                session, normalized, chunk_start, chunk_end,
                timeout=timeout, retries=retries,
            )
            if len(rows) >= 80:
                raise RuntimeError(
                    f'Sohu turnover chunk may be truncated ({len(rows)} rows) '
                    f'{normalized} {chunk_start}..{chunk_end}'
                )
            parts.append(rows)
            chunk_rows.append(len(rows))
            split_recovery_n += meta['split_recovery_n']
            leaf_chunk_n += meta['leaf_chunk_n']
            leaf_nonempty_n += meta['leaf_nonempty_n']
            max_leaf_rows = max(max_leaf_rows, meta['max_leaf_rows'])
            if delay > 0:
                time.sleep(delay)
    finally:
        session.close()
    rows = merge_turnover_rows_unique(normalized, *parts)
    return rows, {
        'chunk_n': len(chunks),
        'chunk_nonempty_n': sum(value > 0 for value in chunk_rows),
        'max_chunk_rows': max(chunk_rows) if chunk_rows else 0,
        'empty_chunk_n': sum(value == 0 for value in chunk_rows),
        'split_recovery_n': split_recovery_n,
        'leaf_chunk_n': leaf_chunk_n,
        'leaf_nonempty_n': leaf_nonempty_n,
        'max_leaf_rows': max_leaf_rows,
    }


def materialize_shard(
    pitst_path: pathlib.Path,
    shard_index: int,
    shard_count: int,
    out_dir: pathlib.Path,
    *,
    workers: int = 1,
    timeout: int = 20,
) -> dict:
    pitst = _read_pitst(pitst_path)
    symbols = sorted(pitst['symbol'].drop_duplicates().tolist())
    selected = select_shard(symbols, shard_index, shard_count)
    expected = {symbol: expected_trade_dates(pitst, symbol) for symbol in selected}
    out_dir.mkdir(parents=True, exist_ok=True)
    all_rows = []
    audits = []
    errors = []

    def one(symbol: str):
        exp = expected[symbol]
        if not exp:
            rows = []
            meta = {
                'chunk_n': 0, 'chunk_nonempty_n': 0, 'max_chunk_rows': 0,
                'empty_chunk_n': 0, 'split_recovery_n': 0, 'leaf_chunk_n': 0,
                'leaf_nonempty_n': 0, 'max_leaf_rows': 0,
            }
        else:
            rows, meta = fetch_symbol_turnover(
                symbol, exp[0], exp[-1], max_calendar_days=90,
                timeout=timeout, retries=3, delay=0.05,
            )
        audit = audit_trade_dates(symbol, exp, rows)
        audit.update(meta)
        return rows, audit

    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        futures = {pool.submit(one, symbol): symbol for symbol in selected}
        for progress, future in enumerate(as_completed(futures), 1):
            symbol = futures[future]
            try:
                rows, audit = future.result()
                all_rows.extend(rows)
                audits.append(audit)
                print(json.dumps({
                    'progress': progress, 'total': len(selected), 'symbol': symbol,
                    'status': audit['status'], 'rows': len(rows),
                }, ensure_ascii=False), flush=True)
            except Exception as exc:
                error = {'symbol': symbol, 'type': type(exc).__name__, 'message': str(exc)}
                errors.append(error)
                print(json.dumps({'progress': progress, 'total': len(selected), **error}, ensure_ascii=False), flush=True)

    audits.sort(key=lambda row: row['symbol'])
    errors.sort(key=lambda row: row['symbol'])
    frame = pd.DataFrame(all_rows, columns=FIELDS)
    if len(frame):
        frame = frame.sort_values(['symbol', 'date']).reset_index(drop=True)
    frame.to_parquet(out_dir / f'SOHU_TURNOVER_SHARD_{shard_index:02d}_V482.parquet', index=False)
    pass_n = sum(row['status'] == 'PASS_EXACT_TURNOVER_DATES' for row in audits)
    review_n = len(audits) - pass_n
    report = {
        'artifact': 'SOHU_TURNOVER_SHARD_V482',
        'version': 'V4.82',
        'shard_index': shard_index,
        'shard_count': shard_count,
        'symbols_selected': len(selected),
        'symbol_list': selected,
        'expected_trade_rows': sum(len(expected[symbol]) for symbol in selected),
        'turnover_rows': len(frame),
        'pass_n': pass_n,
        'review_n': review_n,
        'error_n': len(errors),
        'pitst_trade_corrections': sorted([list(item) for item in PITST_TRADESTATUS_ONE_CORRECTIONS]),
        'audits': audits,
        'errors': errors,
        'coverage_verified': False,
        'turnover_ratio_pit_verified': False,
        'formal_admission': False,
        'oos_metrics_allowed': False,
    }
    (out_dir / f'SOHU_TURNOVER_SHARD_{shard_index:02d}_AUDIT_V482.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: report[key] for key in (
        'shard_index', 'symbols_selected', 'expected_trade_rows', 'turnover_rows',
        'pass_n', 'review_n', 'error_n')}, ensure_ascii=False, indent=2))
    return report


def merge_shards(shards_dir: pathlib.Path, pitst_path: pathlib.Path, out_dir: pathlib.Path) -> dict:
    pitst = _read_pitst(pitst_path)
    expected = pitst[pd.to_numeric(pitst['tradestatus'], errors='coerce').fillna(0).astype(int) == 1][['symbol', 'date']].copy()
    expected = expected.drop_duplicates().sort_values(['symbol', 'date']).reset_index(drop=True)
    if len(expected) != EXPECTED_TRADE_ROWS:
        raise ValueError(f'PIT-ST expected trade rows {len(expected)} != {EXPECTED_TRADE_ROWS}')

    audit_files = sorted(shards_dir.rglob('SOHU_TURNOVER_SHARD_*_AUDIT_V482.json'))
    parquet_files = sorted(shards_dir.rglob('SOHU_TURNOVER_SHARD_*_V482.parquet'))
    if not audit_files or not parquet_files:
        raise FileNotFoundError('missing turnover shard artifacts')
    audits = [json.loads(path.read_text(encoding='utf-8')) for path in audit_files]
    shard_ids = [int(row['shard_index']) for row in audits]
    shard_counts = {int(row['shard_count']) for row in audits}
    if len(shard_counts) != 1 or sorted(shard_ids) != list(range(next(iter(shard_counts)))):
        raise ValueError(f'incomplete turnover shard partition: ids={shard_ids} counts={shard_counts}')

    symbol_lists = [symbol for audit in audits for symbol in audit['symbol_list']]
    frames = [pd.read_parquet(path) for path in parquet_files]
    turnover = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=FIELDS)
    if len(turnover):
        turnover['symbol'] = turnover['symbol'].astype(str).str.upper()
        turnover['date'] = turnover['date'].astype(str).str[:10]
        turnover['turnover_ratio'] = pd.to_numeric(turnover['turnover_ratio'], errors='coerce')
        turnover = turnover.sort_values(['symbol', 'date']).reset_index(drop=True)
    duplicate_rows = int(turnover.duplicated(['symbol', 'date']).sum()) if len(turnover) else 0
    actual = turnover[['symbol', 'date']].drop_duplicates() if len(turnover) else pd.DataFrame(columns=['symbol', 'date'])
    joined = expected.merge(actual, on=['symbol', 'date'], how='outer', indicator=True)
    missing = joined[joined['_merge'] == 'left_only'][['symbol', 'date']]
    extra = joined[joined['_merge'] == 'right_only'][['symbol', 'date']]
    bad_turnover = int((~turnover['turnover_ratio'].map(lambda value: pd.notna(value) and float(value) >= 0)).sum()) if len(turnover) else 0
    shard_review = sum(int(row['review_n']) for row in audits)
    shard_error = sum(int(row['error_n']) for row in audits)
    actual_symbol_n = int(turnover['symbol'].nunique()) if len(turnover) else 0

    global_pass = full_turnover_global_gate(
        unique_symbol_n=actual_symbol_n,
        symbol_list_n=len(symbol_lists),
        turnover_rows=len(turnover),
        duplicate_rows=duplicate_rows,
        missing_n=len(missing),
        extra_n=len(extra),
        bad_turnover_n=bad_turnover,
        shard_error=shard_error,
    )
    zero_trade_symbols = sorted(set(pitst['symbol']) - set(turnover['symbol'])) if len(turnover) else sorted(set(pitst['symbol']))
    status = 'PASS_FULL_TURNOVER_COVERAGE_V482' if global_pass else 'REVIEW_FULL_TURNOVER_COVERAGE_V482'
    out_dir.mkdir(parents=True, exist_ok=True)
    turnover.to_parquet(out_dir / 'SOHU_TURNOVER_FULL_V482.parquet', index=False)
    report = {
        'artifact': 'SOHU_TURNOVER_FULL_V482',
        'version': 'V4.82',
        'status': status,
        'symbol_list_n': len(symbol_lists),
        'turnover_symbol_n': actual_symbol_n,
        'expected_turnover_symbol_n': EXPECTED_TURNOVER_SYMBOL_N,
        'turnover_rows': len(turnover),
        'expected_trade_rows': EXPECTED_TRADE_ROWS,
        'duplicate_symbol_dates': duplicate_rows,
        'missing_trade_dates_n': len(missing),
        'extra_trade_dates_n': len(extra),
        'missing_trade_dates': missing.head(200).to_dict('records'),
        'extra_trade_dates': extra.head(200).to_dict('records'),
        'bad_turnover_rows': bad_turnover,
        'shard_review_n': shard_review,
        'shard_error_n': shard_error,
        'zero_trade_symbols': zero_trade_symbols,
        'expected_zero_trade_symbols': sorted(ZERO_TRADE_SYMBOLS),
        'coverage_verified': global_pass,
        'turnover_unit': 'ratio; Sohu historical turnover percent divided by 100',
        'archived_cross_source_semantics': {
            'symbol': '600634.SH',
            'dates': ['2020-07-20', '2020-07-22', '2020-09-24'],
            'sohu_percent': [0.77, 0.71, 1.21],
            'eastmoney_percent': [0.77, 0.71, 1.21],
            'matched_n': 3,
            'max_diff_bp': 0.0,
        },
        'turnover_ratio_pit_verified': False,
        'pit_state': 'PIT_UNVERIFIED_PENDING_REVISION_SEMANTICS',
        'readiness_blocker_closed': False,
        'formal_admission': False,
        'candidate_adoption_status': 'UNAPPROVED',
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }
    (out_dir / 'SOHU_TURNOVER_FULL_AUDIT_V482.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: report[key] for key in (
        'status', 'symbol_list_n', 'turnover_symbol_n', 'turnover_rows',
        'missing_trade_dates_n', 'extra_trade_dates_n', 'bad_turnover_rows',
        'shard_review_n', 'shard_error_n', 'zero_trade_symbols',
        'coverage_verified', 'turnover_ratio_pit_verified')}, ensure_ascii=False, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd', required=True)
    shard = sub.add_parser('shard')
    shard.add_argument('--pitst', required=True)
    shard.add_argument('--shard-index', type=int, required=True)
    shard.add_argument('--shard-count', type=int, required=True)
    shard.add_argument('--out-dir', required=True)
    shard.add_argument('--workers', type=int, default=1)
    shard.add_argument('--timeout', type=int, default=20)
    merge = sub.add_parser('merge')
    merge.add_argument('--pitst', required=True)
    merge.add_argument('--shards-dir', required=True)
    merge.add_argument('--out-dir', required=True)
    args = parser.parse_args()
    if args.cmd == 'shard':
        materialize_shard(
            pathlib.Path(args.pitst), args.shard_index, args.shard_count,
            pathlib.Path(args.out_dir), workers=args.workers, timeout=args.timeout)
    else:
        merge_shards(pathlib.Path(args.shards_dir), pathlib.Path(args.pitst), pathlib.Path(args.out_dir))


if __name__ == '__main__':
    main()
