from __future__ import annotations

import hashlib
import json
import re
from typing import Any


VERSION = 'V4.82'
STRATEGY_ID = 'GP_V11'
SOURCE_ARTIFACT = 'STRATEGY_ASSET_RECOVERY_CHECKPOINT_V482'
OUTPUT_ARTIFACT = 'STRATEGY_RECOVERY_DEPENDENCY_V482'
WAITING_STATUS = 'WAITING_FOR_AUTHORITATIVE_STRATEGY_ASSETS_V482'
SOURCE_STATUS = 'STRATEGY_ASSETS_INCOMPLETE_V482'

EXPECTED_BLOCKERS = [
    'FACTOR_DEFINITION_MISSING',
    'PARAMETER_SET_MISSING',
    'STRATEGY_CODE_MISSING',
]
EXPECTED_MISSING_FIELDS = [
    'strategy_code_bytes',
    'exact_factor_formulas',
    'exact_normalization_and_clipping',
    'authoritative_weight_vector',
    'score_layer_aggregation',
    'probability_mapping',
    'ranking_topn_semantics',
    'entry_exit_thresholds',
    'holding_and_rebalance_policy',
    'position_sizing_and_risk_rules',
]
FORBIDDEN_METRIC_KEYS = {
    'return',
    'returns',
    'pnl',
    'alpha',
    'sharpe',
    'drawdown',
    'hit_rate',
    'win_rate',
    'performance',
    'metrics',
}
ALLOWED_SURFACE_CONFIDENCE = {
    'AUTHORITATIVE_FILE',
    'USER_CONFIRMED',
    'CONVERSATION_CANDIDATE_UNCONFIRMED',
    'ABSENT',
    'UNINSPECTABLE',
}
SHA256_RE = re.compile(r'^[0-9a-f]{64}$')


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')


def canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _contains_forbidden_metric_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_METRIC_KEYS:
                return True
            if _contains_forbidden_metric_key(child):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_metric_key(child) for child in value)
    return False


def _validate_surfaces(value: Any) -> list[dict]:
    if not isinstance(value, list):
        raise ValueError('searched_surfaces must be a list')
    seen = set()
    out = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError('searched_surfaces item must be an object')
        if not {'surface', 'confidence', 'finding'}.issubset(item):
            raise ValueError('searched_surfaces item schema invalid')
        surface = item.get('surface')
        confidence = item.get('confidence')
        finding = item.get('finding')
        if not isinstance(surface, str) or not surface:
            raise ValueError('searched_surfaces surface invalid')
        if surface in seen:
            raise ValueError('searched_surfaces contains duplicate surface')
        seen.add(surface)
        if confidence not in ALLOWED_SURFACE_CONFIDENCE:
            raise ValueError('searched_surfaces confidence invalid')
        if not isinstance(finding, str) or not finding:
            raise ValueError('searched_surfaces finding invalid')
        out.append(item)
    return out


def validate_strategy_recovery_checkpoint(checkpoint: dict) -> None:
    if not isinstance(checkpoint, dict):
        raise ValueError('strategy recovery checkpoint must be an object')
    if _contains_forbidden_metric_key(checkpoint):
        raise ValueError('forbidden OOS metric field in strategy recovery checkpoint')
    if checkpoint.get('artifact') != SOURCE_ARTIFACT:
        raise ValueError('strategy recovery checkpoint artifact mismatch')
    if checkpoint.get('version') != VERSION:
        raise ValueError('strategy recovery checkpoint version mismatch')
    if checkpoint.get('strategy_id') != STRATEGY_ID:
        raise ValueError('strategy recovery checkpoint strategy_id mismatch')
    if checkpoint.get('status') != SOURCE_STATUS:
        raise ValueError('strategy recovery checkpoint status mismatch')

    if checkpoint.get('strategy_code_recovered') is not False:
        raise ValueError('strategy code unexpectedly recovered')
    if checkpoint.get('parameter_set_recovered') is not False:
        raise ValueError('parameter set unexpectedly recovered')
    if checkpoint.get('factor_definition_recovered') is not False:
        raise ValueError('factor definition unexpectedly recovered')
    if checkpoint.get('model_freeze_allowed') is not False:
        raise ValueError('upstream model freeze unexpectedly open')
    if checkpoint.get('oos_metrics_allowed') is not False:
        raise ValueError('upstream OOS metrics unexpectedly open')

    blockers = checkpoint.get('blockers')
    if blockers != EXPECTED_BLOCKERS:
        raise ValueError('strategy recovery blockers must remain exact and ordered')

    missing = checkpoint.get('missing_required_fields')
    if missing != EXPECTED_MISSING_FIELDS:
        raise ValueError('strategy recovery missing field contract mismatch')

    evidence_sha = checkpoint.get('evidence_sha256')
    if not isinstance(evidence_sha, str) or not SHA256_RE.fullmatch(evidence_sha):
        raise ValueError('strategy recovery evidence_sha256 invalid')

    if not isinstance(checkpoint.get('strategy_assets'), dict):
        raise ValueError('strategy_assets must be an object')
    if not isinstance(checkpoint.get('confirmed_rules'), list):
        raise ValueError('confirmed_rules must be a list')
    if not isinstance(checkpoint.get('candidate_clues'), list):
        raise ValueError('candidate_clues must be a list')
    for clue in checkpoint['candidate_clues']:
        if not isinstance(clue, dict):
            raise ValueError('candidate clue must be an object')
        if clue.get('freeze_eligible') is not False:
            raise ValueError('candidate clue unexpectedly freeze eligible')

    _validate_surfaces(checkpoint.get('searched_surfaces'))


