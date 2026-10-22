from __future__ import annotations

import argparse
import copy
import json
import pathlib

import gp12_formal_input_readiness_v1 as base
import gp12_intraday_readiness_integration_v482 as intraday
import gp12_pit_readiness_integration_v482 as pit

ARTIFACT = 'GP12_FORMAL_INPUT_READINESS_INTRADAY_PIT_TURNOVER_V482'
VERSION = 'V4.82'
UPSTREAM_ARTIFACT = 'GP12_FORMAL_INPUT_READINESS_INTRADAY_PIT_V482'
TURNOVER_BINDING_ARTIFACT = 'GP12_AMOUNT_TURNOVER_BINDING_V1'
TURNOVER_BINDING_SHA256 = '14e5f80915305ad5a6293f5cec3606b3d637a30720b0b9f355ffe1baf21fc96f'
FORMAL_START = '2020-06-01'
FORMAL_END = '2026-04-17'


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_turnover_binding(binding: dict) -> str:
    _require(isinstance(binding, dict), 'amount-turnover binding must be an object')
    binding_sha = base.canonical_json_sha256(binding)
    _require(binding_sha == TURNOVER_BINDING_SHA256, 'TURNOVER_BINDING_IDENTITY_MISMATCH')
    _require(binding.get('artifact') == TURNOVER_BINDING_ARTIFACT, 'turnover binding artifact mismatch')
    _require(binding.get('version') == '1.0', 'turnover binding version mismatch')
    _require(binding.get('formal_start') == FORMAL_START, 'turnover formal start mismatch')
    _require(binding.get('formal_end') == FORMAL_END, 'turnover formal end mismatch')

    amount = binding.get('amount_source') or {}
    _require(amount.get('raw_daily_artifact') == base.RAW_ARTIFACT_NAME, 'amount RAW artifact mismatch')
    _require(amount.get('raw_daily_sha256') == base.RAW_ARTIFACT_SHA256, 'amount RAW identity mismatch')
    _require(amount.get('liquidity_artifact') == base.LIQUIDITY_ARTIFACT_NAME, 'amount liquidity artifact mismatch')
    _require(amount.get('liquidity_sha256') == base.LIQUIDITY_ARTIFACT_SHA256, 'amount liquidity identity mismatch')
    _require(amount.get('trade_rows') == 1_011_607, 'amount trade-row count mismatch')
    _require(amount.get('bad_amount_rows') == 0, 'bad amount rows remain')
    _require(amount.get('raw_pitst_exact_date_verified') is True, 'amount/PIT-ST exact-date coverage not verified')
    _require(amount.get('amount_cny_formal_verified') is True, 'amount CNY Formal source not verified')

    audit = binding.get('turnover_source_audit') or {}
    _require(audit.get('workflow_run') == 34937058721, 'turnover audit run mismatch')
    _require(audit.get('workflow_head') == 'c8a3db077d3dc73e188937e9c355bc0bfa863382', 'turnover audit head mismatch')
    _require(audit.get('artifact_name') == 'gp12-baostock-turnover-full-v482', 'turnover audit artifact mismatch')
    _require(audit.get('artifact_id') == 10383758045, 'turnover audit artifact id mismatch')
    _require(audit.get('artifact_zip_sha256') == '53e574b91d72359e2dc073fdb1796f1945c46222902cf85beb9089b2a712e55a', 'turnover artifact ZIP digest mismatch')
    _require(audit.get('audit_json_sha256') == '9709dd46516f7ba8b3d6914c3a1866649bb23ffc041214ac932477553afa8c0f', 'turnover audit JSON digest mismatch')
    _require(audit.get('parquet_sha256') == '13c86aa5ee0920f00e8bd3c031a275640b3f75a82c7e28c380245b43a9bf84e6', 'turnover parquet digest mismatch')
    _require(audit.get('provider') == 'BaoStock query_history_k_data_plus', 'turnover provider mismatch')
    _require(audit.get('provider_version') == '0.9.3', 'turnover provider version mismatch')
    _require(audit.get('provider_field') == 'turn', 'turnover provider field mismatch')
    _require(audit.get('provider_turn_unit') == 'percent', 'turnover provider unit mismatch')
    _require(audit.get('normalized_unit') == 'ratio', 'turnover normalized unit mismatch')
    _require(audit.get('source_semantics_verified') is True, 'turnover source semantics not verified')
    _require(audit.get('scope_n') == 847, 'turnover scope count mismatch')
    _require(audit.get('turnover_symbol_n') == 844, 'turnover symbol count mismatch')
    _require(audit.get('turnover_rows') == 1_011_607, 'turnover row count mismatch')
    _require(audit.get('missing_n') == 0, 'turnover missing rows remain')
    _require(audit.get('extra_n') == 0, 'turnover extra rows remain')
    _require(audit.get('duplicate_n') == 0, 'turnover duplicate rows remain')
    _require(audit.get('bad_turnover_n') == 0, 'bad turnover rows remain')
    _require(audit.get('unresolved_symbol_n') == 0, 'turnover unresolved symbols remain')
    _require(audit.get('zero_trade_symbols') == ['600074.SH','600485.SH','600677.SH'], 'turnover zero-trade partition mismatch')
    _require(audit.get('applied_trade_status_corrections') == [
        ['002087.SZ','2024-06-13'],
        ['300356.SZ','2023-06-20'],
        ['600647.SH','2024-06-13'],
        ['600766.SH','2024-06-13'],
        ['603133.SH','2024-06-13'],
    ], 'turnover trade-status correction set mismatch')
    _require(float(audit.get('cross_source_sohu_anchor_tolerance_bp')) == 0.5, 'turnover cross-source tolerance mismatch')
    _require(audit.get('cross_source_sohu_anchor_n') == 2, 'turnover cross-source anchor count mismatch')
    _require(audit.get('cross_source_sohu_matched_n') == 2, 'turnover cross-source matched count mismatch')
    _require(audit.get('cross_source_sohu_fail_n') == 0, 'turnover cross-source failures remain')
    _require(float(audit.get('cross_source_sohu_max_diff_bp')) <= 0.5, 'turnover cross-source deviation exceeds threshold')
    _require(audit.get('coverage_verified') is True, 'turnover coverage not verified')
    _require(audit.get('turnover_ratio_pit_verified') is True, 'turnover ratio PIT not verified')

    coverage = binding.get('coverage') or {}
    _require(coverage.get('amount_turnover_pit_verified') is True, 'amount-turnover PIT coverage not verified')
    _require(coverage.get('universe_n') == 847, 'amount-turnover universe mismatch')
    _require(coverage.get('formal_symbol_n') == 844, 'amount-turnover formal-symbol mismatch')
    _require(coverage.get('trade_rows') == 1_011_607, 'amount-turnover trade-row mismatch')
    _require(coverage.get('na_symbols') == ['600074.SH','600485.SH','600677.SH'], 'amount-turnover N/A partition mismatch')

    safety = binding.get('safety') or {}
    _require(safety.get('candidate_adoption_status') == 'UNAPPROVED', 'candidate adoption state mismatch')
    _require(safety.get('candidate_scoring_ready') is False, 'turnover binding cannot open candidate scoring')
    _require(safety.get('model_freeze_allowed') is False, 'turnover binding cannot open model freeze')
    _require(safety.get('oos_metrics_allowed') is False, 'turnover binding cannot open OOS metrics')
    return binding_sha


def build_turnover_checkpoint(
    parameters: dict,
    factors: dict,
    upstream_evidence: dict,
    intraday_binding: dict,
    pit_binding: dict,
    turnover_binding: dict,
) -> dict:
    upstream_validation = base.validate_production_evidence_manifest(upstream_evidence)
    _require(upstream_validation['production_manifest_valid'], 'upstream V1 readiness manifest invalid')
    intraday_sha = intraday.validate_binding(intraday_binding)
    pit_sha = pit.validate_pit_binding(pit_binding)
    turnover_sha = validate_turnover_binding(turnover_binding)

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
        'source_artifact': pit.PIT_BINDING_ARTIFACT,
        'source_sha256': pit_sha,
        'coverage_start': FORMAL_START,
        'coverage_end': FORMAL_END,
        'blockers': [],
    }
    derived['feature_families']['amount_turnover'] = {
        'binding_state': 'BOUND_VERIFIED_ARTIFACT',
        'pit_state': 'PIT_VERIFIED',
        'source_artifact': TURNOVER_BINDING_ARTIFACT,
        'source_sha256': turnover_sha,
        'coverage_start': FORMAL_START,
        'coverage_end': FORMAL_END,
        'blockers': [],
    }

    report = base.build_readiness_report(parameters, factors, derived)
    audit = turnover_binding['turnover_source_audit']
    return {
        **report,
        'artifact': ARTIFACT,
        'version': VERSION,
        'upstream_artifact': UPSTREAM_ARTIFACT,
        'upstream_evidence_artifact': upstream_evidence['artifact'],
        'intraday_binding_artifact': intraday.BINDING_ARTIFACT,
        'intraday_binding_sha256': intraday_sha,
        'pit_binding_artifact': pit.PIT_BINDING_ARTIFACT,
        'pit_binding_sha256': pit_sha,
        'turnover_binding_artifact': TURNOVER_BINDING_ARTIFACT,
        'turnover_binding_sha256': turnover_sha,
        'turnover_audit_workflow_run': audit['workflow_run'],
        'turnover_audit_artifact_id': audit['artifact_id'],
        'turnover_audit_json_sha256': audit['audit_json_sha256'],
        'turnover_ratio_pit_verified': audit['turnover_ratio_pit_verified'],
        'turnover_cross_source_max_diff_bp': audit['cross_source_sohu_max_diff_bp'],
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
    parser.add_argument('--turnover-binding', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()

    report = build_turnover_checkpoint(
        _load(args.parameters),
        _load(args.factors),
        _load(args.upstream_evidence),
        _load(args.intraday_binding),
        _load(args.pit_binding),
        _load(args.turnover_binding),
    )
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({
        'artifact': report['artifact'],
        'validated_families': report['validated_families'],
        'ready_factor_ids': report['ready_factor_ids'],
        'blocked_factor_ids': report['blocked_factor_ids'],
        'f11_missing_dependencies': report['factor_readiness']['F11']['missing_dependencies'],
        'blockers': report['blockers'],
        'candidate_scoring_ready': report['candidate_scoring_ready'],
        'model_freeze_allowed': report['model_freeze_allowed'],
        'oos_metrics_allowed': report['oos_metrics_allowed'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
