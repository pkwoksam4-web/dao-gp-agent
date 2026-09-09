from __future__ import annotations

import copy

import gp12_turnover_formal_v1 as turnover_mod


FORMAL_START = '2020-06-01'
FORMAL_END = '2026-04-17'


def _turnover_is_promotable(summary: dict) -> bool:
    if not isinstance(summary, dict):
        return False
    try:
        turnover_mod.validate_production_summary(summary)
    except ValueError:
        return False
    required = {
        'artifact': 'GP12_TURNOVER_FORMAL_V1',
        'version': '1.0',
        'strategy_id': 'GP12_REBUILD_CANDIDATE_V1',
        'formal_start': FORMAL_START,
        'formal_end': FORMAL_END,
        'pit_state': 'PIT_VERIFIED',
        'status': 'PASS_FORMAL_TURNOVER_V1',
        'formal_feature_ready': True,
        'candidate_freeze_ready': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }
    for key, expected in required.items():
        if summary.get(key) != expected:
            return False
    if summary.get('blockers') != []:
        return False
    if summary.get('materialized_trade_rows') != summary.get('expected_trade_rows'):
        return False
    zero_fields = (
        'duplicate_row_n',
        'missing_turnover_row_n',
        'extra_turnover_row_n',
        'nonpositive_volume_n',
        'nonpositive_outstanding_share_n',
        'nonfinite_turnover_n',
        'future_share_record_violation_n',
        'unresolved_prior_share_record_n',
    )
    if any(summary.get(field) != 0 for field in zero_fields):
        return False
    for hash_field in ('share_manifest_sha256', 'turnover_rows_sha256'):
        value = summary.get(hash_field)
        if not isinstance(value, str) or len(value) != 64:
            return False
    return True


def bind_turnover(parent_evidence: dict, turnover_summary: dict) -> dict:
    if not isinstance(parent_evidence, dict):
        raise ValueError('parent evidence must be an object')
    result = copy.deepcopy(parent_evidence)
    if not _turnover_is_promotable(turnover_summary):
        return result

    families = result.get('feature_families')
    if not isinstance(families, dict) or 'amount_turnover' not in families:
        raise ValueError('parent evidence feature-family schema mismatch')

    families['amount_turnover'] = {
        'binding_state': 'BOUND_VERIFIED_ARTIFACT',
        'pit_state': 'PIT_VERIFIED',
        'source_artifact': 'GP12_TURNOVER_FORMAL_V1',
        'source_sha256': turnover_mod.canonical_json_sha256(turnover_summary),
        'coverage_start': FORMAL_START,
        'coverage_end': FORMAL_END,
        'blockers': [],
    }
    return result