def _required_authoritative_inputs() -> list[dict]:
    return [
        {
            'satisfies_blocker': 'STRATEGY_CODE_MISSING',
            'input': 'authoritative_strategy_code_bytes',
            'requirements': [
                'original or provenance-equivalent GP V1.1 scorer source bytes',
                'stable source identity',
                'byte SHA256',
                'provenance linking the source to the frozen strategy',
            ],
            'requires_sha256': True,
            'requires_provenance': True,
            'complete_package_required': False,
        },
        {
            'satisfies_blocker': 'PARAMETER_SET_MISSING',
            'input': 'authoritative_parameter_package',
            'requirements': [
                'complete frozen parameter package',
                'authoritative weight vector',
                'score aggregation and probability mapping',
                'ranking, entry/exit, holding/rebalance and sizing/risk rules',
                'canonical SHA256 and provenance',
            ],
            'requires_sha256': True,
            'requires_provenance': True,
            'complete_package_required': True,
        },
        {
            'satisfies_blocker': 'FACTOR_DEFINITION_MISSING',
            'input': 'authoritative_factor_definition_package',
            'requirements': [
                'complete exact factor formulas',
                'normalization and clipping rules',
                'lookback/input semantics and frozen definitions',
                'canonical SHA256 and provenance',
            ],
            'requires_sha256': True,
            'requires_provenance': True,
            'complete_package_required': True,
        },
    ]


def build_strategy_recovery_dependency(recovery_checkpoint: dict) -> dict:
    validate_strategy_recovery_checkpoint(recovery_checkpoint)

    surfaces = recovery_checkpoint['searched_surfaces']
    exhausted_surfaces = [
        item['surface'] for item in surfaces if item['confidence'] == 'ABSENT'
    ]
    uninspectable_surfaces = [
        item['surface'] for item in surfaces if item['confidence'] == 'UNINSPECTABLE'
    ]

    reopen_conditions = [
        'AUTHORITATIVE_STRATEGY_CODE_BECOMES_AVAILABLE',
        'AUTHORITATIVE_PARAMETER_PACKAGE_BECOMES_AVAILABLE',
        'AUTHORITATIVE_FACTOR_DEFINITION_PACKAGE_BECOMES_AVAILABLE',
    ]
    if uninspectable_surfaces:
        reopen_conditions.append('UNINSPECTABLE_CARRIER_BECOMES_INSPECTABLE')

    return {
        'artifact': OUTPUT_ARTIFACT,
        'version': VERSION,
        'strategy_id': STRATEGY_ID,
        'status': WAITING_STATUS,
        'strategy_recovery_checkpoint_sha256': canonical_json_sha256(recovery_checkpoint),
        'strategy_recovery_evidence_sha256': recovery_checkpoint['evidence_sha256'],
        'remaining_blockers': EXPECTED_BLOCKERS[:],
        'missing_required_fields': EXPECTED_MISSING_FIELDS[:],
        'required_authoritative_inputs': _required_authoritative_inputs(),
        'exhausted_surfaces': exhausted_surfaces,
        'uninspectable_surfaces': uninspectable_surfaces,
        'reopen_conditions': reopen_conditions,
        'repeat_equivalent_exhausted_searches_allowed': False,
        'conversation_candidate_clues_can_satisfy_blockers': False,
        'auxiliary_components_can_satisfy_strategy_code': False,
        'dependency_satisfied': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }
