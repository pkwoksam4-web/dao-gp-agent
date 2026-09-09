from __future__ import annotations

import argparse
import json
import math
import pathlib
import re

import formal_readiness_v482 as base
from audit_evidence_v1 import validate_sha256

EXPECTED_SPECIAL_N = 11
EXPECTED_ZERO_TRADE_SYMBOLS = ['600074.SH','600485.SH','600677.SH']


def _key(row: dict) -> tuple[str, str]:
    symbol = str(row.get('symbol') or '').upper()
    ex_date = str(row.get('ex_date') or '')[:10]
    if not symbol or len(ex_date) != 10:
        raise ValueError('special row missing symbol/ex_date')
    return symbol, ex_date


def _sha_ok(value) -> bool:
    return bool(re.fullmatch(r'[0-9a-fA-F]{64}', str(value or '')))


def enrich_special_rows(special_rows: list[dict], provenance_report: dict, expected_n: int = EXPECTED_SPECIAL_N) -> list[dict]:
    n = int(expected_n)
    if len(special_rows or []) != n:
        raise ValueError(f'expected {n} special closure rows; got {len(special_rows or [])}')
    if int(provenance_report.get('target_n') or 0) != n:
        raise ValueError('special provenance target partition mismatch')
    if int(provenance_report.get('materialized_n') or 0) != n or int(provenance_report.get('unresolved_n') or 0) != 0:
        raise ValueError('special provenance is not fully materialized')
    by = {}
    for row in provenance_report.get('records') or []:
        key = _key(row)
        if key in by:
            raise ValueError(f'duplicate special provenance row: {key}')
        by[key] = row
    if len(by) != n:
        raise ValueError(f'expected {n} special provenance records; got {len(by)}')
    out = []
    seen = set()
    for raw in special_rows:
        row = dict(raw)
        key = _key(row)
        if key in seen:
            raise ValueError(f'duplicate special closure row: {key}')
        seen.add(key)
        item = by.get(key)
        if item is None or item.get('status') != 'PASS_CNINFO_MATERIALIZED':
            raise ValueError(f'{key}: missing materialized provenance')
        a = float(row.get('adjusted_reference_price'))
        b = float(item.get('adjusted_reference_price'))
        if not math.isfinite(a) or not math.isfinite(b) or abs(a - b) > 1e-6:
            raise ValueError(f'{key}: adjusted reference price mismatch')
        prov = item.get('provenance') or {}
        if prov.get('source') != 'CNINFO_OFFICIAL_PDF':
            raise ValueError(f'{key}: provenance source is not CNINFO_OFFICIAL_PDF')
        aid = str(prov.get('announcement_id') or '').strip()
        sha = str(prov.get('materialized_sha256') or '').lower()
        if not aid or not _sha_ok(sha):
            raise ValueError(f'{key}: missing announcement id/materialized SHA')
        row['announcement_id'] = aid
        row['materialized_sha256'] = sha
        row['materialized_source'] = 'CNINFO_OFFICIAL_PDF'
        row['materialized_title'] = prov.get('announcement_title')
        out.append(row)
    return sorted(out, key=_key)


