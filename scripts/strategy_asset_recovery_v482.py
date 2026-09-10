from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any


VERSION = 'V4.82'
ARTIFACT = 'STRATEGY_ASSET_RECOVERY_CHECKPOINT_V482'
EVIDENCE_ARTIFACT = 'GP_V11_STRATEGY_RECOVERY_EVIDENCE_V482'
STRATEGY_ID = 'GP_V11'

BASE_BLOCKERS = (
    'FACTOR_DEFINITION_MISSING',
    'PARAMETER_SET_MISSING',
    'STRATEGY_CODE_MISSING',
)
ALLOWED_CONFIDENCE = {
    'AUTHORITATIVE_FILE',
    'USER_CONFIRMED',
    'CONVERSATION_CANDIDATE_UNCONFIRMED',
    'ABSENT',
    'UNINSPECTABLE',
}
EVIDENCE_KEYS = {
    'artifact',
    'version',
    'strategy_id',
    'searched_surfaces',
    'confirmed_rules',
    'candidate_clues',
    'recovered_assets',
    'missing_required_fields',
}
FORBIDDEN_METRIC_KEYS = {
    'return', 'returns', 'pnl', 'alpha', 'sharpe', 'drawdown',
    'hit_rate', 'win_rate', 'performance', 'metrics',
}
SHA_RE = re.compile(r'^[0-9a-f]{64}$')


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')


def canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _has_forbidden_metric_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_METRIC_KEYS:
                return True
            if _has_forbidden_metric_key(child):
                return True
    elif isinstance(value, list):
        return any(_has_forbidden_metric_key(child) for child in value)
    return False


def _require_confidence(items: Any, label: str) -> None:
    if not isinstance(items, list):
        raise ValueError(f'{label} must be a list')
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f'{label} item must be an object')
        if item.get('confidence') not in ALLOWED_CONFIDENCE:
            raise ValueError(f'{label} confidence invalid')


def _sha_ok(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA_RE.fullmatch(value))


def _validate_recovered_assets(items: Any) -> tuple[list[dict], bool]:
    if not isinstance(items, list):
        raise ValueError('recovered_assets must be a list')
    normalized: list[dict] = []
    seen_keys: set[str] = set()
    daily_base_code_recovered = False
    required_keys = {
        'key', 'confidence', 'scope', 'source_id', 'archive_sha256',
        'files', 'complete_12_factor_strategy',
    }
    for item in items:
        if not isinstance(item, dict) or set(item) != required_keys:
            raise ValueError('recovered asset schema mismatch')
        key = item.get('key')
        if key in seen_keys:
            raise ValueError('duplicate recovered asset key')
        seen_keys.add(key)
        if key != 'daily_base_strategy_code':
            raise ValueError('unknown recovered asset key')
        if item.get('confidence') != 'AUTHORITATIVE_FILE':
            raise ValueError('recovered asset confidence insufficient')
        if item.get('scope') != 'DAILY_BASE_ONLY':
            raise ValueError('daily base recovered asset scope invalid')
        if item.get('complete_12_factor_strategy') is not False:
            raise ValueError('daily base scope cannot claim complete 12-factor strategy')
        source_id = item.get('source_id')
        if not isinstance(source_id, str) or not source_id:
            raise ValueError('recovered asset source_id invalid')
        if not _sha_ok(item.get('archive_sha256')):
            raise ValueError('recovered asset archive sha256 invalid')
        files = item.get('files')
        if not isinstance(files, list) or not files:
            raise ValueError('recovered asset files invalid')
        seen_paths: set[str] = set()
        for f in files:
            if not isinstance(f, dict) or set(f) != {'path', 'sha256'}:
                raise ValueError('recovered asset file schema mismatch')
            path = f.get('path')
            if not isinstance(path, str) or not path:
                raise ValueError('recovered asset file path invalid')
            if path in seen_paths:
                raise ValueError('duplicate recovered asset file path')
            seen_paths.add(path)
            if not _sha_ok(f.get('sha256')):
                raise ValueError('recovered asset file sha256 invalid')
        normalized.append(copy.deepcopy(item))
        daily_base_code_recovered = True
    return normalized, daily_base_code_recovered


def validate_evidence(evidence: dict) -> None:
    if not isinstance(evidence, dict):
        raise ValueError('strategy recovery evidence must be an object')
    if set(evidence) != EVIDENCE_KEYS:
        raise ValueError('strategy recovery evidence schema mismatch')
    if evidence.get('artifact') != EVIDENCE_ARTIFACT:
        raise ValueError('strategy recovery evidence artifact mismatch')
    if evidence.get('version') != VERSION:
        raise ValueError('strategy recovery evidence version mismatch')
    if evidence.get('strategy_id') != STRATEGY_ID:
        raise ValueError('strategy recovery strategy_id mismatch')
    if _has_forbidden_metric_key(evidence):
        raise ValueError('forbidden OOS metric field in strategy recovery evidence')

    _require_confidence(evidence.get('searched_surfaces'), 'searched_surfaces')
    _require_confidence(evidence.get('confirmed_rules'), 'confirmed_rules')
    _require_confidence(evidence.get('candidate_clues'), 'candidate_clues')
    _validate_recovered_assets(evidence.get('recovered_assets'))

    for item in evidence['candidate_clues']:
        if item.get('confidence') != 'CONVERSATION_CANDIDATE_UNCONFIRMED':
            raise ValueError('candidate clue must remain unconfirmed')
    for item in evidence['confirmed_rules']:
        if item.get('confidence') not in {'USER_CONFIRMED', 'AUTHORITATIVE_FILE'}:
            raise ValueError('confirmed rule confidence insufficient')

    missing = evidence.get('missing_required_fields')
    if not isinstance(missing, list) or not missing or any(not isinstance(x, str) or not x for x in missing):
        raise ValueError('missing_required_fields invalid')
    if len(missing) != len(set(missing)):
        raise ValueError('missing_required_fields contains duplicates')


def _validate_recovery_checkpoint(checkpoint: dict) -> None:
    if not isinstance(checkpoint, dict):
        raise ValueError('model recovery checkpoint must be an object')
    if checkpoint.get('artifact') != 'MODEL_ASSET_RECOVERY_CHECKPOINT_V482':
        raise ValueError('model recovery checkpoint artifact mismatch')
    if checkpoint.get('version') != VERSION:
        raise ValueError('model recovery checkpoint version mismatch')
    blockers = checkpoint.get('blockers')
    if not isinstance(blockers, list):
        raise ValueError('model recovery checkpoint blockers invalid')
    for blocker in BASE_BLOCKERS:
        if blocker not in blockers:
            raise ValueError('expected strategy blocker absent from upstream checkpoint')
    if checkpoint.get('model_freeze_allowed') is not False:
        raise ValueError('upstream checkpoint unexpectedly allows model freeze')


def _authoritative_asset_state(authoritative_assets: dict | None) -> tuple[bool, bool, bool, dict]:
    assets = authoritative_assets or {}
    if not isinstance(assets, dict):
        raise ValueError('authoritative_assets must be an object')
    allowed = {'strategy_code', 'parameters', 'factor_definition'}
    if not set(assets).issubset(allowed):
        raise ValueError('authoritative_assets schema mismatch')
    if _has_forbidden_metric_key(assets):
        raise ValueError('forbidden OOS metric field in authoritative assets')

    normalized: dict[str, Any] = {}

    code = assets.get('strategy_code')
    code_ok = False
    if code is not None:
        if not isinstance(code, dict) or set(code) != {'confidence', 'bytes_sha256', 'source_id'}:
            raise ValueError('strategy_code asset schema mismatch')
        code_ok = (
            code.get('confidence') == 'AUTHORITATIVE_FILE'
            and _sha_ok(code.get('bytes_sha256'))
            and isinstance(code.get('source_id'), str)
            and bool(code.get('source_id'))
        )
        if not code_ok:
            raise ValueError('strategy_code authoritative evidence invalid')
        normalized['strategy_code'] = copy.deepcopy(code)

    params = assets.get('parameters')
    params_ok = False
    if params is not None:
        if not isinstance(params, dict) or set(params) != {'confidence', 'canonical_sha256', 'source_id', 'complete'}:
            raise ValueError('parameters asset schema mismatch')
        if params.get('confidence') != 'AUTHORITATIVE_FILE' or not _sha_ok(params.get('canonical_sha256')):
            raise ValueError('parameters authoritative evidence invalid')
        if not isinstance(params.get('source_id'), str) or not params.get('source_id'):
            raise ValueError('parameters source_id invalid')
        if not isinstance(params.get('complete'), bool):
            raise ValueError('parameters complete flag invalid')
        params_ok = params['complete'] is True
        normalized['parameters'] = copy.deepcopy(params)

    factors = assets.get('factor_definition')
    factors_ok = False
    if factors is not None:
        if not isinstance(factors, dict) or set(factors) != {'confidence', 'canonical_sha256', 'source_id', 'complete'}:
            raise ValueError('factor_definition asset schema mismatch')
        if factors.get('confidence') != 'AUTHORITATIVE_FILE' or not _sha_ok(factors.get('canonical_sha256')):
            raise ValueError('factor_definition authoritative evidence invalid')
        if not isinstance(factors.get('source_id'), str) or not factors.get('source_id'):
            raise ValueError('factor_definition source_id invalid')
        if not isinstance(factors.get('complete'), bool):
            raise ValueError('factor_definition complete flag invalid')
        factors_ok = factors['complete'] is True
        normalized['factor_definition'] = copy.deepcopy(factors)

    return code_ok, params_ok, factors_ok, normalized


def evaluate_strategy_recovery(
    recovery_checkpoint: dict,
    evidence: dict,
    authoritative_assets: dict | None = None,
) -> dict:
    _validate_recovery_checkpoint(recovery_checkpoint)
    validate_evidence(evidence)
    recovered_assets, daily_base_code_recovered = _validate_recovered_assets(evidence['recovered_assets'])
    code_ok, params_ok, factors_ok, normalized_assets = _authoritative_asset_state(authoritative_assets)

    blockers = [b for b in recovery_checkpoint['blockers'] if b not in BASE_BLOCKERS]
    if not factors_ok:
        blockers.append('FACTOR_DEFINITION_MISSING')
    if not params_ok:
        blockers.append('PARAMETER_SET_MISSING')
    if not code_ok:
        blockers.append('STRATEGY_CODE_MISSING')
    blockers = sorted(set(blockers))

    candidate_clues = []
    for clue in evidence['candidate_clues']:
        item = copy.deepcopy(clue)
        item['freeze_eligible'] = False
        candidate_clues.append(item)

    model_freeze_allowed = not blockers
    return {
        'artifact': ARTIFACT,
        'version': VERSION,
        'strategy_id': STRATEGY_ID,
        'status': 'STRATEGY_ASSETS_COMPLETE_V482' if model_freeze_allowed else 'STRATEGY_ASSETS_INCOMPLETE_V482',
        'strategy_code_recovered': code_ok,
        'daily_base_code_recovered': daily_base_code_recovered,
        'parameter_set_recovered': params_ok,
        'factor_definition_recovered': factors_ok,
        'strategy_assets': normalized_assets,
        'recovered_assets': recovered_assets,
        'evidence_sha256': canonical_json_sha256(evidence),
        'searched_surfaces': copy.deepcopy(evidence['searched_surfaces']),
        'confirmed_rules': copy.deepcopy(evidence['confirmed_rules']),
        'candidate_clues': candidate_clues,
        'missing_required_fields': copy.deepcopy(evidence['missing_required_fields']),
        'blockers': blockers,
        'model_freeze_allowed': model_freeze_allowed,
        'oos_metrics_allowed': False,
    }
