from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ARTIFACT = 'GP12_INTRADAY_PARTIAL_PROVENANCE_V482'
VERSION = 'V4.82'
STRATEGY_ID = 'GP_V11'
DATASET = 'neigezhu/china-a-share-1min-ohlcv'
SNAPSHOT_COMMIT = 'f311a5f11569e9d541386982d15f2214d9970b8a'
SCALEOUT_RUN_ID = 34446872502
SCALEOUT_HEAD_SHA = 'babff6bc76976d4ce3595b00f689f5f816bb4b70'

TARGET_SYMBOL = '000638.SZ'
TARGET_DATE = '2026-04-13'
ZERO_TRADE_SYMBOLS = {'600074.SH', '600485.SH', '600677.SH'}

EXPECTED = {
    'shard_n': 17,
    'symbol_n': 847,
    'pass_symbol_n': 843,
    'zero_trade_symbol_n': 3,
    'review_symbol_n': 1,
    'required_trade_dates': 1_011_607,
    'valid_trade_dates': 1_011_606,
    'missing_trade_dates': 1,
    'invalid_grid_dates': 0,
    'bars_15m_rows': 16_185_696,
    'bars_60m_rows': 4_046_424,
}

BAOSTOCK = {
    'run_id': 34452654219,
    'artifact_id': 10142164418,
    'artifact_zip_sha256': 'eaf42fa65436c874e252fc7426612f40b46597f6be2c1738fb2bfc3fbb823e60',
    '5': {'count': 48, 'sha256': '6cb7243bf6b535a6dd3ef9991025a1394a2c1913f5ae963c06c63f139e6347db'},
    '15': {'count': 16, 'sha256': 'f4aaa1728793a02b3e8804789ec0cee1ca1c1e15d7bdda1a22247ac295e6420c'},
    '60': {'count': 4, 'sha256': 'f6ef9280856e0946d1970ea13f680fff14139a258a6aaf9b811fb2da0a4cc6d7'},
}

