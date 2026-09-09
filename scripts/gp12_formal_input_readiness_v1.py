from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from typing import Any


STRATEGY_ID = 'GP12_REBUILD_CANDIDATE_V1'
ARTIFACT = 'GP12_FORMAL_INPUT_READINESS_V1'
VERSION = '1.0'
FORMAL_END = '2026-04-17'
PARAMETERS_SHA256 = '22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204'
FACTORS_SHA256 = 'b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e'

FEATURE_FAMILIES = (
    'market_calendar',
    'stock_adjusted_close',
    'market_adjusted_close',
    'sector_adjusted_close',
    'amount_turnover',
    'main_net_flow',
    'market_breadth',
    'sector_breadth',
    'status',
    'intraday_15m',
    'intraday_60m',
)
SUPPORTING_EVIDENCE = (
    'formal_universe',
    'raw_daily_panel',
    'liquidity_contract',
    'historical_label_provenance',
    'sector_membership_pit',
)
EVIDENCE_KEYS = {
    'artifact',
    'version',
    'strategy_id',
    'formal_end',
    'formal_artifact_sha256',
    'formal_calendar_sha256',
    'universe_sha256',
    'supporting_evidence',
    'feature_families',
}
FAMILY_KEYS = {
    'binding_state',
    'pit_state',
    'source_artifact',
    'source_sha256',
    'coverage_start',
    'coverage_end',
    'blockers',
}
SUPPORT_KEYS = {
    'binding_state',
    'pit_state',
    'source_artifact',
    'source_sha256',
    'ready',
    'blockers',
}
BINDING_STATES = {
    'BOUND_VERIFIED_ARTIFACT',
    'BOUND_STRUCTURAL_ONLY',
    'UNBOUND',
    'NOT_DIRECTLY_REQUIRED',
}
PIT_STATES = {
    'PIT_VERIFIED',
    'PIT_PARTIAL',
    'PIT_UNVERIFIED',
    'PIT_NOT_APPLICABLE',
}
FORBIDDEN_RESULT_KEYS = {
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
SHA_RE = re.compile(r'^[0-9a-f]{64}$')
FACTOR_IDS = tuple(f'F{i}' for i in range(1, 13))


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
        allow_nan=False,
    ).encode('utf-8')


def canonical_json_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _has_forbidden_result_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_RESULT_KEYS:
                return True
            if _has_forbidden_result_key(child):
                return True
    elif isinstance(value, list):
        return any(_has_forbidden_result_key(child) for child in value)
    return False


