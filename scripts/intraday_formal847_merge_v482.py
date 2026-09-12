from __future__ import annotations

import argparse
import json
from pathlib import Path


ARTIFACT = 'INTRADAY_FORMAL847_MATERIALIZATION_SHARD_V482'
VERSION = 'V4.82'
FORMAL_START = '2020-06-01'
FORMAL_END = '2026-04-17'
DATASET = 'neigezhu/china-a-share-1min-ohlcv'
SNAPSHOT_COMMIT = 'f311a5f11569e9d541386982d15f2214d9970b8a'


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def aggregate_reports(reports: list[dict], *, expected_shards: int = 17, expected_symbols: int = 847) -> dict:
    _require(expected_shards > 0, 'expected_shards must be positive')
    _require(expected_symbols > 0, 'expected_symbols must be positive')
    _require(len(reports) == expected_shards, f'expected {expected_shards} shard reports; got {len(reports)}')

    by_index = {}
    all_symbols: list[str] = []
    total_required = 0
    total_valid = 0
    total_missing = 0
    total_invalid = 0
    total_source_bytes = 0
    total_15m_rows = 0
    total_60m_rows = 0
    total_pass_symbols = 0
    total_zero_symbols = 0

    for report in reports:
        _require(report.get('artifact') == ARTIFACT, 'wrong shard artifact')
        _require(report.get('version') == VERSION, 'wrong shard version')
        _require(report.get('formal_start') == FORMAL_START, 'wrong Formal start')
        _require(report.get('formal_end') == FORMAL_END, 'wrong Formal end')
        _require(report.get('dataset') == DATASET, 'wrong dataset')
        _require(report.get('snapshot_commit') == SNAPSHOT_COMMIT, 'wrong fixed snapshot')
        _require(int(report.get('shard_count', -1)) == expected_shards, 'wrong shard_count')

        idx = int(report.get('shard_index', -1))
        _require(0 <= idx < expected_shards, f'invalid shard_index {idx}')
        _require(idx not in by_index, f'duplicate shard_index {idx}')
        by_index[idx] = report

        symbols = [str(x) for x in report.get('symbol_list', [])]
        _require(int(report.get('symbols_selected', -1)) == len(symbols), f'shard {idx} symbols_selected mismatch')
        all_symbols.extend(symbols)

        required = int(report.get('required_trade_dates', -1))
        valid = int(report.get('valid_trade_dates', -1))
        missing = int(report.get('missing_trade_dates', -1))
        invalid = int(report.get('invalid_grid_dates', -1))
        review = int(report.get('review_symbols', -1))
        pass_symbols = int(report.get('pass_symbols', -1))
        zero_symbols = int(report.get('expected_zero_trade_symbols', -1))
        source_bytes = int(report.get('source_bytes_downloaded', -1))
        rows15 = int(report.get('bars_15m', {}).get('rows', -1))
        rows60 = int(report.get('bars_60m', {}).get('rows', -1))

        _require(report.get('status') == 'PASS_SHARD_REQUIRED_DATE_COVERAGE', f'shard {idx} is not PASS')
        _require(report.get('shard_required_date_coverage_verified') is True, f'shard {idx} coverage flag is not true')
        _require(review == 0, f'shard {idx} has review symbols')
        _require(missing == 0, f'shard {idx} has missing required trade dates')
        _require(invalid == 0, f'shard {idx} has invalid minute grids')
        _require(required == valid, f'shard {idx} required/valid trade dates mismatch')
        _require(pass_symbols + zero_symbols == len(symbols), f'shard {idx} symbol accounting mismatch')
        _require(rows15 == valid * 16, f'shard {idx} 15m row count mismatch')
        _require(rows60 == valid * 4, f'shard {idx} 60m row count mismatch')
        _require(source_bytes >= 0, f'shard {idx} source byte count invalid')
        if required > 0:
            _require(source_bytes > 0, f'shard {idx} has required dates but no source bytes')

        # Shards themselves must never self-promote to global coverage or strategy/model gates.
        _require(report.get('formal_847_minute_byte_coverage_verified') is False, f'shard {idx} illegally self-promoted byte coverage')
        _require(report.get('formal_847_15m_coverage_verified') is False, f'shard {idx} illegally self-promoted 15m coverage')
        _require(report.get('formal_847_60m_coverage_verified') is False, f'shard {idx} illegally self-promoted 60m coverage')
        _require(report.get('historical_gp_intraday_resampling_contract_recovered') is False, f'shard {idx} illegally promoted historical contract')
        _require(report.get('factor_formula_recovered') is False, f'shard {idx} illegally promoted factor formula')
        _require(report.get('model_freeze_allowed') is False, f'shard {idx} illegally promoted model freeze')
        _require(report.get('oos_metrics_allowed') is False, f'shard {idx} illegally promoted OOS')

        total_required += required
        total_valid += valid
        total_missing += missing
        total_invalid += invalid
        total_source_bytes += source_bytes
        total_15m_rows += rows15
        total_60m_rows += rows60
        total_pass_symbols += pass_symbols
        total_zero_symbols += zero_symbols

    _require(sorted(by_index) == list(range(expected_shards)), 'shard partition is incomplete')
    _require(len(all_symbols) == expected_symbols, f'expected {expected_symbols} symbol assignments; got {len(all_symbols)}')
    _require(len(set(all_symbols)) == expected_symbols, 'duplicate or missing symbols across shards')
    _require(total_pass_symbols + total_zero_symbols == expected_symbols, 'global symbol accounting mismatch')
    _require(total_required == total_valid, 'global required/valid trade date mismatch')
    _require(total_missing == 0 and total_invalid == 0, 'global missing/invalid dates remain')
    _require(total_15m_rows == total_valid * 16, 'global 15m row count mismatch')
    _require(total_60m_rows == total_valid * 4, 'global 60m row count mismatch')

    return {
        'artifact': 'INTRADAY_FORMAL847_COVERAGE_AUDIT_V482',
        'version': VERSION,
        'status': 'PASS_FORMAL847_INTRADAY_COVERAGE',
        'scope': 'FORMAL_WINDOW_REQUIRED_TRADE_DATES_FIXED_SNAPSHOT_DATA_COVERAGE_ONLY_NOT_HISTORICAL_GP_FACTOR_AUTHORITY',
        'formal_start': FORMAL_START,
        'formal_end': FORMAL_END,
        'dataset': DATASET,
        'snapshot_commit': SNAPSHOT_COMMIT,
        'shards': expected_shards,
        'symbols': expected_symbols,
        'pass_symbols': total_pass_symbols,
        'expected_zero_trade_symbols': total_zero_symbols,
        'required_trade_dates': total_required,
        'valid_trade_dates': total_valid,
        'missing_trade_dates': total_missing,
        'invalid_grid_dates': total_invalid,
        'source_bytes_downloaded': total_source_bytes,
        'bars_15m_rows': total_15m_rows,
        'bars_60m_rows': total_60m_rows,
        'formal_847_minute_byte_coverage_verified': True,
        'formal_847_15m_coverage_verified': True,
        'formal_847_60m_coverage_verified': True,
        'historical_gp_intraday_resampling_contract_recovered': False,
        'factor_formula_recovered': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
        'shard_indices': sorted(by_index),
        'symbol_list': sorted(all_symbols),
    }


def load_reports(root: Path) -> list[dict]:
    paths = sorted(root.rglob('INTRADAY_FORMAL847_SHARD_*_AUDIT_V482.json'))
    if not paths:
        raise FileNotFoundError('no Formal847 shard audit reports found')
    return [json.loads(path.read_text(encoding='utf-8')) for path in paths]


def main() -> None:
    parser = argparse.ArgumentParser(description='Aggregate fail-closed Formal847 intraday shard coverage.')
    parser.add_argument('--reports-dir', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--expected-shards', type=int, default=17)
    parser.add_argument('--expected-symbols', type=int, default=847)
    args = parser.parse_args()

    reports = load_reports(Path(args.reports_dir))
    result = aggregate_reports(reports, expected_shards=args.expected_shards, expected_symbols=args.expected_symbols)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
