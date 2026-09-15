from __future__ import annotations

import argparse
import json
import pathlib

from gp12_pit_full_audit_v482 import audit_universe
from sample50_validate import parse_sina_qfq

NA_SYMBOLS = ['600074.SH', '600485.SH', '600677.SH']
EXPECTED_UNIVERSE_N = 847
EXPECTED_FORMAL_N = 844
EXPECTED_RAW_ROWS = 1_011_607


def find_unique(root: pathlib.Path, name: str) -> pathlib.Path:
    hits = [p for p in root.rglob(name) if p.is_file()]
    if len(hits) != 1:
        raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def load_json(root: pathlib.Path, name: str) -> dict:
    return json.loads(find_unique(root, name).read_text(encoding='utf-8'))


def load_factors(source_census_dir: pathlib.Path, symbols: list[str]) -> dict[str, list[dict]]:
    out = {}
    for symbol in symbols:
        code, exchange = symbol.split('.')
        path = find_unique(source_census_dir, f'{code}_{exchange}_sina_qfq.js')
        rows = parse_sina_qfq(path.read_bytes())
        out[symbol] = [{'d': row['date'], 'f': row['factor']} for row in rows]
    return out


def load_raw(raw_dir: pathlib.Path):
    import pandas as pd

    path = find_unique(raw_dir, 'SOHU_RAW_FULL_V482.parquet')
    frame = pd.read_parquet(path, columns=['symbol', 'date', 'close'])
    frame['symbol'] = frame['symbol'].astype(str).str.upper()
    frame['date'] = frame['date'].astype(str).str[:10]
    if len(frame) != EXPECTED_RAW_ROWS:
        raise ValueError(f'expected {EXPECTED_RAW_ROWS} RAW rows; got {len(frame)}')
    if frame.duplicated(['symbol', 'date']).any():
        raise ValueError('duplicate RAW symbol/date rows')
    symbols = sorted(frame['symbol'].unique().tolist())
    expected_formal_symbols = EXPECTED_UNIVERSE_N - len(NA_SYMBOLS)
    if len(symbols) != expected_formal_symbols:
        raise ValueError(f'expected {expected_formal_symbols} RAW symbols; got {len(symbols)}')
    out = {}
    for symbol, group in frame.groupby('symbol', sort=True):
        rows = group.sort_values('date')[['date', 'close']].to_dict('records')
        out[str(symbol).upper()] = rows
    return out, len(frame)


def run(args) -> dict:
    manifest = json.loads(pathlib.Path(args.manifest).read_text(encoding='utf-8'))
    if len(manifest.get('nominal_events') or []) != 2732:
        raise ValueError('nominal event manifest count mismatch')
    if len(manifest.get('standard_overrides') or []) != 270:
        raise ValueError('standard override manifest count mismatch')
    if len(manifest.get('special_overrides') or []) != 11:
        raise ValueError('special override manifest count mismatch')

    frozen = load_json(pathlib.Path(args.frozen_dir), 'GLOBAL_QFQ_MISSING_EVENT_CLOSURE_V481.json')
    records = frozen.get('records') or []
    if len(records) != EXPECTED_UNIVERSE_N:
        raise ValueError(f'expected {EXPECTED_UNIVERSE_N} frozen records; got {len(records)}')

    effective = load_json(pathlib.Path(args.effective_dir), 'EFFECTIVE_TERM_CLOSURE_V482.json')
    secondary = load_json(pathlib.Path(args.secondary_dir), 'REMAINING_EXACT_CLOSURE_V482.json')
    reparsed = load_json(pathlib.Path(args.reparsed_dir), 'REPARSED_REMAINING_CLOSURE_V482.json')
    recovered = load_json(pathlib.Path(args.recovered_dir), 'RECOVERED_REMAINING_CLOSURE_V482.json')
    final_six = load_json(pathlib.Path(args.final_six_dir), 'FINAL_SIX_CLOSURE_V482.json')
    final_four = load_json(pathlib.Path(args.final_four_dir), 'FINAL_FOUR_CLOSURE_V482.json')
    standard_stages = [
        effective.get('event_overrides') or [],
        secondary.get('accepted_overrides') or [],
        reparsed.get('new_overrides') or [],
        recovered.get('accepted_overrides') or [],
        final_six.get('accepted_overrides') or [],
        final_four.get('accepted_overrides') or [],
    ]
    if sum(len(stage) for stage in standard_stages) != 270:
        raise ValueError('standard closure stage count mismatch')

    raw_by_symbol, raw_rows = load_raw(pathlib.Path(args.raw_dir))
    formal_symbols = sorted(set(str(r.get('symbol') or '').upper() for r in records) - set(NA_SYMBOLS))
    if len(formal_symbols) != EXPECTED_FORMAL_N:
        raise ValueError(f'expected {EXPECTED_FORMAL_N} formal symbols; got {len(formal_symbols)}')
    if sorted(raw_by_symbol) != formal_symbols:
        raise ValueError('RAW symbol partition does not match frozen formal partition')
    factors_by_symbol = load_factors(pathlib.Path(args.source_census_dir), formal_symbols)

    result = audit_universe(
        raw_by_symbol=raw_by_symbol,
        factors_by_symbol=factors_by_symbol,
        frozen_records=records,
        standard_stages=standard_stages,
        special_rows=manifest['special_overrides'],
        manifest=manifest,
        na_symbols=NA_SYMBOLS,
        expected_standard_n=270,
        expected_special_n=11,
        threshold_bp=float(args.threshold_bp),
    )
    result['raw_trade_rows'] = raw_rows
    result['source_runs'] = {
        'frozen_closure': 34078398130,
        'source_census': 34009079533,
        'full_raw': 34192233633,
        'effective': 34102907115,
        'secondary': 34106853526,
        'reparsed': 34109448536,
        'recovered': 34111100684,
        'final_six': 34116386540,
        'final_four': 34117443729,
    }
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'GP12_PIT_ADJUSTED_CLOSE_FULL_AUDIT_V482.json'
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'artifact': result['artifact'],
        'universe_n': result['universe_n'],
        'formal_symbol_n': result['formal_symbol_n'],
        'raw_trade_rows': result['raw_trade_rows'],
        'constant_scale_pass_n': result['constant_scale_pass_n'],
        'constant_scale_fail_n': result['constant_scale_fail_n'],
        'max_constant_scale_diff_bp': result['max_constant_scale_diff_bp'],
        'special_prev_close_pass_n': result['special_prev_close_pass_n'],
        'adjusted_close_pit_verified': result['adjusted_close_pit_verified'],
        'oos_metrics_allowed': result['oos_metrics_allowed'],
    }, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--frozen-dir', required=True)
    parser.add_argument('--effective-dir', required=True)
    parser.add_argument('--secondary-dir', required=True)
    parser.add_argument('--reparsed-dir', required=True)
    parser.add_argument('--recovered-dir', required=True)
    parser.add_argument('--final-six-dir', required=True)
    parser.add_argument('--final-four-dir', required=True)
    parser.add_argument('--source-census-dir', required=True)
    parser.add_argument('--raw-dir', required=True)
    parser.add_argument('--out-dir', required=True)
    parser.add_argument('--threshold-bp', type=float, default=5.0)
    run(parser.parse_args())


if __name__ == '__main__':
    main()
