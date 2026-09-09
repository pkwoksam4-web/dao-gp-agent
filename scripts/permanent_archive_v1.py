from __future__ import annotations

from copy import deepcopy

from audit_evidence_v1 import CANONICAL_REPOSITORY, validate_evidence_manifest, validate_sha256

GITHUB_RELEASE_PROVIDER = 'GITHUB_RELEASE'
GOOGLE_DRIVE_PROVIDER = 'GOOGLE_DRIVE_ARTIFACT_ZIP'
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


def _validate_common_asset(name: str, item: dict, asset: dict) -> None:
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


def validate_archive_receipt(manifest: dict, receipt: dict) -> dict[str, dict]:
    if not isinstance(receipt, dict):
        raise ValueError('archive receipt must be object')
    if receipt.get('artifact') != 'PERMANENT_ARCHIVE_RECEIPT_V1' or receipt.get('version') != 'V1':
        raise ValueError('archive receipt identity invalid')
    provider = receipt.get('provider')
    if provider not in {GITHUB_RELEASE_PROVIDER, GOOGLE_DRIVE_PROVIDER}:
        raise ValueError('archive provider invalid')
    if receipt.get('repository') != CANONICAL_REPOSITORY:
        raise ValueError('archive repository mismatch')

    if provider == GITHUB_RELEASE_PROVIDER:
        if receipt.get('release_tag') != ARCHIVE_RELEASE_TAG:
            raise ValueError('archive release tag mismatch')
        if receipt.get('release_target_sha') != ARCHIVE_TARGET_SHA:
            raise ValueError('archive release target mismatch')
    else:
        if receipt.get('archive_target_sha') != ARCHIVE_TARGET_SHA:
            raise ValueError('archive target mismatch')
        if not str(receipt.get('folder_id') or '').strip():
            raise ValueError('drive archive folder missing')
        if receipt.get('retention_lock') not in {True, False}:
            raise ValueError('drive retention lock state missing')

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
        _validate_common_asset(name, item, asset)
        if provider == GOOGLE_DRIVE_PROVIDER:
            if not str(asset.get('drive_file_id') or '').strip():
                raise ValueError(f'drive file id missing: {name}')
            if not str(asset.get('archive_container_name') or '').strip():
                raise ValueError(f'archive container name missing: {name}')
            if not validate_sha256(asset.get('archive_container_sha256')):
                raise ValueError(f'archive container sha256 invalid: {name}')
            try:
                container_bytes = int(asset.get('archive_container_bytes'))
            except (TypeError, ValueError):
                raise ValueError(f'archive container bytes invalid: {name}')
            if container_bytes <= 0:
                raise ValueError(f'archive container bytes invalid: {name}')
    return by_name


def apply_archive_receipt(manifest: dict, receipt: dict) -> dict:
    by_name = validate_archive_receipt(manifest, receipt)
    provider = receipt['provider']
    out = deepcopy(manifest)
    for item in out['evidence_items']:
        if item.get('class') != 'LARGE_HASH_BOUND':
            continue
        asset = by_name[item['logical_name']]
        item['permanent_bytes_available'] = True
        archive = {
            'provider': provider,
            'repository': receipt['repository'],
            'asset_name': asset['asset_name'],
            'sha256': asset['sha256'],
            'bytes': int(asset['bytes']),
            'download_verified': True,
        }
        if provider == GITHUB_RELEASE_PROVIDER:
            archive.update({
                'release_tag': receipt['release_tag'],
                'release_target_sha': receipt['release_target_sha'],
                'browser_download_url': asset.get('browser_download_url'),
                'release_asset_id': asset.get('release_asset_id'),
            })
        else:
            archive.update({
                'archive_target_sha': receipt['archive_target_sha'],
                'folder_id': receipt['folder_id'],
                'drive_file_id': asset['drive_file_id'],
                'archive_container_name': asset['archive_container_name'],
                'archive_container_sha256': asset['archive_container_sha256'],
                'archive_container_bytes': int(asset['archive_container_bytes']),
                'retention_lock': bool(receipt['retention_lock']),
            })
        item['archive'] = archive

    blockers = [b for b in (out.get('blockers') or []) if b != 'PERMANENT_BYTE_ARCHIVE_OPEN']
    if provider == GOOGLE_DRIVE_PROVIDER and receipt.get('retention_lock') is not True:
        if 'IMMUTABLE_RETENTION_LOCK_OPEN' not in blockers:
            blockers.append('IMMUTABLE_RETENTION_LOCK_OPEN')
    out['blockers'] = blockers
    receipt_summary = {
        'artifact': receipt['artifact'],
        'version': receipt['version'],
        'provider': provider,
    }
    if provider == GITHUB_RELEASE_PROVIDER:
        receipt_summary.update({'release_tag': receipt['release_tag'], 'release_target_sha': receipt['release_target_sha']})
    else:
        receipt_summary.update({
            'archive_target_sha': receipt['archive_target_sha'],
            'folder_id': receipt['folder_id'],
            'retention_lock': bool(receipt['retention_lock']),
        })
    out['permanent_archive_receipt'] = receipt_summary
    errors = validate_evidence_manifest(out)
    if errors:
        raise ValueError('archived manifest validation failed: ' + '; '.join(errors))
    return out