def _sha(value: object, label: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or SHA_RE.fullmatch(value) is None:
        raise ValueError(f'{label} must be a lowercase 64-hex SHA256')
    return value


def _iso_date(value: object, label: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ValueError(f'{label} must be an ISO date')
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f'{label} must be an ISO date') from exc
    if parsed.isoformat() != value:
        raise ValueError(f'{label} must use canonical ISO format')
    return value


def _blockers(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f'{label} blockers must be a list')
    normalized = []
    for blocker in value:
        if not isinstance(blocker, str) or not blocker.strip():
            raise ValueError(f'{label} blocker must be a nonempty string')
        normalized.append(blocker.strip())
    return sorted(set(normalized))


def validate_candidate_identity(parameters: dict, factors: dict) -> dict:
    if not isinstance(parameters, dict) or not isinstance(factors, dict):
        raise ValueError('candidate contracts must be objects')
    try:
        parameter_sha = canonical_json_sha256(parameters)
        factor_sha = canonical_json_sha256(factors)
    except (TypeError, ValueError) as exc:
        raise ValueError('candidate contracts must be finite canonical JSON') from exc
    if parameter_sha != PARAMETERS_SHA256:
        raise ValueError('candidate parameter identity mismatch')
    if factor_sha != FACTORS_SHA256:
        raise ValueError('candidate factor identity mismatch')
    if parameters.get('strategy_id') != STRATEGY_ID:
        raise ValueError('candidate parameter strategy mismatch')
    if factors.get('strategy_id') != STRATEGY_ID:
        raise ValueError('candidate factor strategy mismatch')
    return {
        'candidate_parameters_sha256': parameter_sha,
        'candidate_factors_sha256': factor_sha,
    }


def _validate_evidence_top_level(evidence_manifest: dict) -> None:
    if not isinstance(evidence_manifest, dict):
        raise ValueError('evidence manifest must be an object')
    if set(evidence_manifest) != EVIDENCE_KEYS:
        raise ValueError('evidence manifest schema mismatch')
    if _has_forbidden_result_key(evidence_manifest):
        raise ValueError('FORBIDDEN_OOS_OR_PERFORMANCE_FIELD')
    if evidence_manifest.get('artifact') != 'GP12_FORMAL_INPUT_EVIDENCE_V1':
        raise ValueError('evidence artifact mismatch')
    if evidence_manifest.get('version') != VERSION:
        raise ValueError('evidence version mismatch')
    if evidence_manifest.get('strategy_id') != STRATEGY_ID:
        raise ValueError('evidence strategy mismatch')
    if evidence_manifest.get('formal_end') != FORMAL_END:
        raise ValueError('FORMAL_BOUNDARY_VIOLATION')
    _sha(evidence_manifest.get('formal_artifact_sha256'), 'formal_artifact_sha256')
    _sha(evidence_manifest.get('formal_calendar_sha256'), 'formal_calendar_sha256')
    _sha(evidence_manifest.get('universe_sha256'), 'universe_sha256')


def _normalize_family(name: str, raw: object) -> dict:
    if not isinstance(raw, dict) or set(raw) != FAMILY_KEYS:
        raise ValueError(f'feature family schema mismatch: {name}')
    binding = raw.get('binding_state')
    pit = raw.get('pit_state')
    if binding not in BINDING_STATES:
        raise ValueError(f'invalid binding state: {name}')
    if pit not in PIT_STATES:
        raise ValueError(f'invalid PIT state: {name}')
    if binding == 'NOT_DIRECTLY_REQUIRED':
        raise ValueError(f'scorer family cannot be NOT_DIRECTLY_REQUIRED: {name}')

    source_artifact = raw.get('source_artifact')
    source_sha = raw.get('source_sha256')
    if binding in {'BOUND_VERIFIED_ARTIFACT', 'BOUND_STRUCTURAL_ONLY'}:
        if not isinstance(source_artifact, str) or not source_artifact.strip():
            raise ValueError(f'bound family requires source artifact: {name}')
        source_artifact = source_artifact.strip()
        source_sha = _sha(source_sha, f'{name}.source_sha256')
    else:
        if source_artifact is not None or source_sha is not None:
            raise ValueError(f'unbound family cannot carry source identity: {name}')

    coverage_start = _iso_date(raw.get('coverage_start'), f'{name}.coverage_start', nullable=True)
    coverage_end = _iso_date(raw.get('coverage_end'), f'{name}.coverage_end', nullable=True)
    if (coverage_start is None) != (coverage_end is None):
        raise ValueError(f'family coverage must provide both endpoints: {name}')
    if coverage_start is not None:
        if coverage_start > coverage_end:
            raise ValueError(f'family coverage reversed: {name}')
        if coverage_end > FORMAL_END:
            raise ValueError('FORMAL_BOUNDARY_VIOLATION')

    blockers = _blockers(raw.get('blockers'), name)
    ready = (
        binding == 'BOUND_VERIFIED_ARTIFACT'
        and pit == 'PIT_VERIFIED'
        and coverage_start is not None
        and coverage_end is not None
        and coverage_end <= FORMAL_END
        and not blockers
    )
    return {
        'binding_state': binding,
        'pit_state': pit,
        'source_artifact': source_artifact,
        'source_sha256': source_sha,
        'coverage_start': coverage_start,
        'coverage_end': coverage_end,
        'blockers': blockers,
        'formal_feature_ready': ready,
    }


def evaluate_feature_families(evidence_manifest: dict) -> dict[str, dict]:
    raw_families = evidence_manifest.get('feature_families')
    if not isinstance(raw_families, dict) or set(raw_families) != set(FEATURE_FAMILIES):
        raise ValueError('feature family set mismatch')
    return {
        name: _normalize_family(name, raw_families[name])
        for name in FEATURE_FAMILIES
    }


def _normalize_supporting(evidence_manifest: dict) -> dict[str, dict]:
    raw_support = evidence_manifest.get('supporting_evidence')
    if not isinstance(raw_support, dict) or set(raw_support) != set(SUPPORTING_EVIDENCE):
        raise ValueError('supporting evidence set mismatch')
    result = {}
    for name in SUPPORTING_EVIDENCE:
        raw = raw_support[name]
        if not isinstance(raw, dict) or set(raw) != SUPPORT_KEYS:
            raise ValueError(f'supporting evidence schema mismatch: {name}')
        binding = raw.get('binding_state')
        pit = raw.get('pit_state')
        if binding not in BINDING_STATES:
            raise ValueError(f'invalid supporting binding state: {name}')
        if pit not in PIT_STATES:
            raise ValueError(f'invalid supporting PIT state: {name}')
        source_artifact = raw.get('source_artifact')
        source_sha = raw.get('source_sha256')
        if binding in {'BOUND_VERIFIED_ARTIFACT', 'BOUND_STRUCTURAL_ONLY'}:
            if not isinstance(source_artifact, str) or not source_artifact.strip():
                raise ValueError(f'bound supporting evidence requires source artifact: {name}')
            source_artifact = source_artifact.strip()
            source_sha = _sha(source_sha, f'{name}.source_sha256')
        elif source_artifact is not None or source_sha is not None:
            raise ValueError(f'unbound supporting evidence cannot carry source identity: {name}')
        if not isinstance(raw.get('ready'), bool):
            raise ValueError(f'supporting ready flag must be boolean: {name}')
        result[name] = {
            'binding_state': binding,
            'pit_state': pit,
            'source_artifact': source_artifact,
            'source_sha256': source_sha,
            'ready': raw['ready'],
            'blockers': _blockers(raw.get('blockers'), name),
        }
    return result


def build_readiness_report(parameters: dict, factors: dict, evidence_manifest: dict) -> dict:
    identity = validate_candidate_identity(parameters, factors)
    _validate_evidence_top_level(evidence_manifest)
    families = evaluate_feature_families(evidence_manifest)
    supporting = _normalize_supporting(evidence_manifest)

    blockers = []
    for state in families.values():
        blockers.extend(state['blockers'])
    for state in supporting.values():
        blockers.extend(state['blockers'])
    blockers = sorted(set(blockers))

    validated_families = sorted(
        name for name, state in families.items() if state['formal_feature_ready'])
    missing_or_unvalidated = sorted(
        name for name, state in families.items() if not state['formal_feature_ready'])

    return {
        'artifact': ARTIFACT,
        'version': VERSION,
        'strategy_id': STRATEGY_ID,
        'candidate_adoption_status': 'UNAPPROVED',
        'formal_end': FORMAL_END,
        'formal_artifact_sha256': evidence_manifest['formal_artifact_sha256'],
        'formal_calendar_sha256': evidence_manifest['formal_calendar_sha256'],
        'universe_sha256': evidence_manifest['universe_sha256'],
        **identity,
        'supporting_evidence': supporting,
        'feature_families': families,
        'factor_readiness': {},
        'validated_families': validated_families,
        'missing_or_unvalidated_families': missing_or_unvalidated,
        'ready_factor_ids': [],
        'blocked_factor_ids': list(FACTOR_IDS),
        'blockers': blockers,
        'candidate_scoring_ready': False,
        'candidate_freeze_ready': False,
        'real_feature_inputs_validated': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }
