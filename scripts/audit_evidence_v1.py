from __future__ import annotations

import hashlib
import json
import pathlib
import re
from collections import defaultdict


SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
ARTIFACT_DIGEST_RE = re.compile(r'^sha256:[0-9a-f]{64}$')
EVIDENCE_CLASSES = {'SMALL_PERSISTED', 'LARGE_HASH_BOUND'}
READINESS_STATES = [
    'FORMAL_DATA_READY',
    'FEATURE_INPUT_READY',
    'STRATEGY_READY',
    'MODEL_FROZEN',
    'OOS_ADMITTED',
]
CANONICAL_BASE_BRANCH = 'gp/gp12-formal-input-readiness-v1'
CANONICAL_BASE_HEAD = 'b815773d00e4c6bf775b3ce111aef3fc458cd741'
CANONICAL_REPOSITORY = 'pkwoksam4-web/dao-gp-agent'


def sha256_file(path: pathlib.Path | str) -> str:
    p = pathlib.Path(path)
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def schema_fingerprint(frame) -> str:
    payload = [
        {'name': str(name), 'dtype': str(dtype)}
        for name, dtype in zip(frame.columns.tolist(), frame.dtypes.tolist())
    ]
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def validate_sha256(value) -> bool:
    return bool(SHA256_RE.fullmatch(str(value or '')))


def validate_artifact_digest(value) -> bool:
    return bool(ARTIFACT_DIGEST_RE.fullmatch(str(value or '')))


def _append(errors: list[str], value: str) -> None:
    if value not in errors:
        errors.append(value)


def _valid_large_archive(item: dict, sha: str, size: int) -> bool:
    archive = item.get('archive')
    if not isinstance(archive, dict):
        return False
    if archive.get('provider') != 'GITHUB_RELEASE':
        return False
    if archive.get('repository') != CANONICAL_REPOSITORY:
        return False
    if not str(archive.get('release_tag') or '').strip():
        return False
    if not re.fullmatch(r'^[0-9a-f]{40}$', str(archive.get('release_target_sha') or '')):
        return False
    if archive.get('asset_name') != item.get('file_name'):
        return False
    if archive.get('sha256') != sha or not validate_sha256(archive.get('sha256')):
        return False
    try:
        archive_bytes = int(archive.get('bytes'))
    except (TypeError, ValueError):
        return False
    if archive_bytes != size:
        return False
    if archive.get('download_verified') is not True:
        return False
    return True


def validate_evidence_manifest(doc: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ['MANIFEST_NOT_OBJECT']
    if doc.get('artifact') != 'AUDIT_EVIDENCE_MANIFEST_V1' or doc.get('version') != 'V1':
        _append(errors, 'MANIFEST_IDENTITY_INVALID')

    lineage = doc.get('canonical_lineage')
    if not isinstance(lineage, dict):
        _append(errors, 'CANONICAL_LINEAGE_MISSING')
    else:
        if lineage.get('repository') != CANONICAL_REPOSITORY:
            _append(errors, 'CANONICAL_REPOSITORY_MISMATCH')
        if lineage.get('base_branch') != CANONICAL_BASE_BRANCH:
            _append(errors, 'CANONICAL_BASE_BRANCH_MISMATCH')
        if lineage.get('base_head_sha') != CANONICAL_BASE_HEAD:
            _append(errors, 'CANONICAL_BASE_HEAD_MISMATCH')
        if lineage.get('remediation_branch') != 'gp/audit-remediation-v1':
            _append(errors, 'REMEDIATION_BRANCH_MISMATCH')

    items = doc.get('evidence_items')
    if not isinstance(items, list):
        return errors + ['EVIDENCE_ITEMS_INVALID']

    by_logical: dict[str, set[str]] = defaultdict(set)
    by_source: dict[tuple, set[str]] = defaultdict(set)
    for item in items:
        if not isinstance(item, dict):
            _append(errors, 'EVIDENCE_ITEM_NOT_OBJECT')
            continue
        name = str(item.get('logical_name') or '').strip()
        if not name:
            _append(errors, 'EVIDENCE_LOGICAL_NAME_MISSING')
            name = '<missing>'
        cls = item.get('class')
        if cls not in EVIDENCE_CLASSES:
            _append(errors, f'UNKNOWN_EVIDENCE_CLASS:{name}')
        digest = item.get('source_artifact_digest')
        if digest is not None and not validate_artifact_digest(digest):
            _append(errors, f'ARTIFACT_DIGEST_INVALID:{name}')
        sha = item.get('sha256')
        if not validate_sha256(sha):
            _append(errors, f'FILE_SHA256_INVALID:{name}')
        try:
            size = int(item.get('bytes'))
        except (TypeError, ValueError):
            size = -1
        if size < 0:
            _append(errors, f'FILE_BYTES_INVALID:{name}')

        permanent = item.get('permanent_bytes_available')
        expiry = item.get('expiry_at')
        if cls == 'LARGE_HASH_BOUND' and permanent is True and expiry and not _valid_large_archive(item, str(sha or ''), size):
            _append(errors, f'ACTIONS_ONLY_BYTES_FALSELY_PERMANENT:{name}')
        if cls == 'SMALL_PERSISTED' and permanent is True and not item.get('persisted_repository_path'):
            _append(errors, f'PERSISTED_PATH_MISSING:{name}')

        if validate_sha256(sha):
            by_logical[name].add(str(sha))
            source_key = (
                item.get('source_run_id'),
                item.get('source_artifact_id'),
                item.get('file_name'),
            )
            by_source[source_key].add(str(sha))

    for name, hashes in by_logical.items():
        if len(hashes) > 1:
            _append(errors, f'CONFLICTING_LOGICAL_IDENTITY:{name}')
    for source_key, hashes in by_source.items():
        if len(hashes) > 1:
            _append(errors, 'CONFLICTING_SOURCE_IDENTITY:' + '|'.join(str(x) for x in source_key))

    if doc.get('model_freeze_allowed') is not False:
        _append(errors, 'MODEL_FREEZE_MUST_REMAIN_CLOSED')
    if doc.get('oos_metrics_allowed') is not False:
        _append(errors, 'OOS_METRICS_MUST_REMAIN_CLOSED')
    return errors


def validate_status_model(doc: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ['STATUS_MODEL_NOT_OBJECT']
    if doc.get('artifact') != 'AUDIT_STATUS_MODEL_V1' or doc.get('version') != 'V1':
        _append(errors, 'STATUS_MODEL_IDENTITY_INVALID')
    states = doc.get('states')
    if states != READINESS_STATES:
        _append(errors, 'STATUS_STATE_ORDER_INVALID')
    order = {name: i for i, name in enumerate(READINESS_STATES)}
    implies = doc.get('implies') or {}
    if not isinstance(implies, dict):
        _append(errors, 'STATUS_IMPLIES_INVALID')
        return errors
    for source, targets in implies.items():
        if source not in order:
            _append(errors, f'UNKNOWN_STATUS:{source}')
            continue
        if not isinstance(targets, list):
            _append(errors, f'STATUS_TARGETS_INVALID:{source}')
            continue
        for target in targets:
            if target not in order:
                _append(errors, f'UNKNOWN_STATUS:{target}')
            elif order[target] > order[source]:
                _append(errors, f'UPWARD_INFERENCE_FORBIDDEN:{source}->{target}')
    return errors
