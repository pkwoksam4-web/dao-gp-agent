import copy
import unittest

try:
    from permanent_archive_v1 import validate_archive_receipt, apply_archive_receipt
except ModuleNotFoundError:
    validate_archive_receipt = None
    apply_archive_receipt = None

from audit_evidence_v1 import validate_evidence_manifest


def require(fn, testcase):
    testcase.assertTrue(callable(fn), 'permanent_archive_v1 production function is missing')
    return fn


class PermanentArchiveReceiptTests(unittest.TestCase):
    def _manifest(self):
        return {
            'artifact': 'AUDIT_EVIDENCE_MANIFEST_V1',
            'version': 'V1',
            'canonical_lineage': {
                'repository': 'pkwoksam4-web/dao-gp-agent',
                'base_branch': 'gp/gp12-formal-input-readiness-v1',
                'base_head_sha': 'b815773d00e4c6bf775b3ce111aef3fc458cd741',
                'remediation_branch': 'gp/audit-remediation-v1',
            },
            'evidence_items': [
                {
                    'logical_name': 'FULL_RAW_PARQUET_V482',
                    'class': 'LARGE_HASH_BOUND',
                    'source_type': 'GITHUB_ACTIONS',
                    'source_run_id': 34192233633,
                    'source_artifact_id': 10042614517,
                    'source_artifact_name': 'gp-sohu-full-raw-v482-reaudit',
                    'source_artifact_digest': 'sha256:' + 'a' * 64,
                    'source_head_sha': '8' * 40,
                    'file_name': 'SOHU_RAW_FULL_V482.parquet',
                    'sha256': '1' * 64,
                    'bytes': 100,
                    'permanent_bytes_available': False,
                    'expiry_at': '2026-10-08T05:51:50Z',
                },
                {
                    'logical_name': 'LIQUIDITY_80M_PANEL_V482',
                    'class': 'LARGE_HASH_BOUND',
                    'source_type': 'GITHUB_ACTIONS',
                    'source_run_id': 34192233633,
                    'source_artifact_id': 10042615093,
                    'source_artifact_name': 'gp-liquidity-80m-v482',
                    'source_artifact_digest': 'sha256:' + 'b' * 64,
                    'source_head_sha': '8' * 40,
                    'file_name': 'LIQUIDITY_80M_PANEL_V482.parquet',
                    'sha256': '2' * 64,
                    'bytes': 200,
                    'permanent_bytes_available': False,
                    'expiry_at': '2026-10-08T05:51:52Z',
                },
            ],
            'blockers': ['PERMANENT_BYTE_ARCHIVE_OPEN', 'REPOSITORY_BRANCH_PROTECTION_OPEN'],
            'formal_promotion_allowed': False,
            'model_freeze_allowed': False,
            'oos_metrics_allowed': False,
            'baostock_847_scaleout_allowed': False,
        }

    def _receipt(self):
        return {
            'artifact': 'PERMANENT_ARCHIVE_RECEIPT_V1',
            'version': 'V1',
            'provider': 'GITHUB_RELEASE',
            'repository': 'pkwoksam4-web/dao-gp-agent',
            'release_tag': 'gp-evidence-v482-audit-v1',
            'release_target_sha': 'ee445e5dae3f2b78328d72de144d15f4c52e77ad',
            'assets': [
                {
                    'logical_name': 'FULL_RAW_PARQUET_V482',
                    'asset_name': 'SOHU_RAW_FULL_V482.parquet',
                    'sha256': '1' * 64,
                    'bytes': 100,
                    'download_verified': True,
                },
                {
                    'logical_name': 'LIQUIDITY_80M_PANEL_V482',
                    'asset_name': 'LIQUIDITY_80M_PANEL_V482.parquet',
                    'sha256': '2' * 64,
                    'bytes': 200,
                    'download_verified': True,
                },
            ],
        }

    def test_exact_release_receipt_closes_only_archive_blocker(self):
        fn = require(apply_archive_receipt, self)
        manifest = fn(self._manifest(), self._receipt())
        self.assertNotIn('PERMANENT_BYTE_ARCHIVE_OPEN', manifest['blockers'])
        self.assertIn('REPOSITORY_BRANCH_PROTECTION_OPEN', manifest['blockers'])
        self.assertFalse(manifest['model_freeze_allowed'])
        self.assertFalse(manifest['oos_metrics_allowed'])
        for item in manifest['evidence_items']:
            self.assertTrue(item['permanent_bytes_available'])
            self.assertEqual(item['archive']['provider'], 'GITHUB_RELEASE')
            self.assertEqual(item['archive']['sha256'], item['sha256'])
            self.assertEqual(item['archive']['bytes'], item['bytes'])
        self.assertEqual(validate_evidence_manifest(manifest), [])

    def test_wrong_release_download_sha_fails_closed(self):
        fn = require(validate_archive_receipt, self)
        receipt = self._receipt()
        receipt['assets'][0]['sha256'] = 'f' * 64
        with self.assertRaises(ValueError):
            fn(self._manifest(), receipt)

    def test_unverified_download_fails_closed(self):
        fn = require(validate_archive_receipt, self)
        receipt = self._receipt()
        receipt['assets'][0]['download_verified'] = False
        with self.assertRaises(ValueError):
            fn(self._manifest(), receipt)

    def test_missing_asset_fails_closed(self):
        fn = require(validate_archive_receipt, self)
        receipt = self._receipt()
        receipt['assets'] = receipt['assets'][:1]
        with self.assertRaises(ValueError):
            fn(self._manifest(), receipt)

    def test_duplicate_logical_asset_fails_closed(self):
        fn = require(validate_archive_receipt, self)
        receipt = self._receipt()
        receipt['assets'].append(copy.deepcopy(receipt['assets'][0]))
        with self.assertRaises(ValueError):
            fn(self._manifest(), receipt)


if __name__ == '__main__':
    unittest.main()
