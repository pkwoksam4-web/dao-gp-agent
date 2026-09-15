from __future__ import annotations

import argparse
import copy
import json
import pathlib

import gp12_formal_input_readiness_v1 as base
import gp12_intraday_readiness_integration_v482 as intraday

ARTIFACT = 'GP12_FORMAL_INPUT_READINESS_INTRADAY_PIT_V482'
VERSION = 'V4.82'
UPSTREAM_ARTIFACT = 'GP12_FORMAL_INPUT_READINESS_INTRADAY_V482'
PIT_BINDING_ARTIFACT = 'GP12_PIT_ADJUSTED_CLOSE_BINDING_V1'
PIT_BINDING_SHA256 = 'c06d22448f43ffcb47568cce60db0c3da18aa14c7b022a35997cdfdc3f5b66c0'
FORMAL_START = '2020-06-01'
FORMAL_END = '2026-04-17'


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_pit_binding(binding: dict) -> str:
    _require(isinstance(binding, dict), 'PIT adjusted-close binding must be an object')
    binding_sha = base.canonical_json_sha256(binding)
    _require(binding_sha == PIT_BINDING_SHA256, 'PIT_ADJUSTED_CLOSE_BINDING_IDENTITY_MISMATCH')
    _require(binding.get('artifact') == PIT_BINDING_ARTIFACT, 'PIT binding artifact mismatch')
    _require(binding.get('version') == '1.0', 'PIT binding version mismatch')
    _require(binding.get('formal_start') == FORMAL_START, 'PIT formal start mismatch')
    _require(binding.get('formal_end') == FORMAL_END, 'PIT formal end mismatch')

    audit = binding.get('source_audit') or {}
    _require(audit.get('workflow_run') == 34928104668, 'PIT audit run mismatch')
    _require(audit.get('workflow_head') == '30a826f2e4e1dc4350b3e89453e66848a8d5141f', 'PIT audit head mismatch')
    _require(audit.get('artifact_name') == 'gp12-pit-adjusted-close-full-audit-v482', 'PIT audit artifact mismatch')
    _require(audit.get('artifact_id') == 10380675799, 'PIT audit artifact id mismatch')
    _require(audit.get('artifact_zip_sha256') == 'fb57bce61a9156fa3d2bb327dc1d8dba70c6fa9739eb7d87bfb5a3e88c6e9b3f', 'PIT audit ZIP digest mismatch')
    _require(audit.get('audit_json_sha256') == '2d75ace7461d4e7879e49a1678bb0d51f0acc3ca3abdc380c068876c1c569c6e', 'PIT audit JSON digest mismatch')
    _require(audit.get('universe_n') == 847, 'PIT universe count mismatch')
    _require(audit.get('formal_symbol_n') == 844, 'PIT formal-symbol count mismatch')
    _require(audit.get('na_symbols') == ['600074.SH','600485.SH','600677.SH'], 'PIT N/A partition mismatch')
    _require(audit.get('raw_trade_rows') == 1_011_607, 'PIT RAW trade-row count mismatch')
    _require(audit.get('nominal_event_n') == 2732, 'PIT nominal-event count mismatch')
    _require(audit.get('standard_override_n') == 270, 'PIT standard-override count mismatch')
    _require(audit.get('special_override_n') == 11, 'PIT special-override count mismatch')
    _require(audit.get('total_override_n') == 281, 'PIT total-override count mismatch')
    _require(audit.get('special_prev_close_pass_n') == 11, 'PIT special previous-close coverage mismatch')
    _require(audit.get('constant_scale_pass_n') == 844, 'PIT constant-scale pass count mismatch')
    _require(audit.get('constant_scale_fail_n') == 0, 'PIT constant-scale failures remain')
    _require(float(audit.get('threshold_bp')) == 5.0, 'PIT threshold mismatch')
    max_bp = float(audit.get('max_constant_scale_diff_bp'))
    _require(max_bp <= 5.0, 'PIT constant-scale deviation exceeds threshold')
    _require(audit.get('adjusted_close_pit_verified') is True, 'PIT adjusted close not verified')

    runs = binding.get('source_runs') or {}
    expected_runs = {
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
    _require(runs == expected_runs, 'PIT source-run identity mismatch')

    coverage = binding.get('coverage') or {}
    _require(coverage.get('stock_adjusted_close_pit_verified') is True, 'stock adjusted close PIT coverage not verified')
    _require(coverage.get('f6_f10_scale_invariance_verified') is True, 'F6-F10 scale invariance not verified')
    _require(coverage.get('candidate_scale_invariance_test') == 'test_gp12_candidate_v1.ScoringTests.test_price_and_currency_scale_do_not_change_factors', 'scale-invariance test identity mismatch')

    safety = binding.get('safety') or {}
    _require(safety.get('candidate_adoption_status') == 'UNAPPROVED', 'candidate adoption state mismatch')
    _require(safety.get('candidate_scoring_ready') is False, 'PIT binding cannot open candidate scoring')
    _require(safety.get('model_freeze_allowed') is False, 'PIT binding cannot open model freeze')
    _require(safety.get('oos_metrics_allowed') is False, 'PIT binding cannot open OOS metrics')
    return binding_sha


def build_pit_checkpoint(parameters: dict, factors: dict, upstream_evidence: dict, intraday_binding: dict, pit_binding: dict) -> dict:
    upstream_validation = base.validate_production_evidence_manifest(upstream_evidence)
    _require(upstream_validation['production_manifest_valid'], 'upstream V1 readiness manifest invalid')
    intraday_sha = intraday.validate_binding(intraday_binding)
    pit_sha = validate_pit_binding(pit_binding)

    derived = copy.deepcopy(upstream_evidence)
    for family in ('intraday_15m', 'intraday_60m'):
        derived['feature_families'][family] = {
            'binding_state': 'BOUND_VERIFIED_ARTIFACT',
            'pit_state': 'PIT_VERIFIED',
            'source_artifact': intraday.BINDING_ARTIFACT,
            'source_sha256': intraday_sha,
            'coverage_start': FORMAL_START,
            'coverage_end': FORMAL_END,
            'blockers': [],
        }
    derived['feature_families']['stock_adjusted_close'] = {
        'binding_state': 'BOUND_VERIFIED_ARTIFACT',
        'pit_state': 'PIT_VERIFIED',
        'source_artifact': PIT_BINDING_ARTIFACT,
        'source_sha256': pit_sha,
        'coverage_start': FORMAL_START,
        'coverage_end': FORMAL_END,
        'blockers': [],
    }

    report = base.build_readiness_report(parameters, factors, derived)
    audit = pit_binding['source_audit']
    return {
        **report,
        'artifact': ARTIFACT,
        'version': VERSION,
        'upstream_artifact': UPSTREAM_ARTIFACT,
        'upstream_evidence_artifact': upstream_evidence['artifact'],
        'intraday_binding_artifact': intraday.BINDING_ARTIFACT,
        'intraday_binding_sha256': intraday_sha,
        'pit_binding_artifact': PIT_BINDING_ARTIFACT,
        'pit_binding_sha256': pit_sha,
        'pit_audit_workflow_run': audit['workflow_run'],
        'pit_audit_artifact_id': audit['artifact_id'],
        'pit_audit_json_sha256': audit['audit_json_sha256'],
        'pit_constant_scale_pass_n': audit['constant_scale_pass_n'],
        'pit_max_constant_scale_diff_bp': audit['max_constant_scale_diff_bp'],
        'adjusted_close_pit_verified': audit['adjusted_close_pit_verified'],
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
    parser.add_argument('--pit-binding', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()

    report = build_pit_checkpoint(
        _load(args.parameters),
        _load(args.factors),
        _load(args.upstream_evidence),
        _load(args.intraday_binding),
        _load(args.pit_binding),
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
