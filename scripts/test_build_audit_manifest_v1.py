import hashlib
import json
import pathlib
import tempfile
import unittest

import pandas as pd

try:
    from build_audit_manifest_v1 import (
        build_manifest,
        enrich_raw_audit,
        enrich_liquidity_audit,
    )
except ModuleNotFoundError:
    build_manifest = None
    enrich_raw_audit = None
    enrich_liquidity_audit = None

from audit_evidence_v1 import validate_evidence_manifest


def require(fn, testcase):
    testcase.assertTrue(callable(fn), 'build_audit_manifest_v1 production function is missing')
    return fn


class RebindingTests(unittest.TestCase):
    def test_raw_audit_is_enriched_from_exact_parquet_bytes(self):
        fn=require(enrich_raw_audit,self)
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            pq=root/'raw.parquet'; audit=root/'raw.json'
            pd.DataFrame([{'symbol':'000001.SZ','date':'2020-06-01','close':10.0}]).to_parquet(pq,index=False)
            audit.write_text(json.dumps({'artifact':'SOHU_RAW_FULL_V482','version':'V4.82','raw_rows':1}),encoding='utf-8')
            out=fn(audit,pq)
            self.assertEqual(out['full_parquet_sha256'],hashlib.sha256(pq.read_bytes()).hexdigest())
            self.assertEqual(out['full_parquet_bytes'],pq.stat().st_size)
            self.assertEqual(out['raw_rows'],1)
            self.assertRegex(out['schema_fingerprint'],r'^[0-9a-f]{64}$')

    def test_liquidity_rebinding_hash_links_raw_and_pitst_inputs(self):
        fn=require(enrich_liquidity_audit,self)
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            panel=root/'panel.parquet'; raw=root/'raw.parquet'; pit=root/'pit.csv'; audit=root/'liq.json'
            pd.DataFrame([{'symbol':'000001.SZ','eligible_non_st':True}]).to_parquet(panel,index=False)
            raw.write_bytes(b'exact-raw')
            pit.write_text('symbol,date,tradestatus,isST\n000001.SZ,2020-06-01,1,0\n',encoding='utf-8')
            audit.write_text(json.dumps({'artifact':'LIQUIDITY_80M_APPLY_V482','version':'V4.82','panel_rows':1}),encoding='utf-8')
            out=fn(audit,panel,raw,pit)
            self.assertEqual(out['input_full_raw_sha256'],hashlib.sha256(raw.read_bytes()).hexdigest())
            self.assertEqual(out['input_pitst_sha256'],hashlib.sha256(pit.read_bytes()).hexdigest())
            self.assertEqual(out['panel_parquet_sha256'],hashlib.sha256(panel.read_bytes()).hexdigest())
            self.assertEqual(out['panel_parquet_bytes'],panel.stat().st_size)


class ManifestBuildTests(unittest.TestCase):
    def _config(self, root):
        small=root/'small.json'; large=root/'large.bin'
        small.write_text('{"x":1}',encoding='utf-8'); large.write_bytes(b'large-bytes')
        return {
            'artifact':'AUDIT_EVIDENCE_SOURCES_V1','version':'V1',
            'canonical_lineage':{
                'repository':'pkwoksam4-web/dao-gp-agent',
                'base_branch':'gp/gp12-formal-input-readiness-v1',
                'base_head_sha':'b815773d00e4c6bf775b3ce111aef3fc458cd741',
                'remediation_branch':'gp/audit-remediation-v1',
            },
            'required_governance_blockers':['PERMANENT_BYTE_ARCHIVE_OPEN','REPOSITORY_BRANCH_PROTECTION_OPEN','STRATEGY_ASSETS_INCOMPLETE'],
            'items':[
                {
                    'logical_name':'SMALL','class':'SMALL_PERSISTED','path':str(small),
                    'source_type':'REPOSITORY','source_head_sha':'1'*40,
                    'persisted_repository_path':'evidence/audit-remediation-v1/small.json',
                    'permanent_bytes_available':True,
                },
                {
                    'logical_name':'LARGE','class':'LARGE_HASH_BOUND','path':str(large),
                    'source_type':'GITHUB_ACTIONS','source_run_id':3,'source_artifact_id':4,'source_artifact_name':'large',
                    'source_artifact_digest':'sha256:'+'b'*64,'source_head_sha':'2'*40,
                    'permanent_bytes_available':False,'expiry_at':'2026-10-01T00:00:00Z',
                },
            ],
        }

    def test_manifest_requires_exact_canonical_lineage(self):
        fn=require(build_manifest,self)
        with tempfile.TemporaryDirectory() as td:
            cfg=self._config(pathlib.Path(td)); cfg['canonical_lineage'].pop('base_head_sha')
            with self.assertRaises(ValueError): fn(cfg)

    def test_actions_item_rejects_malformed_artifact_digest(self):
        fn=require(build_manifest,self)
        with tempfile.TemporaryDirectory() as td:
            cfg=self._config(pathlib.Path(td)); cfg['items'][1]['source_artifact_digest']='bad'
            with self.assertRaises(ValueError): fn(cfg)

    def test_repository_small_evidence_does_not_require_fake_artifact_digest(self):
        fn=require(build_manifest,self)
        with tempfile.TemporaryDirectory() as td:
            cfg=self._config(pathlib.Path(td)); manifest=fn(cfg)
            small=next(x for x in manifest['evidence_items'] if x['logical_name']=='SMALL')
            self.assertEqual(small['source_type'],'REPOSITORY')
            self.assertNotIn('source_artifact_digest',small)
            self.assertTrue(small['permanent_bytes_available'])

    def test_manifest_rejects_conflicting_logical_identity(self):
        fn=require(build_manifest,self)
        with tempfile.TemporaryDirectory() as td:
            cfg=self._config(pathlib.Path(td)); other=pathlib.Path(td)/'other.bin'; other.write_bytes(b'other')
            dup=dict(cfg['items'][1]); dup['path']=str(other); cfg['items'].append(dup)
            with self.assertRaises(ValueError): fn(cfg)

    def test_manifest_keeps_required_governance_blockers_visible(self):
        fn=require(build_manifest,self)
        with tempfile.TemporaryDirectory() as td:
            cfg=self._config(pathlib.Path(td)); manifest=fn(cfg)
            self.assertIn('PERMANENT_BYTE_ARCHIVE_OPEN',manifest['blockers'])
            self.assertIn('REPOSITORY_BRANCH_PROTECTION_OPEN',manifest['blockers'])
            self.assertIn('STRATEGY_ASSETS_INCOMPLETE',manifest['blockers'])
            self.assertFalse(manifest['formal_promotion_allowed'])
            self.assertFalse(manifest['model_freeze_allowed'])
            self.assertFalse(manifest['oos_metrics_allowed'])
            self.assertFalse(manifest['baostock_847_scaleout_allowed'])
            self.assertEqual(validate_evidence_manifest(manifest),[])

    def test_actions_only_large_bytes_cannot_be_marked_permanent(self):
        fn=require(build_manifest,self)
        with tempfile.TemporaryDirectory() as td:
            cfg=self._config(pathlib.Path(td)); cfg['items'][1]['permanent_bytes_available']=True
            with self.assertRaises(ValueError): fn(cfg)


if __name__=='__main__': unittest.main()