SINA = {
    'run_id': 34444014051,
    'artifact_id': 10138954337,
    'artifact_zip_sha256': 'a42b71995fdc355a920dc062a40c6294db129c2c41f3dbdc29b2d8a80fb5a7eb',
    'target_rows': 238,
    'target_rows_sha256': '72eac61af5dcd6b9d35e890f26f122e30905db1459da1f91d8557857de2faacc',
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
        return True
    except ValueError:
        return False


def _validate_shards(shard_reports: list[dict]) -> tuple[dict, list[dict]]:
    _require(len(shard_reports) == EXPECTED['shard_n'], 'expected exactly 17 shard audits')
    indexes = []
    evidence = []
    review_records = []
    zero_trade_records = []

    totals = {
        'symbol_n': 0,
        'pass_symbol_n': 0,
        'zero_trade_symbol_n': 0,
        'review_symbol_n': 0,
        'required_trade_dates': 0,
        'valid_trade_dates': 0,
        'missing_trade_dates': 0,
        'invalid_grid_dates': 0,
        'bars_15m_rows': 0,
        'bars_60m_rows': 0,
    }

    for report in shard_reports:
        _require(report.get('artifact') == 'INTRADAY_FORMAL847_MATERIALIZATION_SHARD_V482', 'shard artifact mismatch')
        _require(report.get('version') == VERSION, 'shard version mismatch')
        _require(report.get('dataset') == DATASET, 'shard dataset mismatch')
        _require(report.get('snapshot_commit') == SNAPSHOT_COMMIT, 'shard snapshot mismatch')
        _require(int(report.get('shard_count', -1)) == EXPECTED['shard_n'], 'shard-count mismatch')
        idx = int(report.get('shard_index', -1))
        indexes.append(idx)

        b15 = report.get('bars_15m') or {}
        b60 = report.get('bars_60m') or {}
        _require(_is_sha256(b15.get('sha256')), '15m parquet sha256 missing')
        _require(_is_sha256(b60.get('sha256')), '60m parquet sha256 missing')
        valid_days = int(report.get('valid_trade_dates', 0))
        _require(int(b15.get('rows', -1)) == valid_days * 16, '15m rows do not equal valid_days x 16')
        _require(int(b60.get('rows', -1)) == valid_days * 4, '60m rows do not equal valid_days x 4')

        totals['symbol_n'] += int(report.get('symbols_selected', 0))
        totals['pass_symbol_n'] += int(report.get('pass_symbols', 0))
        totals['zero_trade_symbol_n'] += int(report.get('expected_zero_trade_symbols', 0))
        totals['review_symbol_n'] += int(report.get('review_symbols', 0))
        totals['required_trade_dates'] += int(report.get('required_trade_dates', 0))
        totals['valid_trade_dates'] += valid_days
        totals['missing_trade_dates'] += int(report.get('missing_trade_dates', 0))
        totals['invalid_grid_dates'] += int(report.get('invalid_grid_dates', 0))
        totals['bars_15m_rows'] += int(b15['rows'])
        totals['bars_60m_rows'] += int(b60['rows'])

        for record in report.get('records') or []:
            status = record.get('status')
            if status == 'EXPECTED_ZERO_TRADE_NA':
                zero_trade_records.append(record)
            elif status != 'PASS_REQUIRED_TRADE_DATES_EXACT':
                review_records.append(record)

        evidence.append({
            'shard_index': idx,
            'symbols_selected': int(report.get('symbols_selected', 0)),
            'required_trade_dates': int(report.get('required_trade_dates', 0)),
            'valid_trade_dates': valid_days,
            'missing_trade_dates': int(report.get('missing_trade_dates', 0)),
            'invalid_grid_dates': int(report.get('invalid_grid_dates', 0)),
            'bars_15m': {'rows': int(b15['rows']), 'sha256': b15['sha256']},
            'bars_60m': {'rows': int(b60['rows']), 'sha256': b60['sha256']},
        })

    _require(sorted(indexes) == list(range(17)), 'shard indexes are not exactly 0..16')
    for key, expected in EXPECTED.items():
        if key == 'shard_n':
            continue
        _require(totals[key] == expected, f'frozen aggregate mismatch: {key}')

    _require(len(review_records) == 1, 'single gap contract violated')
    review = review_records[0]
    _require(review.get('symbol') == TARGET_SYMBOL, 'single gap symbol mismatch')
    _require(review.get('status') == 'REVIEW_REQUIRED_TRADE_DATES', 'single gap status mismatch')
    _require(review.get('missing_trade_dates') == [TARGET_DATE], 'single gap date mismatch')
    _require((review.get('invalid_grid_dates') or []) == [], 'single gap contains invalid grid')

    zero_symbols = {r.get('symbol') for r in zero_trade_records}
    _require(zero_symbols == ZERO_TRADE_SYMBOLS, 'zero-trade symbol set mismatch')
    _require(len(zero_trade_records) == 3, 'zero-trade record cardinality mismatch')

    evidence.sort(key=lambda x: x['shard_index'])
    semantic = hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return totals, evidence + [{'semantic_sha256': semantic}]


def _validate_baostock(probe: dict) -> None:
    _require(probe.get('artifact') == 'INTRADAY_000638_BAOSTOCK_PROBE_V482', 'BaoStock artifact mismatch')
    _require(probe.get('version') == VERSION, 'BaoStock version mismatch')
    _require(probe.get('symbol') == TARGET_SYMBOL and probe.get('date') == TARGET_DATE, 'BaoStock symbol/date mismatch')
    _require(probe.get('provider') == 'BaoStock' and probe.get('query_code') == 'sz.000638', 'BaoStock provider identity mismatch')
    _require(str(probe.get('adjustflag')) == '3', 'BaoStock adjustflag mismatch')
    _require(probe.get('formal_fill_allowed') is False, 'BaoStock upstream probe unexpectedly promotional')
    _require(probe.get('minute_byte_coverage_verified') is False, 'BaoStock cannot promote minute-byte coverage')
    freqs = probe.get('frequencies') or {}
    for freq in ('5', '15', '60'):
        item = freqs.get(freq) or {}
        _require(str(item.get('error_code')) == '0', f'BaoStock {freq}m query error')
        _require(int(item.get('count', -1)) == BAOSTOCK[freq]['count'], f'BaoStock {freq}m count mismatch')
        _require(item.get('response_canonical_sha256') == BAOSTOCK[freq]['sha256'], f'BaoStock {freq}m canonical hash mismatch')


def _validate_sina(sina: dict) -> None:
    _require(sina.get('artifact') == 'SINA_000638_1M_PROBE_V482', 'Sina artifact mismatch')
    _require(sina.get('version') == VERSION, 'Sina version mismatch')
    _require(sina.get('symbol') == TARGET_SYMBOL and sina.get('target_date') == TARGET_DATE, 'Sina symbol/date mismatch')
    _require(sina.get('target_present') is True, 'Sina target date absent')
    _require(int(sina.get('target_rows', -1)) == SINA['target_rows'], 'Sina target-row count mismatch')
    _require(sina.get('target_rows_sha256') == SINA['target_rows_sha256'], 'Sina target-row hash mismatch')
    _require(sina.get('eligible_as_fallback_source') is False, 'Sina must remain corroboration-only')
    _require(sina.get('formal_847_coverage_promoted') is False, 'Sina must not promote Formal847 coverage')
    _require(sina.get('model_freeze_allowed') is False and sina.get('oos_metrics_allowed') is False, 'Sina evidence is not fail-closed')


def build_intraday_partial_provenance(shard_reports: list[dict], baostock_probe: dict, sina_audit: dict) -> dict:
    totals, shard_evidence_with_hash = _validate_shards(shard_reports)
    _validate_baostock(baostock_probe)
    _validate_sina(sina_audit)
    semantic_sha = shard_evidence_with_hash[-1]['semantic_sha256']
    shard_evidence = shard_evidence_with_hash[:-1]

    return {
        'artifact': ARTIFACT,
        'version': VERSION,
        'strategy_id': STRATEGY_ID,
        'status': 'PASS_FORMAL847_15M_60M_COVERAGE_PARTIAL_INTRADAY_PROVENANCE',
        'scope': 'FORMAL847_AGGREGATE_BAR_COVERAGE_ONLY_NOT_HISTORICAL_GP_FACTOR_AUTHORITY',
        'primary_snapshot': {
            'dataset': DATASET,
            'snapshot_commit': SNAPSHOT_COMMIT,
            'workflow_run_id': SCALEOUT_RUN_ID,
            'workflow_head_sha': SCALEOUT_HEAD_SHA,
            'shard_n': 17,
            **totals,
            'shard_evidence_semantic_sha256': semantic_sha,
            'shards': shard_evidence,
        },
        'exact_gap': {'symbol': TARGET_SYMBOL, 'date': TARGET_DATE},
        'expected_zero_trade_symbols': sorted(ZERO_TRADE_SYMBOLS),
        'aggregate_fallback': {
            'role': 'EXACT_SINGLE_DAY_NATIVE_AGGREGATE_BARS_NOT_MINUTE_RECONSTRUCTION',
            'provider': 'BaoStock',
            'symbol': TARGET_SYMBOL,
            'date': TARGET_DATE,
            'workflow_run_id': BAOSTOCK['run_id'],
            'artifact_id': BAOSTOCK['artifact_id'],
            'artifact_zip_sha256': BAOSTOCK['artifact_zip_sha256'],
            'bars_5m_count': BAOSTOCK['5']['count'],
            'bars_15m_count': BAOSTOCK['15']['count'],
            'bars_60m_count': BAOSTOCK['60']['count'],
            'canonical_sha256': {
                '5m': BAOSTOCK['5']['sha256'],
                '15m': BAOSTOCK['15']['sha256'],
                '60m': BAOSTOCK['60']['sha256'],
            },
            'minute_byte_coverage_verified': False,
        },
        'minute_corroboration': {
            'provider': 'Sina',
            'role': 'CORROBORATION_ONLY_NOT_ADMITTED_AS_FORMAL_MINUTE_FILL',
            'workflow_run_id': SINA['run_id'],
            'artifact_id': SINA['artifact_id'],
            'artifact_zip_sha256': SINA['artifact_zip_sha256'],
            'target_rows': SINA['target_rows'],
            'target_rows_sha256': SINA['target_rows_sha256'],
            'eligible_as_fallback_source': False,
        },
        'formal_847_15m_coverage_verified': True,
        'formal_847_60m_coverage_verified': True,
        'formal_847_minute_byte_coverage_verified': False,
        'historical_gp_intraday_resampling_contract_recovered': False,
        'factor_formula_recovered': False,
        'remaining_subgaps': [
            'FORMAL847_MINUTE_BYTE_COVERAGE_SINGLE_DAY_GAP_000638_SZ_2026_04_13',
            'HISTORICAL_GP_INTRADAY_RESAMPLING_CONTRACT_MISSING',
            'EXACT_INTRADAY_CONFIRMATION_FACTOR_FORMULA_MISSING',
        ],
        'blocker': 'FORMAL847_INTRADAY_BYTE_COVERAGE_AND_HISTORICAL_RESAMPLING_MISSING',
        'blocker_closed': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--shard-dir', required=True)
    ap.add_argument('--baostock', required=True)
    ap.add_argument('--sina', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    shard_paths = sorted(Path(args.shard_dir).rglob('*_AUDIT_V482.json'))
    reports = [_load_json(p) for p in shard_paths]
    result = build_intraday_partial_provenance(reports, _load_json(Path(args.baostock)), _load_json(Path(args.sina)))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({
        'status': result['status'],
        'symbol_n': result['primary_snapshot']['symbol_n'],
        'required_trade_dates': result['primary_snapshot']['required_trade_dates'],
        'valid_trade_dates': result['primary_snapshot']['valid_trade_dates'],
        'exact_gap': result['exact_gap'],
        'formal_847_15m_coverage_verified': result['formal_847_15m_coverage_verified'],
        'formal_847_60m_coverage_verified': result['formal_847_60m_coverage_verified'],
        'formal_847_minute_byte_coverage_verified': result['formal_847_minute_byte_coverage_verified'],
        'model_freeze_allowed': result['model_freeze_allowed'],
        'oos_metrics_allowed': result['oos_metrics_allowed'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
