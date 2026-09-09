import hashlib
import pathlib
import tempfile
import unittest

try:
    from build_audit_manifest_v1 import build_manifest
except ModuleNotFoundError:
    build_manifest = None


class ManifestIdentityLockTests(unittest.TestCase):
    def _cfg(self, root):
        p=pathlib.Path(root)/'large.bin'; p.write_bytes(b'authoritative-bytes')
        return p, {
            'artifact':'AUDIT_EVIDENCE_SOURCES_V1','version':'V1',
            'canonical_lineage':{
                'repository':'pkwoksam4-web/dao-gp-agent',
                'base_branch':'gp/gp12-formal-input-readiness-v1',
                'base_head_sha':'b815773d00e4c6bf775b3ce111aef3fc458cd741',
                'remediation_branch':'gp/audit-remediation-v1',
            },
            'required_governance_blockers':['PERMANENT_BYTE_ARCHIVE_OPEN','REPOSITORY_BRANCH_PROTECTION_OPEN','STRATEGY_ASSETS_INCOMPLETE'],
            'items':[{
                'logical_name':'LARGE','class':'LARGE_HASH_BOUND','path':str(p),
                'source_type':'GITHUB_ACTIONS','source_run_id':1,'source_artifact_id':2,
                'source_artifact_name':'large','source_artifact_digest':'sha256:'+'a'*64,
                'source_head_sha':'1'*40,'permanent_bytes_available':False,
                'expiry_at':'2026-10-01T00:00:00Z',
                'expected_sha256':hashlib.sha256(b'authoritative-bytes').hexdigest(),
                'expected_bytes':len(b'authoritative-bytes'),
            }],
        }

    def test_exact_expected_identity_passes_and_expected_fields_are_not_dropped(self):
        self.assertTrue(callable(build_manifest))
        with tempfile.TemporaryDirectory() as td:
            _,cfg=self._cfg(td); doc=build_manifest(cfg); item=doc['evidence_items'][0]
            self.assertEqual(item['sha256'],item['expected_sha256'])
            self.assertEqual(item['bytes'],item['expected_bytes'])

    def test_wrong_expected_sha_fails_closed(self):
        self.assertTrue(callable(build_manifest))
        with tempfile.TemporaryDirectory() as td:
            _,cfg=self._cfg(td); cfg['items'][0]['expected_sha256']='0'*64
            with self.assertRaises(ValueError): build_manifest(cfg)

    def test_wrong_expected_bytes_fails_closed(self):
        self.assertTrue(callable(build_manifest))
        with tempfile.TemporaryDirectory() as td:
            _,cfg=self._cfg(td); cfg['items'][0]['expected_bytes']+=1
            with self.assertRaises(ValueError): build_manifest(cfg)


if __name__=='__main__': unittest.main()
