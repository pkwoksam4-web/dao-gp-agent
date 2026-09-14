from __future__ import annotations

import argparse
import copy
import json
import pathlib

import gp12_formal_input_readiness_v1 as base

ARTIFACT = 'GP12_FORMAL_INPUT_READINESS_INTRADAY_V482'
VERSION = 'V4.82'
UPSTREAM_ARTIFACT = 'GP12_FORMAL_INPUT_READINESS_V1'
BINDING_ARTIFACT = 'GP12_INTRADAY_FORMAL847_BINDING_V1'
BINDING_SHA256 = 'd65a7dac16525f360a4fc93b104c49e8ba279f7eae7c7ac0ba9fba834fc99573'
FORMAL_START = '2020-06-01'
FORMAL_END = '2026-04-17'


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_binding(binding: dict) -> str:
    _require(isinstance(binding, dict), 'intraday binding must be an object')
    binding_sha = base.canonical_json_sha256(binding)
    _require(binding_sha == BINDING_SHA256, 'INTRADAY_BINDING_IDENTITY_MISMATCH')
    _require(binding.get('artifact') == BINDING_ARTIFACT, 'intraday binding artifact mismatch')
    _require(binding.get('version') == '1.0', 'intraday binding version mismatch')
    _require(binding.get('formal_start') == FORMAL_START, 'intraday formal start mismatch')
    _require(binding.get('formal_end') == FORMAL_END, 'intraday formal end mismatch')

    primary = binding.get('primary_source') or {}
    _require(primary.get('dataset') == 'neigezhu/china-a-share-1min-ohlcv', 'intraday dataset mismatch')
    _require(primary.get('snapshot_commit') == 'f311a5f11569e9d541386982d15f2214d9970b8a', 'intraday snapshot mismatch')
    _require(primary.get('formal_symbols') == 847, 'intraday universe count mismatch')
    _require(primary.get('required_trade_dates') == 1_011_607, 'required trade-date count mismatch')
    _require(primary.get('primary_valid_trade_dates') == 1_011_606, 'primary valid trade-date count mismatch')
    _require(primary.get('primary_missing_trade_dates') == 1, 'primary missing trade-date count mismatch')
    _require(primary.get('unique_gap') == '000638.SZ/2026-04-13', 'intraday gap identity mismatch')

    fallback = binding.get('exact_fallback') or {}
    _require(fallback.get('provider') == 'BaoStock', 'fallback provider mismatch')
    _require(fallback.get('symbol') == '000638.SZ', 'fallback symbol mismatch')
    _require(fallback.get('date') == '2026-04-13', 'fallback date mismatch')
    _require(fallback.get('query_code') == 'sz.000638', 'fallback query mismatch')
    _require(str(fallback.get('adjustflag')) == '3', 'fallback adjustflag mismatch')
    _require(fallback.get('run_id') == 34452654219, 'fallback run mismatch')
    _require(fallback.get('artifact_id') == 10142164418, 'fallback artifact mismatch')
    _require(fallback.get('artifact_zip_sha256') == 'eaf42fa65436c874e252fc7426612f40b46597f6be2c1738fb2bfc3fbb823e60', 'fallback ZIP hash mismatch')
    _require(fallback.get('bars_15m_count') == 16, '15m fallback count mismatch')
    _require(fallback.get('bars_60m_count') == 4, '60m fallback count mismatch')
    _require(fallback.get('bars_15m_canonical_sha256') == 'f4aaa1728793a02b3e8804789ec0cee1ca1c1e15d7bdda1a22247ac295e6420c', '15m fallback hash mismatch')
    _require(fallback.get('bars_60m_canonical_sha256') == 'f6ef9280856e0946d1970ea13f680fff14139a258a6aaf9b811fb2da0a4cc6d7', '60m fallback hash mismatch')

    coverage = binding.get('coverage') or {}
    _require(coverage.get('formal_847_15m_coverage_verified') is True, '15m coverage not verified')
    _require(coverage.get('formal_847_60m_coverage_verified') is True, '60m coverage not verified')
    _require(coverage.get('formal_847_minute_byte_coverage_verified') is False, 'minute-byte coverage must remain false')
    _require(coverage.get('historical_gp_intraday_resampling_contract_recovered') is False, 'historical resampling must remain unrecovered')
    _require(coverage.get('factor_formula_recovered') is False, 'factor formula must remain unrecovered')

    safety = binding.get('safety') or {}
    _require(safety.get('candidate_adoption_status') == 'UNAPPROVED', 'candidate adoption state mismatch')
    _require(safety.get('model_freeze_allowed') is False, 'binding cannot open model freeze')
    _require(safety.get('oos_metrics_allowed') is False, 'binding cannot open OOS metrics')
    return binding_sha


def build_intraday_checkpoint(parameters: dict, factors: dict, upstream_evidence: dict, binding: dict) -> dict:
    upstream_validation = base.validate_production_evidence_manifest(upstream_evidence)
    _require(upstream_validation['production_manifest_valid'], 'upstream V1 readiness manifest invalid')
    binding_sha = validate_binding(binding)

    derived = copy.deepcopy(upstream_evidence)
    for family in ('intraday_15m', 'intraday_60m'):
        derived['feature_families'][family] = {
            'binding_state': 'BOUND_VERIFIED_ARTIFACT',
            'pit_state': 'PIT_VERIFIED',
            'source_artifact': BINDING_ARTIFACT,
            'source_sha256': binding_sha,
            'coverage_start': FORMAL_START,
            'coverage_end': FORMAL_END,
            'blockers': [],
        }

    report = base.build_readiness_report(parameters, factors, derived)
    coverage = binding['coverage']
    return {
        **report,
        'artifact': ARTIFACT,
        'version': VERSION,
        'upstream_artifact': UPSTREAM_ARTIFACT,
        'upstream_evidence_artifact': upstream_evidence['artifact'],
        'intraday_binding_artifact': BINDING_ARTIFACT,
        'intraday_binding_sha256': binding_sha,
        'formal_847_minute_byte_coverage_verified': coverage['formal_847_minute_byte_coverage_verified'],
        'historical_gp_intraday_resampling_contract_recovered': coverage['historical_gp_intraday_resampling_contract_recovered'],
        'factor_formula_recovered': coverage['factor_formula_recovered'],
    }


def _load(path: str) -> dict:
    value = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError(f'JSON object required: {path}')
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--parameters', required=True)
    parser.add_argument('--factors', required=True)
    parser.add_argument('--upstream-evidence', required=True)
    parser.add_argument('--intraday-binding', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()

    report = build_intraday_checkpoint(
        _load(args.parameters),
        _load(args.factors),
        _load(args.upstream_evidence),
        _load(args.intraday_binding),
    )
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({
        'artifact': report['artifact'],
        'validated_families': report['validated_families'],
        'ready_factor_ids': report['ready_factor_ids'],
        'blocked_factor_ids': report['blocked_factor_ids'],
        'blockers': report['blockers'],
        'candidate_scoring_ready': report['candidate_scoring_ready'],
        'model_freeze_allowed': report['model_freeze_allowed'],
        'oos_metrics_allowed': report['oos_metrics_allowed'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
