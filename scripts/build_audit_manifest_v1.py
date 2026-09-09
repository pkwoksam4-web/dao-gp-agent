from __future__ import annotations

import json
import pathlib
import re
from copy import deepcopy

import pandas as pd

from audit_evidence_v1 import (
    CANONICAL_BASE_BRANCH,
    CANONICAL_BASE_HEAD,
    CANONICAL_REPOSITORY,
    schema_fingerprint,
    sha256_file,
    validate_artifact_digest,
    validate_evidence_manifest,
)

SHA40_RE = re.compile(r'^[0-9a-f]{40}$')


def _load_json(path: pathlib.Path | str) -> dict:
    p = pathlib.Path(path)
    value = json.loads(p.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError(f'{p}: JSON object required')
    return value


def enrich_raw_audit(audit_path, parquet_path) -> dict:
    audit = deepcopy(_load_json(audit_path))
    pq = pathlib.Path(parquet_path)
    frame = pd.read_parquet(pq)
    audit['full_parquet_sha256'] = sha256_file(pq)
    audit['full_parquet_bytes'] = pq.stat().st_size
    audit['schema_fingerprint'] = schema_fingerprint(frame)
    if 'raw_rows' in audit and int(audit['raw_rows']) != len(frame):
        raise ValueError('RAW row count does not match exact parquet bytes')
    return audit


def enrich_liquidity_audit(audit_path, panel_path, raw_path, pitst_path) -> dict:
    audit = deepcopy(_load_json(audit_path))
    panel = pathlib.Path(panel_path)
    frame = pd.read_parquet(panel)
    audit['input_full_raw_sha256'] = sha256_file(raw_path)
    audit['input_pitst_sha256'] = sha256_file(pitst_path)
    audit['panel_parquet_sha256'] = sha256_file(panel)
    audit['panel_parquet_bytes'] = panel.stat().st_size
    audit['schema_fingerprint'] = schema_fingerprint(frame)
    if 'panel_rows' in audit and int(audit['panel_rows']) != len(frame):
        raise ValueError('Liquidity row count does not match exact panel bytes')
    return audit


def _validate_lineage(lineage: dict) -> None:
    if not isinstance(lineage, dict):
        raise ValueError('canonical_lineage missing')
    expected = {
        'repository': CANONICAL_REPOSITORY,
        'base_branch': CANONICAL_BASE_BRANCH,
        'base_head_sha': CANONICAL_BASE_HEAD,
        'remediation_branch': 'gp/audit-remediation-v1',
    }
    for key, value in expected.items():
        if lineage.get(key) != value:
            raise ValueError(f'canonical lineage mismatch: {key}')


def _validate_source_provenance(item: dict) -> None:
    source_type = item.get('source_type')
    if source_type == 'GITHUB_ACTIONS':
        if not validate_artifact_digest(item.get('source_artifact_digest')):
            raise ValueError(f"artifact digest invalid: {item.get('logical_name')}")
        for key in ('source_run_id', 'source_artifact_id', 'source_artifact_name'):
            if not item.get(key):
                raise ValueError(f"Actions provenance missing {key}: {item.get('logical_name')}")
        if not SHA40_RE.fullmatch(str(item.get('source_head_sha') or '')):
            raise ValueError(f"Actions source head invalid: {item.get('logical_name')}")
        return
    if source_type == 'REPOSITORY':
        if 'source_artifact_digest' in item or 'source_artifact_id' in item or 'source_run_id' in item:
            raise ValueError(f"repository evidence must not carry fake Actions provenance: {item.get('logical_name')}")
        if not SHA40_RE.fullmatch(str(item.get('source_head_sha') or '')):
            raise ValueError(f"repository source head invalid: {item.get('logical_name')}")
        if not item.get('persisted_repository_path'):
            raise ValueError(f"repository evidence missing persisted path: {item.get('logical_name')}")
        return
    raise ValueError(f"unknown source_type: {source_type}")


def build_manifest(config: dict) -> dict:
    if not isinstance(config, dict) or config.get('artifact') != 'AUDIT_EVIDENCE_SOURCES_V1' or config.get('version') != 'V1':
        raise ValueError('evidence source config identity invalid')
    _validate_lineage(config.get('canonical_lineage'))
    items = config.get('items')
    if not isinstance(items, list):
        raise ValueError('items must be a list')

    evidence = []
    for raw in items:
        item = deepcopy(raw)
        p = pathlib.Path(str(item.pop('path', '')))
        if not p.is_file():
            raise FileNotFoundError(p)
        _validate_source_provenance(item)
        item['file_name'] = item.get('file_name') or p.name
        item['sha256'] = sha256_file(p)
        item['bytes'] = p.stat().st_size
        if p.suffix.lower() == '.parquet':
            frame = pd.read_parquet(p)
            item['row_count'] = len(frame)
            item['schema_fingerprint'] = schema_fingerprint(frame)
        if item.get('class') == 'LARGE_HASH_BOUND' and item.get('permanent_bytes_available') is True and item.get('expiry_at'):
            raise ValueError('Actions-only large bytes cannot be marked permanent')
        evidence.append(item)

    blockers = list(dict.fromkeys(config.get('required_governance_blockers') or []))
    manifest = {
        'artifact': 'AUDIT_EVIDENCE_MANIFEST_V1',
        'version': 'V1',
        'canonical_lineage': deepcopy(config['canonical_lineage']),
        'evidence_items': evidence,
        'blockers': blockers,
        'formal_promotion_allowed': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
        'baostock_847_scaleout_allowed': False,
    }
    errors = validate_evidence_manifest(manifest)
    if errors:
        raise ValueError('manifest validation failed: ' + '; '.join(errors))
    return manifest


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    cfg = _load_json(a.config)
    manifest = build_manifest(cfg)
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'evidence_n': len(manifest['evidence_items']), 'blockers': manifest['blockers']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
