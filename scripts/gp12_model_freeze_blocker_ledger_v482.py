from __future__ import annotations


HISTORICAL_CONTRACT_BLOCKERS = [
    'COMPLETE_12_FACTOR_STRATEGY_CODE_BYTES_MISSING',
    'EXACT_NON_DAILY_FACTOR_FORMULAS_NORMALIZATION_AGGREGATION_MISSING',
    'FULL_GP12_THREE_WAY_PROBABILITY_MAPPING_MISSING',
    'RANKING_TOPN_SEMANTICS_MISSING',
    'ENTRY_EXIT_THRESHOLDS_MISSING',
    'HOLDING_REBALANCE_POLICY_MISSING',
    'POSITION_SIZING_AND_RISK_RULES_MISSING',
    'ACTUAL_FILL_PRICE_AND_INTRADAY_EXECUTION_RULES_MISSING',
]

SECTOR_FUND_BLOCKER = 'PIT_SECTOR_AND_FUND_FLOW_INPUT_PROVENANCE_INCOMPLETE'
INTRADAY_BLOCKER = 'FORMAL847_INTRADAY_BYTE_COVERAGE_AND_HISTORICAL_RESAMPLING_MISSING'
MIXED_BLOCKERS = [SECTOR_FUND_BLOCKER, INTRADAY_BLOCKER]
CANONICAL_BLOCKERS = HISTORICAL_CONTRACT_BLOCKERS + MIXED_BLOCKERS

EXPECTED_INTRADAY_SEMANTIC_SHA256 = '355502946ab0f769dc43313f7757984e2bac9297cb241df378b875c9de20e39b'
EXPECTED_INTRADAY_SOURCE_FILES_HASH_BOUND = 844
EXPECTED_INTRADAY_SOURCE_BYTES_HASH_BOUND = 8048396274
EXPECTED_FUND_FLOW_SHA256 = '034f6578d1475856c8a74285167e6f167bbb7052d25a1c691d804a9c2bbe6eea'
EXPECTED_FUND_FLOW_SIZE_BYTES = 2134704074
EXPECTED_FUND_FLOW_ROWS = 4934625
EXPECTED_FUND_FLOW_SYMBOLS = 5148
EXPECTED_FUND_FLOW_COVERAGE = ['2021-01-04','2025-04-23']


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


def _require_fail_closed(name: str, evidence: dict) -> None:
    _require(evidence.get('model_freeze_allowed') is False, f'{name} inputs are not fail-closed')
    _require(evidence.get('oos_metrics_allowed') is False, f'{name} inputs are not fail-closed')


def _validate_checkpoint(checkpoint: dict) -> None:
    _require(checkpoint.get('artifact') == 'GP12_MODEL_FREEZE_PROVENANCE_CHECKPOINT_V482', 'checkpoint identity mismatch')
    _require(checkpoint.get('version') == 'V4.82' and checkpoint.get('strategy_id') == 'GP_V11', 'checkpoint identity mismatch')
    _require(checkpoint.get('status') == 'BLOCKED_MODEL_FREEZE_PROVENANCE', 'checkpoint status mismatch')
    _require(checkpoint.get('formal_feature_ready') is True and checkpoint.get('oos_calendar_ready') is True, 'checkpoint prerequisite mismatch')
    _require(checkpoint.get('strategy_provenance_complete') is False, 'checkpoint provenance unexpectedly complete')
    _require(checkpoint.get('candidate_substitution_allowed') is False, 'checkpoint candidate substitution unexpectedly allowed')
    _require_fail_closed('checkpoint', checkpoint)
    remaining = checkpoint.get('remaining_blockers') or []
    _require(len(remaining) == 10 and set(remaining) == set(CANONICAL_BLOCKERS), 'canonical blocker set mismatch')


def _validate_triage(triage: dict) -> None:
    _require(triage.get('artifact') == 'GP12_MODEL_FREEZE_RECOVERY_TRIAGE_V482', 'triage identity mismatch')
    _require(triage.get('version') == 'V4.82' and triage.get('strategy_id') == 'GP_V11', 'triage identity mismatch')
    _require(triage.get('status') == 'RECOVERY_TRIAGED_MODEL_FREEZE_BLOCKED', 'triage status mismatch')
    _require(set(triage.get('historical_contract_blockers') or []) == set(HISTORICAL_CONTRACT_BLOCKERS), 'triage historical blocker mismatch')
    _require(set(triage.get('mixed_data_and_contract_blockers') or []) == set(MIXED_BLOCKERS), 'triage mixed blocker mismatch')
    _require((triage.get('pure_engineering_blockers') or []) == [], 'triage unexpectedly contains pure engineering blockers')
    _require(triage.get('candidate_substitution_allowed') is False, 'triage candidate substitution unexpectedly allowed')
    _require_fail_closed('triage', triage)


def _validate_sector_fund(evidence: dict) -> None:
    ok = (
        evidence.get('artifact') == 'GP12_SECTOR_FUND_SOURCE_PROVENANCE_V482'
        and evidence.get('version') == 'V4.82'
        and evidence.get('strategy_id') == 'GP_V11'
        and evidence.get('status') == 'PARTIAL_SOURCE_PROVENANCE_BOUND'
        and evidence.get('blocker') == SECTOR_FUND_BLOCKER
        and evidence.get('blocker_closed') is False
        and evidence.get('data_completion_would_close_blocker_by_itself') is False
    )
    _require(ok, 'sector/fund partial provenance mismatch')
    sector = evidence.get('sector') or {}
    fund = evidence.get('fund_flow') or {}
    _require(
        sector.get('adapter_path_recovered') is True
        and sector.get('source_snapshot_identity_locked') is False
        and sector.get('pit_membership_verified') is False,
        'sector/fund sector-state mismatch',
    )
    fund_ok = (
        fund.get('candidate_snapshot_identity_locked') is True
        and fund.get('remote_pointer_identity_verified') is True
        and fund.get('actual_snapshot_bytes_verified_in_current_recovery') is True
        and int(fund.get('verified_rows',-1)) == EXPECTED_FUND_FLOW_ROWS
        and int(fund.get('verified_symbols',-1)) == EXPECTED_FUND_FLOW_SYMBOLS
        and list(fund.get('verified_coverage') or []) == EXPECTED_FUND_FLOW_COVERAGE
        and int(fund.get('verified_payload_size_bytes',-1)) == EXPECTED_FUND_FLOW_SIZE_BYTES
        and fund.get('verified_payload_sha256') == EXPECTED_FUND_FLOW_SHA256
        and fund.get('formal_window_coverage_complete') is False
        and fund.get('pit_provenance_complete') is False
    )
    _require(fund_ok, 'sector/fund fund-flow-state mismatch')
    remaining_data = list(evidence.get('remaining_data_gaps') or [])
    _require(bool(remaining_data), 'sector/fund remaining data gaps missing')
    _require('FUND_FLOW_SOURCE_BYTES_NOT_VERIFIED_IN_CURRENT_RECOVERY' not in remaining_data, 'sector/fund stale source-byte gap')
    _require(bool(evidence.get('remaining_contract_gaps')), 'sector/fund remaining contract gaps missing')
    _require_fail_closed('sector/fund', evidence)


def _validate_intraday(evidence: dict) -> None:
    ok = (
        evidence.get('artifact') == 'GP12_INTRADAY_PARTIAL_PROVENANCE_V482'
        and evidence.get('version') == 'V4.82'
        and evidence.get('strategy_id') == 'GP_V11'
        and evidence.get('status') == 'PASS_FORMAL847_15M_60M_COVERAGE_PARTIAL_INTRADAY_PROVENANCE'
        and evidence.get('blocker') == INTRADAY_BLOCKER
        and evidence.get('blocker_closed') is False
        and evidence.get('formal_847_source_files_bytes_hash_bound') is True
        and evidence.get('formal_847_required_minute_date_coverage_complete') is False
        and evidence.get('formal_847_15m_coverage_verified') is True
        and evidence.get('formal_847_60m_coverage_verified') is True
        and evidence.get('formal_847_minute_byte_coverage_verified') is False
        and evidence.get('historical_gp_intraday_resampling_contract_recovered') is False
        and evidence.get('factor_formula_recovered') is False
    )
    _require(ok, 'intraday partial provenance mismatch')
    _require(evidence.get('exact_gap') == {'symbol':'000638.SZ','date':'2026-04-13'}, 'intraday exact gap mismatch')
    primary = evidence.get('primary_snapshot') or {}
    expected = {
        'symbol_n':847,
        'required_trade_dates':1011607,
        'valid_trade_dates':1011606,
        'missing_trade_dates':1,
        'invalid_grid_dates':0,
        'bars_15m_rows':16185696,
        'bars_60m_rows':4046424,
        'shard_evidence_semantic_sha256':EXPECTED_INTRADAY_SEMANTIC_SHA256,
        'source_files_hash_bound':EXPECTED_INTRADAY_SOURCE_FILES_HASH_BOUND,
        'source_bytes_hash_bound':EXPECTED_INTRADAY_SOURCE_BYTES_HASH_BOUND,
    }
    _require(all(primary.get(k) == v for k, v in expected.items()), 'intraday frozen cardinality/hash mismatch')
    _require(_is_sha256(primary.get('source_file_binding_semantic_sha256')), 'intraday source-file binding hash missing')
    _require(len(evidence.get('remaining_subgaps') or []) == 3, 'intraday remaining subgap mismatch')
    _require_fail_closed('intraday', evidence)


