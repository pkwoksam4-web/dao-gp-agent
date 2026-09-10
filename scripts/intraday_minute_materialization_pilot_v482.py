from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = ['symbol', 'timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover']
ALLOWED_INTERVALS = {15, 60}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _expected_grid(day: pd.Timestamp) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex, pd.DatetimeIndex]:
    day = pd.Timestamp(day).normalize()
    marker = pd.DatetimeIndex([day + pd.Timedelta(hours=9, minutes=30)])
    am = pd.date_range(day + pd.Timedelta(hours=9, minutes=31), day + pd.Timedelta(hours=11, minutes=30), freq='1min')
    pm = pd.date_range(day + pd.Timedelta(hours=13, minutes=1), day + pd.Timedelta(hours=15), freq='1min')
    return marker, am, pm


def split_and_validate_day(day_frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    missing_columns = [c for c in REQUIRED_COLUMNS if c not in day_frame.columns]
    if missing_columns:
        raise ValueError(f'missing required columns: {missing_columns}')

    df = day_frame.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)

    if df['timestamp'].duplicated().any():
        raise ValueError('duplicate timestamp')
    if df.empty:
        raise ValueError('empty day')

    dates = df['timestamp'].dt.normalize().unique()
    if len(dates) != 1:
        raise ValueError('split_and_validate_day requires exactly one trade date')

    marker_grid, am_grid, pm_grid = _expected_grid(pd.Timestamp(dates[0]))
    expected = marker_grid.append(am_grid).append(pm_grid)
    actual = pd.DatetimeIndex(df['timestamp'])
    if len(actual) != 241 or not actual.equals(expected):
        raise ValueError('continuous session minute grid mismatch')

    marker = df.iloc[[0]].copy().reset_index(drop=True)
    continuous = df.iloc[1:].copy().reset_index(drop=True)
    return continuous, marker


def _aggregate_chunk(chunk: pd.DataFrame, session: str, interval_minutes: int) -> dict:
    return {
        'symbol': str(chunk.iloc[0]['symbol']),
        'trade_date': pd.Timestamp(chunk.iloc[0]['timestamp']).normalize(),
        'session': session,
        'interval_minutes': interval_minutes,
        'source_start': pd.Timestamp(chunk.iloc[0]['timestamp']),
        'bar_end': pd.Timestamp(chunk.iloc[-1]['timestamp']),
        'source_rows': int(len(chunk)),
        'open': float(chunk.iloc[0]['open']),
        'high': float(chunk['high'].max()),
        'low': float(chunk['low'].min()),
        'close': float(chunk.iloc[-1]['close']),
        'volume': int(chunk['volume'].sum()),
        'turnover': float(chunk['turnover'].sum()),
    }


def resample_day(day_frame: pd.DataFrame, interval_minutes: int) -> pd.DataFrame:
    if interval_minutes not in ALLOWED_INTERVALS:
        raise ValueError('interval_minutes must be 15 or 60')

    continuous, _marker = split_and_validate_day(day_frame)
    am = continuous.iloc[:120].reset_index(drop=True)
    pm = continuous.iloc[120:].reset_index(drop=True)

    rows = []
    for session_name, frame in [('AM', am), ('PM', pm)]:
        if len(frame) != 120:
            raise ValueError('continuous session minute grid mismatch')
        for start in range(0, 120, interval_minutes):
            chunk = frame.iloc[start:start + interval_minutes]
            if len(chunk) != interval_minutes:
                raise ValueError('continuous session minute grid mismatch')
            rows.append(_aggregate_chunk(chunk, session_name, interval_minutes))
    return pd.DataFrame(rows)


def resample_all(source: pd.DataFrame, interval_minutes: int) -> pd.DataFrame:
    if interval_minutes not in ALLOWED_INTERVALS:
        raise ValueError('interval_minutes must be 15 or 60')
    df = source.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    if df['timestamp'].duplicated().any():
        raise ValueError('duplicate timestamp')
    df['_trade_date'] = df['timestamp'].dt.normalize()

    parts = []
    for _, day_frame in df.groupby('_trade_date', sort=True):
        parts.append(resample_day(day_frame.drop(columns=['_trade_date']), interval_minutes))
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def _parquet_identity(path: Path, frame: pd.DataFrame) -> dict:
    return {
        'path': path.name,
        'sha256': sha256_file(path),
        'bytes': path.stat().st_size,
        'rows': int(len(frame)),
        'schema': [{'name': str(c), 'dtype': str(frame[c].dtype)} for c in frame.columns],
    }


