from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

from intraday_formal847_inventory_audit_v482 import norm_symbol
from intraday_minute_materialization_pilot_v482 import REQUIRED_COLUMNS, resample_day


FORMAL_START = '2020-06-01'
FORMAL_END = '2026-04-17'
SNAPSHOT_COMMIT = 'f311a5f11569e9d541386982d15f2214d9970b8a'
DATASET = 'neigezhu/china-a-share-1min-ohlcv'
ZERO_TRADE_SYMBOLS = {'600074.SH', '600485.SH', '600677.SH'}
PITST_TRADESTATUS_ONE_CORRECTIONS = {
    ('002087.SZ', '2024-06-13'),
    ('300356.SZ', '2023-06-20'),
    ('600647.SH', '2024-06-13'),
    ('600766.SH', '2024-06-13'),
    ('603133.SH', '2024-06-13'),
}
BAR_COLUMNS = [
    'symbol', 'trade_date', 'session', 'interval_minutes', 'source_start',
    'bar_end', 'source_rows', 'open', 'high', 'low', 'close', 'volume', 'turnover',
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def required_trade_dates(pitst: pd.DataFrame, symbol: str) -> list[str]:
    s = norm_symbol(symbol)
    df = pitst.copy()
    if not {'symbol', 'date', 'tradestatus'}.issubset(df.columns):
        raise ValueError('PIT/ST must contain symbol,date,tradestatus')
    df['symbol'] = df['symbol'].map(norm_symbol)
    df['date'] = df['date'].astype(str).str[:10]
    df['tradestatus'] = pd.to_numeric(df['tradestatus'], errors='coerce').fillna(0).astype(int)
    for corr_symbol, corr_date in PITST_TRADESTATUS_ONE_CORRECTIONS:
        if corr_symbol == s:
            mask = (df['symbol'] == corr_symbol) & (df['date'] == corr_date)
            if int(mask.sum()) == 1:
                df.loc[mask, 'tradestatus'] = 1
    g = df[
        (df['symbol'] == s)
        & (df['date'] >= FORMAL_START)
        & (df['date'] <= FORMAL_END)
        & (df['tradestatus'] == 1)
    ]
    return sorted(g['date'].drop_duplicates().tolist())


def _empty_bars() -> pd.DataFrame:
    return pd.DataFrame(columns=BAR_COLUMNS)


def _validate_required_values(day_frame: pd.DataFrame) -> None:
    numeric = ['open', 'high', 'low', 'close', 'volume', 'turnover']
    vals = day_frame[numeric].apply(pd.to_numeric, errors='coerce')
    if vals.isna().any().any():
        raise ValueError('required minute values contain non-numeric or NaN')
    if (vals[['open', 'high', 'low', 'close']] <= 0).any().any():
        raise ValueError('required minute OHLC must be positive')
    if (vals[['volume', 'turnover']] < 0).any().any():
        raise ValueError('required minute volume/turnover must be non-negative')


def _index_required_days(df: pd.DataFrame, required_dates: list[str]) -> dict[str, pd.DataFrame]:
    if '_date' not in df.columns:
        raise ValueError('indexed minute frame must contain _date')
    wanted = {str(d)[:10] for d in required_dates}
    if not wanted:
        return {}
    required_frame = df[df['_date'].isin(wanted)]
    return {
        str(day): group.drop(columns=['_date']).copy()
        for day, group in required_frame.groupby('_date', sort=False)
    }


def audit_source_frame(source: pd.DataFrame, required_dates: list[str], symbol: str):
    s = norm_symbol(symbol)
    required = sorted(set(str(d)[:10] for d in required_dates if FORMAL_START <= str(d)[:10] <= FORMAL_END))
    if not required:
        status = 'EXPECTED_ZERO_TRADE_NA' if s in ZERO_TRADE_SYMBOLS else 'UNEXPECTED_ZERO_REQUIRED_DATES'
        return _empty_bars(), _empty_bars(), {
            'symbol': s,
            'status': status,
            'required_trade_dates': 0,
            'valid_trade_dates': 0,
            'missing_trade_dates': [],
            'invalid_grid_dates': [],
            'source_rows_required_dates': 0,
            'coverage_accounted': s in ZERO_TRADE_SYMBOLS,
        }

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in source.columns]
    if missing_cols:
        raise ValueError(f'missing required source columns: {missing_cols}')
    df = source[REQUIRED_COLUMNS].copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    if df['timestamp'].isna().any():
        raise ValueError('source contains invalid timestamps')
    df['_date'] = df['timestamp'].dt.strftime('%Y-%m-%d')
    indexed_days = _index_required_days(df, required)

    bars15_parts = []
    bars60_parts = []
    missing = []
    invalid = []
    valid = 0
    source_rows_required = 0
    for d in required:
        day = indexed_days.get(d)
        if day is None:
            missing.append(d)
            continue
        source_rows_required += int(len(day))
        day = day.copy()
        day['symbol'] = s
        try:
            _validate_required_values(day)
            b15 = resample_day(day, 15)
            b60 = resample_day(day, 60)
            if len(b15) != 16 or len(b60) != 4:
                raise ValueError(f'bar count mismatch: 15m={len(b15)} 60m={len(b60)}')
            bars15_parts.append(b15)
            bars60_parts.append(b60)
            valid += 1
        except Exception as exc:
            invalid.append({'date': d, 'type': type(exc).__name__, 'message': str(exc)})

    bars15 = pd.concat(bars15_parts, ignore_index=True) if bars15_parts else _empty_bars()
    bars60 = pd.concat(bars60_parts, ignore_index=True) if bars60_parts else _empty_bars()
    exact = not missing and not invalid and valid == len(required)
    return bars15, bars60, {
        'symbol': s,
        'status': 'PASS_REQUIRED_TRADE_DATES_EXACT' if exact else 'REVIEW_REQUIRED_TRADE_DATES',
        'required_trade_dates': len(required),
        'valid_trade_dates': valid,
        'missing_trade_dates': missing,
        'invalid_grid_dates': invalid,
        'source_rows_required_dates': source_rows_required,
        'coverage_accounted': exact,
    }


def _download_fixed_snapshot(canonical_path: str, dest: Path, retries: int = 4, timeout: int = 180) -> dict:
    encoded_path = quote(canonical_path, safe='/')
    url = f'https://huggingface.co/datasets/{DATASET}/resolve/{SNAPSHOT_COMMIT}/{encoded_path}?download=true'
    dest.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=(30, timeout), allow_redirects=True) as r:
                r.raise_for_status()
                with dest.open('wb') as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                if dest.stat().st_size <= 0:
                    raise ValueError('downloaded file is empty')
                return {
                    'http_status': int(r.status_code),
                    'resolved_url_host': r.url.split('/')[2] if '://' in r.url else '',
                    'etag': r.headers.get('etag'),
                    'x_linked_etag': r.headers.get('x-linked-etag'),
                    'bytes': dest.stat().st_size,
                    'sha256': sha256_file(dest),
                }
        except Exception as exc:
            last = exc
            if dest.exists():
                dest.unlink()
            if attempt < retries:
                time.sleep(min(8, 2 ** (attempt - 1)))
    raise RuntimeError(f'fixed snapshot download failed after {retries} attempts: {type(last).__name__}: {last}')


def _parquet_identity(path: Path, rows: int) -> dict:
    return {'path': path.name, 'sha256': sha256_file(path), 'bytes': path.stat().st_size, 'rows': int(rows)}


