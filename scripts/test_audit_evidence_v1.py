import hashlib
import json
import pathlib
import tempfile
import unittest

import pandas as pd

try:
    from audit_evidence_v1 import (
        sha256_file,
        schema_fingerprint,
        validate_sha256,
        validate_evidence_manifest,
        validate_status_model,
    )
except ModuleNotFoundError:
    sha256_file = None
    schema_fingerprint = None
    validate_sha256 = None
    validate_evidence_manifest = None
    validate_status_model = None


def require(fn, testcase):
    testcase.assertTrue(callable(fn), 'audit_evidence_v1 production function is missing')
    return fn


class FileIdentityTests(unittest.TestCase):
    def test_sha256_file_matches_exact_bytes_and_changes_on_mutation(self):
        fn = require(sha256_file, self)
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / 'x.bin'
            p.write_bytes(b'abc')
            first = fn(p)
            self.assertEqual(first, hashlib.sha256(b'abc').hexdigest())
            p.write_bytes(b'abd')
            self.assertNotEqual(fn(p), first)

    def test_schema_fingerprint_is_deterministic_and_order_sensitive(self):
        fn = require(schema_fingerprint, self)
        a = pd.DataFrame({'symbol': pd.Series(['000001.SZ'], dtype='string'), 'amount': pd.Series([1.0], dtype='float64')})
        b = a.copy()
        c = a[['amount', 'symbol']]
        self.assertEqual(fn(a), fn(b))
        self.assertNotEqual(fn(a), fn(c))

    def test_validate_sha256_rejects_malformed_values(self):
        fn = require(validate_sha256, self)
        self.assertTrue(fn('a' * 64))
        self.assertFalse(fn('A' * 64))
        self.assertFalse(fn('abc'))
        self.assertFalse(fn(None))


class ManifestValidationTests(unittest.TestCase):
    def _base(self):
        return {
            'artifact': 'AUDIT_EVIDENCE_MANIFEST_V1',
            'version': 'V1',
            'canonical_lineage': {
                'repository': 'pkwoksam4-web/dao-gp-agent',
                'base_branch': 'gp/gp12-formal-input-readiness-v1',
                'base_head_sha': 'b815773d00e4c6bf775b3ce111aef3fc458cd741',
                'remediation_branch': 'gp/audit-remediation-v1',
            },
            'evidence_items': [],
            'blockers': [],
            'formal_promotion_allowed': False,
            'model_freeze_allowed': False,
            'oos_metrics_allowed': False,
        }

    def test_actions_only_large_bytes_cannot_claim_permanence(self):
        fn = require(validate_evidence_manifest, self)
        doc = self._base()
        doc['evidence_items'] = [{
            'logical_name': 'FULL_RAW',
            'class': 'LARGE_HASH_BOUND',
            'source_run_id': 1,
            'source_artifact_id': 2,
            'source_artifact_name': 'raw',
            'source_artifact_digest': 'sha256:' + 'b' * 64,
            'file_name': 'raw.parquet',
            'sha256': 'c' * 64,
            'bytes': 10,
            'permanent_bytes_available': True,
            'expiry_at': '2026-10-01T00:00:00Z',
        }]
        self.assertIn('ACTIONS_ONLY_BYTES_FALSELY_PERMANENT:FULL_RAW', fn(doc))

    def test_conflicting_duplicate_logical_identity_is_rejected(self):
        fn = require(validate_evidence_manifest, self)
        doc = self._base()
        common = {
            'logical_name': 'RAW_AUDIT',
            'class': 'SMALL_PERSISTED',
            'source_run_id': 1,
            'source_artifact_id': 2,
            'source_artifact_name': 'raw',
            'source_artifact_digest': 'sha256:' + 'd' * 64,
            'file_name': 'audit.json',
            'bytes': 10,
            'permanent_bytes_available': True,
            'persisted_repository_path': 'evidence/audit.json',
        }
        doc['evidence_items'] = [dict(common, sha256='e' * 64), dict(common, sha256='f' * 64)]
        self.assertIn('CONFLICTING_LOGICAL_IDENTITY:RAW_AUDIT', fn(doc))


class StatusModelTests(unittest.TestCase):
    def test_status_model_rejects_upward_inference(self):
        fn = require(validate_status_model, self)
        doc = {
            'artifact': 'AUDIT_STATUS_MODEL_V1',
            'version': 'V1',
            'states': ['FORMAL_DATA_READY', 'FEATURE_INPUT_READY', 'STRATEGY_READY', 'MODEL_FROZEN', 'OOS_ADMITTED'],
            'implies': {'FORMAL_DATA_READY': ['STRATEGY_READY']},
        }
        self.assertIn('UPWARD_INFERENCE_FORBIDDEN:FORMAL_DATA_READY->STRATEGY_READY', fn(doc))


if __name__ == '__main__':
    unittest.main()
