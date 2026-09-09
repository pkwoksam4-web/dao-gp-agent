from __future__ import annotations

from copy import deepcopy

from audit_evidence_v1 import CANONICAL_REPOSITORY, validate_evidence_manifest, validate_sha256

ARCHIVE_PROVIDER = 'GITHUB_RELEASE'
ARCHIVE_RELEASE_TAG = 'gp-evidence-v482-audit-v1'
ARCHIVE_TARGET_SHA = 'ee445e5dae3f2b78328d72de144d15f4c52e77ad'


def _large_items(manifest: dict) -> dict[str, dict]:
    items = manifest.get('evidence_items')
    if not isinstance(items, list):
        raise ValueError('manifest evidence_items invalid')
    out: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict) or item.get('class') != 'LARGE_HASH_BOUND':
            continue
        name = str(item.get('logical_name') or '').strip()
        if not name or name in out:
            raise ValueError('large evidence logical identity invalid')
        out[name] = item
    if not out:
        raise ValueError('no large evidence items')
    return out


def validate_archive_receipt(manifest: dict, receipt: dict) -> dict[str, dict]:
    if not isinstance(receipt, dict):
        raise ValueError('archive receipt must be object')
    if receipt.get('artifact') != 'PERMANENT_ARCHIVE_RECEIPT_V1' or receipt.get('version') != 'V1':
        raise ValueError('archive receipt identity invalid')
    if receipt.get('provider') != ARCHIVE_PROVIDER:
        raise ValueError('archive provider invalid')
    if receipt.get('repository') != CANONICAL_REPOSITORY:
        raise ValueError('archive repository mismatch')
    if receipt.get('release_tag') != ARCHIVE_RELEASE_TAG:
        raise ValueError('archive release tag mismatch')
    if receipt.get('release_target_sha') != ARCHIVE_TARGET_SHA:
        raise ValueError('archive release target mismatch')

    large = _large_items(manifest)
    assets = receipt.get('assets')
    if not isinstance(assets, list):
        raise ValueError('archive assets invalid')
    by_name: dict[str, dict] = {}
    for asset in assets:
        if not isinstance(asset, dict):
            raise ValueError('archive asset invalid')
        name = str(asset.get('logical_name') or '').strip()
        if not name or name in by_name:
            raise ValueError('duplicate or missing archive logical asset')
        by_name[name] = asset

    if set(by_name) != set(large):
        raise ValueError('archive asset coverage mismatch')

    for name, item in large.items():
        asset = by_name[name]
        if asset.get('asset_name') != item.get('file_name'):
            raise ValueError(f'archive asset name mismatch: {name}')
        if not validate_sha256(asset.get('sha256')) or asset.get('sha256') != item.get('sha256'):
            raise ValueError(f'archive sha256 mismatch: {name}')
        try:
            asset_bytes = int(asset.get('bytes'))
            item_bytes = int(item.get('bytes'))
        except (TypeError, ValueError):
            raise ValueError(f'archive bytes invalid: {name}')
        if asset_bytes != item_bytes:
            raise ValueError(f'archive bytes mismatch: {name}')
        if asset.get('download_verified') is not True:
            raise ValueError(f'archive download unverified: {name}')
    return by_name


def apply_archive_receipt(manifest: dict, receipt: dict) -> dict:
    by_name = validate_archive_receipt(manifest, receipt)
    out = deepcopy(manifest)
    for item in out['evidence_items']:
        if item.get('class') != 'LARGE_HASH_BOUND':
            continue
        asset = by_name[item['logical_name']]
        item['permanent_bytes_available'] = True
        item['archive'] = {
            'provider': receipt['provider'],
            'repository': receipt['repository'],
            'release_tag': receipt['release_tag'],
            'release_target_sha': receipt['release_target_sha'],
            'asset_name': asset['asset_name'],
            'sha256': asset['sha256'],
            'bytes': int(asset['bytes']),
            'download_verified': True,
            'browser_download_url': asset.get('browser_download_url'),
            'release_asset_id': asset.get('release_asset_id'),
        }
    blockers = [b for b in (out.get('blockers') or []) if b != 'PERMANENT_BYTE_ARCHIVE_OPEN']
    out['blockers'] = blockers
    out['permanent_archive_receipt'] = {
        'artifact': receipt['artifact'],
        'version': receipt['version'],
        'provider': receipt['provider'],
        'release_tag': receipt['release_tag'],
        'release_target_sha': receipt['release_target_sha'],
    }
    errors = validate_evidence_manifest(out)
    if errors:
        raise ValueError('archived manifest validation failed: ' + '; '.join(errors))
    return out