def materialize(input_path: Path, out_dir: Path, symbol: str, snapshot_commit: str, canonical_path: str, expected_sha256: str) -> dict:
    actual_sha = sha256_file(input_path)
    if actual_sha != expected_sha256:
        raise ValueError(f'source sha256 mismatch: expected {expected_sha256}, got {actual_sha}')

    source = pd.read_parquet(input_path)
    missing_columns = [c for c in REQUIRED_COLUMNS if c not in source.columns]
    if missing_columns:
        raise ValueError(f'missing required columns: {missing_columns}')
    source = source[REQUIRED_COLUMNS].copy()
    source['timestamp'] = pd.to_datetime(source['timestamp'])
    source = source.sort_values('timestamp').reset_index(drop=True)

    if source['timestamp'].duplicated().any():
        raise ValueError('duplicate timestamp')
    dates = source['timestamp'].dt.normalize()
    day_counts = source.groupby(dates).size()
    if day_counts.empty or not (day_counts == 241).all():
        raise ValueError('source day row count is not exactly 241 for every date')

    bars15 = resample_all(source, 15)
    bars60 = resample_all(source, 60)
    trading_dates = int(day_counts.size)
    if len(bars15) != trading_dates * 16:
        raise ValueError('15m output row count mismatch')
    if len(bars60) != trading_dates * 4:
        raise ValueError('60m output row count mismatch')
    if not (bars15['source_rows'] == 15).all() or not (bars60['source_rows'] == 60).all():
        raise ValueError('resampled source row count mismatch')

    out_dir.mkdir(parents=True, exist_ok=True)
    out15 = out_dir / '002002_15M_F311A5F.parquet'
    out60 = out_dir / '002002_60M_F311A5F.parquet'
    bars15.to_parquet(out15, index=False)
    bars60.to_parquet(out60, index=False)

    first15 = bars15.iloc[0]
    last15 = bars15.iloc[-1]
    first60 = bars60.iloc[0]
    last60 = bars60.iloc[-1]

    evidence = {
        'artifact': 'INTRADAY_MINUTE_MATERIALIZATION_PILOT_V482',
        'version': 'V4.82',
        'status': 'PASS_SINGLE_SYMBOL_SESSION_AWARE_RESAMPLE_PILOT_NOT_FORMAL',
        'scope': 'SINGLE_SYMBOL_002002_FIXED_SNAPSHOT_ONLY_NOT_FORMAL_847_COVERAGE_NOT_FACTOR_FORMULA',
        'source': {
            'dataset': 'neigezhu/china-a-share-1min-ohlcv',
            'snapshot_commit': snapshot_commit,
            'canonical_path': canonical_path,
            'symbol': symbol,
            'sha256': actual_sha,
            'bytes': input_path.stat().st_size,
            'rows': int(len(source)),
            'trading_dates': trading_dates,
            'timestamp_min': str(source['timestamp'].min()),
            'timestamp_max': str(source['timestamp'].max()),
            'day_row_count_distribution': {str(k): int(v) for k, v in sorted(Counter(day_counts.tolist()).items())},
            'exact_241_rows_each_date': bool((day_counts == 241).all()),
        },
        'session_contract': {
            'opening_marker': '09:30',
            'opening_marker_handling': 'EXCLUDED_FROM_CONTINUOUS_15M_60M_RESAMPLE',
            'am_continuous': '09:31..11:30 inclusive = 120 rows',
            'pm_continuous': '13:01..15:00 inclusive = 120 rows',
            'minutes_per_day_used': 240,
            'lunch_break_crossing_allowed': False,
            'missing_or_duplicate_minute_policy': 'FAIL_CLOSED',
            'bar_label': 'RIGHT_EDGE_CLOSED_MINUTE_TIMESTAMP',
            'interpretation': 'This contract is derived from the observed fixed-snapshot 002002 source shape: 241 rows on every one of 3403 dates, with a 09:30 row and no 13:00 row. It is a pilot resampling contract, not recovered historical GP factor logic.',
        },
        'output_15m': _parquet_identity(out15, bars15),
        'output_60m': _parquet_identity(out60, bars60),
        'boundary_examples': {
            '15m_first': {'source_start': str(first15['source_start']), 'bar_end': str(first15['bar_end'])},
            '15m_last': {'source_start': str(last15['source_start']), 'bar_end': str(last15['bar_end'])},
            '60m_first': {'source_start': str(first60['source_start']), 'bar_end': str(first60['bar_end'])},
            '60m_last': {'source_start': str(last60['source_start']), 'bar_end': str(last60['bar_end'])},
        },
        'single_symbol_minute_bytes_materialized': True,
        'single_symbol_15m_resampling_validated': True,
        'single_symbol_60m_resampling_validated': True,
        'formal_847_15m_coverage_verified': False,
        'formal_847_60m_coverage_verified': False,
        'historical_gp_intraday_resampling_contract_recovered': False,
        'factor_formula_recovered': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }
    evidence_path = out_dir / 'INTRADAY_MINUTE_MATERIALIZATION_PILOT_V482.json'
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description='V4.82 single-symbol intraday minute materialization pilot; never promotes Formal/OOS readiness.')
    parser.add_argument('--input', required=True)
    parser.add_argument('--out-dir', required=True)
    parser.add_argument('--symbol', required=True)
    parser.add_argument('--snapshot-commit', required=True)
    parser.add_argument('--canonical-path', required=True)
    parser.add_argument('--expected-sha256', required=True)
    args = parser.parse_args()
    materialize(Path(args.input), Path(args.out_dir), args.symbol, args.snapshot_commit, args.canonical_path, args.expected_sha256)


if __name__ == '__main__':
    main()