def materialize_shard(
    pitst_path: Path,
    inventory_path: Path,
    shard_index: int,
    shard_count: int,
    out_dir: Path,
    cache_dir: Path,
) -> dict:
    if shard_count <= 0 or not 0 <= shard_index < shard_count:
        raise ValueError('invalid shard index/count')
    pit = pd.read_csv(pitst_path, dtype={'symbol': 'string', 'date': 'string'})
    inventory = pd.read_csv(inventory_path, dtype='string', keep_default_na=False)
    if len(inventory) != 847 or inventory['_norm_symbol'].nunique() != 847:
        raise ValueError('inventory map must contain exactly 847 unique symbols')
    inventory['_norm_symbol'] = inventory['_norm_symbol'].map(norm_symbol)
    inventory = inventory.set_index('_norm_symbol', drop=False)
    symbols = sorted(inventory.index.tolist())
    selected = symbols[shard_index::shard_count]

    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    records = []
    bars15_parts = []
    bars60_parts = []

    for i, symbol in enumerate(selected, 1):
        req = required_trade_dates(pit, symbol)
        base = {
            'symbol': symbol,
            'canonical_path': str(inventory.loc[symbol, 'file']),
            'required_trade_dates': len(req),
            'required_start': req[0] if req else None,
            'required_end': req[-1] if req else None,
            'snapshot_commit': SNAPSHOT_COMMIT,
        }
        if not req:
            _b15, _b60, audit = audit_source_frame(pd.DataFrame(), req, symbol)
            records.append({**base, **audit, 'source_downloaded': False, 'source_sha256': None, 'source_bytes': 0})
            print(json.dumps({'progress': i, 'total': len(selected), 'symbol': symbol, 'status': audit['status']}, ensure_ascii=False), flush=True)
            continue

        local = cache_dir / f'{symbol.replace(".", "_")}.parquet'
        try:
            dl = _download_fixed_snapshot(base['canonical_path'], local)
            source = pd.read_parquet(local, columns=REQUIRED_COLUMNS)
            b15, b60, audit = audit_source_frame(source, req, symbol)
            if not b15.empty:
                bars15_parts.append(b15)
            if not b60.empty:
                bars60_parts.append(b60)
            records.append({
                **base,
                **audit,
                'source_downloaded': True,
                'source_sha256': dl['sha256'],
                'source_bytes': dl['bytes'],
                'source_rows_total': int(len(source)),
                'http_status': dl['http_status'],
                'etag': dl['etag'],
                'x_linked_etag': dl['x_linked_etag'],
            })
        except Exception as exc:
            records.append({
                **base,
                'status': 'ERROR_SOURCE_OR_PARSE',
                'valid_trade_dates': 0,
                'missing_trade_dates': req,
                'invalid_grid_dates': [],
                'source_rows_required_dates': 0,
                'coverage_accounted': False,
                'source_downloaded': local.exists(),
                'source_sha256': sha256_file(local) if local.exists() else None,
                'source_bytes': local.stat().st_size if local.exists() else 0,
                'error_type': type(exc).__name__,
                'error_message': str(exc),
            })
        finally:
            if local.exists():
                local.unlink()
        print(json.dumps({
            'progress': i,
            'total': len(selected),
            'symbol': symbol,
            'status': records[-1]['status'],
            'required': len(req),
            'valid': records[-1].get('valid_trade_dates', 0),
        }, ensure_ascii=False), flush=True)

    bars15 = pd.concat(bars15_parts, ignore_index=True) if bars15_parts else _empty_bars()
    bars60 = pd.concat(bars60_parts, ignore_index=True) if bars60_parts else _empty_bars()
    out15 = out_dir / f'INTRADAY_FORMAL847_SHARD_{shard_index:02d}_15M_V482.parquet'
    out60 = out_dir / f'INTRADAY_FORMAL847_SHARD_{shard_index:02d}_60M_V482.parquet'
    bars15.to_parquet(out15, index=False)
    bars60.to_parquet(out60, index=False)

    records_df = pd.DataFrame(records)
    records_csv = out_dir / f'INTRADAY_FORMAL847_SHARD_{shard_index:02d}_COVERAGE_V482.csv'
    records_df.to_csv(records_csv, index=False)
    pass_n = sum(r['status'] == 'PASS_REQUIRED_TRADE_DATES_EXACT' for r in records)
    zero_n = sum(r['status'] == 'EXPECTED_ZERO_TRADE_NA' for r in records)
    review_n = len(records) - pass_n - zero_n
    report = {
        'artifact': 'INTRADAY_FORMAL847_MATERIALIZATION_SHARD_V482',
        'version': 'V4.82',
        'status': 'PASS_SHARD_REQUIRED_DATE_COVERAGE' if review_n == 0 else 'REVIEW_SHARD_REQUIRED_DATE_COVERAGE',
        'scope': 'FORMAL_WINDOW_REQUIRED_TRADE_DATES_ONLY_NOT_HISTORICAL_GP_FACTOR_AUTHORITY',
        'formal_start': FORMAL_START,
        'formal_end': FORMAL_END,
        'dataset': DATASET,
        'snapshot_commit': SNAPSHOT_COMMIT,
        'shard_index': shard_index,
        'shard_count': shard_count,
        'symbols_selected': len(selected),
        'symbol_list': selected,
        'pass_symbols': pass_n,
        'expected_zero_trade_symbols': zero_n,
        'review_symbols': review_n,
        'required_trade_dates': sum(int(r['required_trade_dates']) for r in records),
        'valid_trade_dates': sum(int(r.get('valid_trade_dates', 0)) for r in records),
        'missing_trade_dates': sum(len(r.get('missing_trade_dates', [])) for r in records),
        'invalid_grid_dates': sum(len(r.get('invalid_grid_dates', [])) for r in records),
        'source_bytes_downloaded': sum(int(r.get('source_bytes', 0)) for r in records),
        'bars_15m': _parquet_identity(out15, len(bars15)),
        'bars_60m': _parquet_identity(out60, len(bars60)),
        'coverage_csv': _parquet_identity(records_csv, len(records)),
        'records': records,
        'shard_required_date_coverage_verified': review_n == 0,
        'formal_847_minute_byte_coverage_verified': False,
        'formal_847_15m_coverage_verified': False,
        'formal_847_60m_coverage_verified': False,
        'historical_gp_intraday_resampling_contract_recovered': False,
        'factor_formula_recovered': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }
    report_path = out_dir / f'INTRADAY_FORMAL847_SHARD_{shard_index:02d}_AUDIT_V482.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({
        k: report[k]
        for k in [
            'status', 'shard_index', 'symbols_selected', 'pass_symbols',
            'expected_zero_trade_symbols', 'review_symbols', 'required_trade_dates',
            'valid_trade_dates', 'missing_trade_dates', 'invalid_grid_dates',
            'source_bytes_downloaded',
        ]
    }, ensure_ascii=False, indent=2), flush=True)
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('shard')
    s.add_argument('--pitst', required=True)
    s.add_argument('--inventory', required=True)
    s.add_argument('--shard-index', type=int, required=True)
    s.add_argument('--shard-count', type=int, required=True)
    s.add_argument('--out-dir', required=True)
    s.add_argument('--cache-dir', required=True)
    a = ap.parse_args()
    if a.cmd == 'shard':
        materialize_shard(
            Path(a.pitst),
            Path(a.inventory),
            a.shard_index,
            a.shard_count,
            Path(a.out_dir),
            Path(a.cache_dir),
        )


if __name__ == '__main__':
    main()