def validate_market_data_readiness(raw: dict, liquidity: dict) -> dict:
    raw_checks = {
        'artifact': raw.get('artifact') == 'SOHU_RAW_FULL_V482',
        'version': raw.get('version') == 'V4.82',
        'status': raw.get('status') == 'PASS_FULL_RAW_V482',
        'symbol_n': int(raw.get('symbol_n') or 0) == 847,
        'raw_rows': int(raw.get('raw_rows') or 0) == 1_011_607,
        'expected_trade_rows': int(raw.get('expected_trade_rows') or 0) == 1_011_607,
        'duplicates': int(raw.get('duplicate_symbol_dates') or 0) == 0,
        'missing': int(raw.get('missing_trade_dates_n') or 0) == 0,
        'extra': int(raw.get('extra_trade_dates_n') or 0) == 0,
        'bad_ohlc': int(raw.get('bad_ohlc_rows') or 0) == 0,
        'bad_volume': int(raw.get('bad_volume_rows') or 0) == 0,
        'bad_amount': int(raw.get('bad_amount_rows') or 0) == 0,
        'shard_error': int(raw.get('shard_error_n') or 0) == 0,
        'global_reaudit': raw.get('global_reaudit_pass') is True,
        'zero_trade_symbols': raw.get('zero_trade_symbols') == EXPECTED_ZERO_TRADE_SYMBOLS,
        'full_parquet_sha256': validate_sha256(raw.get('full_parquet_sha256')),
        'full_parquet_bytes': int(raw.get('full_parquet_bytes') or 0) > 0,
        'schema_fingerprint': validate_sha256(raw.get('schema_fingerprint')),
        'source_formal_closed': raw.get('formal_admission') is False,
        'source_oos_closed': raw.get('oos_metrics_allowed') is False,
    }
    failed_raw = [k for k,v in raw_checks.items() if not v]
    if failed_raw:
        raise ValueError(f'Full RAW market-data gate failed: {failed_raw}')

    pit = liquidity.get('raw_pitst_audit') or {}
    liq_checks = {
        'artifact': liquidity.get('artifact') == 'LIQUIDITY_80M_APPLY_V482',
        'version': liquidity.get('version') == 'V4.82',
        'threshold': int(liquidity.get('threshold_cny') or 0) == 80_000_000,
        'symbol_n': int(liquidity.get('symbol_n') or 0) == 847,
        'calendar_days': int(liquidity.get('calendar_days') or 0) == 1426,
        'panel_rows': int(liquidity.get('panel_rows') or 0) == 1_207_822,
        'pitst_source_rows': int(liquidity.get('pitst_source_rows') or 0) == 1_022_100,
        'pitst_observed_rows': int(liquidity.get('pitst_observed_rows') or 0) == 1_022_100,
        'lifecycle_padding_rows': int(liquidity.get('lifecycle_padding_rows') or 0) == 185_722,
        'corrected_trade_rows': int(liquidity.get('corrected_trade_rows') or 0) == 1_011_607,
        'raw_trade_rows': int(liquidity.get('raw_trade_rows') or 0) == 1_011_607,
        'raw_pitst_status': pit.get('status') == 'PASS_EXACT_RAW_PITST',
        'raw_pitst_expected': int(pit.get('expected_trade_rows') or 0) == 1_011_607,
        'raw_pitst_rows': int(pit.get('raw_trade_rows') or 0) == 1_011_607,
        'raw_pitst_duplicates': int(pit.get('duplicate_raw_symbol_dates') or 0) == 0,
        'raw_pitst_missing': int(pit.get('missing_trade_dates_n') or 0) == 0,
        'raw_pitst_extra': int(pit.get('extra_trade_dates_n') or 0) == 0,
        'raw_pitst_bad_amount': int(pit.get('bad_amount_rows') or 0) == 0,
        'raw_pitst_bad_volume': int(pit.get('bad_volume_rows') or 0) == 0,
        'current_trade_violation': int(liquidity.get('current_trade_violation_n') or 0) == 0,
        'st_overlay_violation': int(liquidity.get('st_overlay_violation_n') or 0) == 0,
        'input_full_raw_sha256': validate_sha256(liquidity.get('input_full_raw_sha256')),
        'input_pitst_sha256': validate_sha256(liquidity.get('input_pitst_sha256')),
        'panel_parquet_sha256': validate_sha256(liquidity.get('panel_parquet_sha256')),
        'panel_parquet_bytes': int(liquidity.get('panel_parquet_bytes') or 0) > 0,
        'schema_fingerprint': validate_sha256(liquidity.get('schema_fingerprint')),
        'source_formal_closed': liquidity.get('formal_admission') is False,
        'source_oos_closed': liquidity.get('oos_metrics_allowed') is False,
    }
    failed_liq = [k for k,v in liq_checks.items() if not v]
    if failed_liq:
        raise ValueError(f'Frozen liquidity market-data gate failed: {failed_liq}')

    if liquidity['input_full_raw_sha256'] != raw['full_parquet_sha256']:
        raise ValueError('Frozen liquidity input RAW hash does not match Full RAW parquet hash')

    byte_bindings = {
        'full_raw_sha256': raw['full_parquet_sha256'],
        'liquidity_panel_sha256': liquidity['panel_parquet_sha256'],
        'pitst_sha256': liquidity['input_pitst_sha256'],
    }
    return {
        'market_data_ready': True,
        'full_raw_status': raw['status'],
        'symbol_n': 847,
        'raw_trade_rows': int(raw['raw_rows']),
        'missing_trade_dates_n': 0,
        'extra_trade_dates_n': 0,
        'duplicate_symbol_dates': 0,
        'zero_trade_symbols': list(EXPECTED_ZERO_TRADE_SYMBOLS),
        'liquidity_threshold_cny': 80_000_000,
        'calendar_days': 1426,
        'panel_rows': int(liquidity['panel_rows']),
        'pitst_source_rows': int(liquidity['pitst_source_rows']),
        'lifecycle_padding_rows': int(liquidity['lifecycle_padding_rows']),
        'liquidity_pre_st_true_rows': int(liquidity.get('liquidity_pre_st_true_rows') or 0),
        'eligible_non_st_true_rows': int(liquidity.get('eligible_non_st_true_rows') or 0),
        'latest_date': liquidity.get('latest_date'),
        'latest_liquidity_pre_st_n': int(liquidity.get('latest_liquidity_pre_st_n') or 0),
        'latest_eligible_non_st_n': int(liquidity.get('latest_eligible_non_st_n') or 0),
        'raw_pitst_status': pit['status'],
        'current_trade_violation_n': 0,
        'st_overlay_violation_n': 0,
        'byte_bindings': byte_bindings,
    }


def _load(root: pathlib.Path, name: str) -> dict:
    p = base._find_unique(root, name)
    return json.loads(p.read_text(encoding='utf-8'))


def finalize(frozen_dir: pathlib.Path, special_dir: pathlib.Path, special_provenance_dir: pathlib.Path,
             effective_dir: pathlib.Path, secondary_dir: pathlib.Path, reparsed_dir: pathlib.Path,
             reparsed_evidence_dir: pathlib.Path, recovered_dir: pathlib.Path, final_six_dir: pathlib.Path,
             final_four_dir: pathlib.Path, source_census_dir: pathlib.Path, raw_dir: pathlib.Path,
             liquidity_dir: pathlib.Path) -> dict:
    audit = base.audit(
        frozen_dir, special_dir, effective_dir, secondary_dir, reparsed_dir,
        reparsed_evidence_dir, recovered_dir, final_six_dir, final_four_dir, source_census_dir,
    )
    if audit.get('checkpoint') != base.FINAL_CHECKPOINT:
        raise ValueError('final checkpoint mismatch')
    if audit.get('full_path_pass_n') != 844 or audit.get('full_path_fail_n') != 0:
        raise ValueError('fresh 844-path audit is not fully closed')
    if float(audit.get('max_full_path_diff_bp')) > base.THRESHOLD_BP:
        raise ValueError('fresh full-path audit exceeds 5bp')
    if audit.get('standard_override_n') != 270 or audit.get('standard_provenance_ok') is not True:
        raise ValueError('standard provenance is not closed')
    if (audit.get('na') or {}).get('count') != 3:
        raise ValueError('N/A partition is not exact three')

    special = _load(special_dir, 'SPECIAL_EXRIGHT_CLOSURE_V482.json')
    provenance = _load(special_provenance_dir, 'SPECIAL_EXRIGHT_PROVENANCE_V482.json')
    enriched = enrich_special_rows(special.get('records') or [], provenance)
    special_prov = base.classify_special_provenance(enriched)
    if special_prov.get('blocker_n') != 0 or special_prov.get('materialized_n') != 11:
        raise ValueError('special provenance remains open')

    raw = _load(raw_dir, 'SOHU_RAW_FULL_AUDIT_V482.json')
    liquidity = _load(liquidity_dir, 'LIQUIDITY_80M_APPLY_AUDIT_V482.json')
    market_data = validate_market_data_readiness(raw, liquidity)

    gate = base.decide_gate(
        math_closed=True,
        standard_provenance_ok=True,
        na_ok=True,
        special_provenance=special_prov,
    )
    if gate.get('status') != 'FORMAL_READY_V482' or gate.get('formal_ready') is not True:
        raise ValueError('Formal gate did not close')
    gate = dict(gate)
    gate['market_data_ready'] = True
    return {
        'artifact': 'FORMAL_READINESS_FINAL_V482',
        'version': 'V4.82',
        'checkpoint': audit['checkpoint'],
        'universe_n': 847,
        'formal_symbol_n': 844,
        'full_path_pass_n': audit['full_path_pass_n'],
        'full_path_fail_n': audit['full_path_fail_n'],
        'max_full_path_diff_bp': audit['max_full_path_diff_bp'],
        'standard_override_n': audit['standard_override_n'],
        'special_override_n': audit['special_override_n'],
        'total_override_n': audit['total_override_n'],
        'na': audit['na'],
        'special_provenance': special_prov,
        'special_materialized_rows': enriched,
        'market_data': market_data,
        'byte_bindings': dict(market_data['byte_bindings']),
        'gate': gate,
        'formal_ready': True,
        'validated_global_provenance_emitted': True,
        'oos_metrics_allowed': False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    names = ('frozen-dir','special-dir','special-provenance-dir','effective-dir','secondary-dir','reparsed-dir',
             'reparsed-evidence-dir','recovered-dir','final-six-dir','final-four-dir','source-census-dir',
             'raw-dir','liquidity-dir','out-dir')
    for name in names:
        ap.add_argument('--' + name, required=True)
    a = ap.parse_args()
    x = finalize(
        pathlib.Path(a.frozen_dir), pathlib.Path(a.special_dir), pathlib.Path(a.special_provenance_dir),
        pathlib.Path(a.effective_dir), pathlib.Path(a.secondary_dir), pathlib.Path(a.reparsed_dir),
        pathlib.Path(a.reparsed_evidence_dir), pathlib.Path(a.recovered_dir), pathlib.Path(a.final_six_dir),
        pathlib.Path(a.final_four_dir), pathlib.Path(a.source_census_dir), pathlib.Path(a.raw_dir),
        pathlib.Path(a.liquidity_dir),
    )
    out = pathlib.Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    (out / 'FORMAL_READINESS_FINAL_V482.json').write_text(json.dumps(x, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'checkpoint': x['checkpoint'], 'full_path_pass_n': x['full_path_pass_n'],
        'max_full_path_diff_bp': x['max_full_path_diff_bp'], 'standard_override_n': x['standard_override_n'],
        'special_materialized_n': x['special_provenance']['materialized_n'],
        'market_data': x['market_data'], 'gate': x['gate'],
        'oos_metrics_allowed': x['oos_metrics_allowed'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