def build_model_freeze_blocker_ledger(
    checkpoint: dict,
    recovery_triage: dict,
    sector_fund_partial: dict,
    intraday_partial: dict,
) -> dict:
    _validate_checkpoint(checkpoint)
    _validate_triage(recovery_triage)
    _validate_sector_fund(sector_fund_partial)
    _validate_intraday(intraday_partial)

    blockers = []
    for blocker in HISTORICAL_CONTRACT_BLOCKERS:
        blockers.append({
            'blocker': blocker,
            'category': 'HISTORICAL_STRATEGY_CONTRACT',
            'recovery_state': 'HISTORICAL_CONTRACT_MISSING',
            'blocker_closed': False,
            'evidence': {
                'accessible_archive_recovery_complete': True,
                'candidate_substitution_allowed': False,
            },
        })

    fund = sector_fund_partial['fund_flow']
    blockers.append({
        'blocker': SECTOR_FUND_BLOCKER,
        'category': 'MIXED_DATA_AND_HISTORICAL_CONTRACT',
        'recovery_state': 'PARTIAL_ENGINEERING_RECOVERY',
        'blocker_closed': False,
        'evidence': {
            'sector_adapter_path_recovered': True,
            'sector_source_snapshot_identity_locked': False,
            'sector_pit_membership_verified': False,
            'fund_flow_candidate_snapshot_identity_locked': True,
            'fund_flow_source_bytes_verified': True,
            'fund_flow_verified_rows': fund['verified_rows'],
            'fund_flow_verified_symbols': fund['verified_symbols'],
            'fund_flow_verified_coverage': list(fund['verified_coverage']),
            'fund_flow_verified_payload_size_bytes': fund['verified_payload_size_bytes'],
            'fund_flow_verified_payload_sha256': fund['verified_payload_sha256'],
            'fund_flow_formal_window_coverage_complete': False,
            'fund_flow_pit_provenance_complete': False,
            'remaining_data_gaps': list(sector_fund_partial.get('remaining_data_gaps') or []),
            'remaining_contract_gaps': list(sector_fund_partial.get('remaining_contract_gaps') or []),
        },
    })

    primary = intraday_partial['primary_snapshot']
    blockers.append({
        'blocker': INTRADAY_BLOCKER,
        'category': 'MIXED_DATA_AND_HISTORICAL_CONTRACT',
        'recovery_state': 'PARTIAL_ENGINEERING_RECOVERY',
        'blocker_closed': False,
        'evidence': {
            'formal_847_source_files_bytes_hash_bound': True,
            'source_files_hash_bound': primary['source_files_hash_bound'],
            'source_bytes_hash_bound': primary['source_bytes_hash_bound'],
            'source_file_binding_semantic_sha256': primary['source_file_binding_semantic_sha256'],
            'formal_847_required_minute_date_coverage_complete': False,
            'formal_847_15m_coverage_verified': True,
            'formal_847_60m_coverage_verified': True,
            'formal_847_minute_byte_coverage_verified': False,
            'historical_gp_intraday_resampling_contract_recovered': False,
            'factor_formula_recovered': False,
            'exact_gap': dict(intraday_partial['exact_gap']),
            'required_trade_dates': primary['required_trade_dates'],
            'valid_trade_dates': primary['valid_trade_dates'],
            'missing_trade_dates': primary['missing_trade_dates'],
            'invalid_grid_dates': primary['invalid_grid_dates'],
            'bars_15m_rows': primary['bars_15m_rows'],
            'bars_60m_rows': primary['bars_60m_rows'],
            'shard_evidence_semantic_sha256': primary['shard_evidence_semantic_sha256'],
            'remaining_subgaps': list(intraday_partial.get('remaining_subgaps') or []),
        },
    })

    return {
        'artifact': 'GP12_MODEL_FREEZE_BLOCKER_LEDGER_V482',
        'version': 'V4.82',
        'strategy_id': 'GP_V11',
        'status': 'BLOCKED_MODEL_FREEZE_PROVENANCE_RECOVERY_PARTIAL',
        'summary': {
            'blocker_n': 10,
            'closed_n': 0,
            'partial_recovery_n': 2,
            'historical_contract_missing_n': 8,
        },
        'blockers': blockers,
        'candidate_substitution_allowed': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
        'next_gate': 'SEARCH_EXTERNAL_ORIGINAL_CONTRACT_AND_CONTINUE_ENGINEER_RECOVERABLE_SUBGAPS',
    }
