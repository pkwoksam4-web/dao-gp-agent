import hashlib
import json
import pathlib
import unittest

try:
    from audit_semantics_v1 import (
        symbol_set_sha256,
        validate_fixed_probe_registry,
        validate_pitst_coverage,
    )
except ModuleNotFoundError:
    symbol_set_sha256 = None
    validate_fixed_probe_registry = None
    validate_pitst_coverage = None

from audit_evidence_v1 import validate_status_model

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'


def require(fn, testcase):
    testcase.assertTrue(callable(fn), 'audit_semantics_v1 production function is missing')
    return fn


class FixedProbeRegistryTests(unittest.TestCase):
    RAW5=['000001.SZ','000014.SZ','001201.SZ','002001.SZ','002002.SZ']

    def test_symbol_hash_is_sorted_newline_canonical(self):
        fn=require(symbol_set_sha256,self)
        expected=hashlib.sha256(('\n'.join(sorted(self.RAW5))+'\n').encode()).hexdigest()
        self.assertEqual(fn(list(reversed(self.RAW5))),expected)

    def test_bare_fixed5_and_wrong_symbol_hash_are_rejected(self):
        fn=require(validate_fixed_probe_registry,self)
        doc={
            'artifact':'FIXED_PROBE_REGISTRY_V1','version':'V1','bare_label_forbidden':True,
            'probes':[{
                'probe_id':'fixed5','probe_kind':'EXACT_FIXED_SET','ordered_symbols':self.RAW5,
                'sorted_symbol_sha256':'0'*64,'promotion_eligible':False,
            }],
            'unverified_prior_assertions':[],
        }
        errors=fn(doc)
        self.assertIn('BARE_FIXED5_LABEL_FORBIDDEN:fixed5',errors)
        self.assertIn('SYMBOL_SET_HASH_MISMATCH:fixed5',errors)

    def test_repository_registry_separates_raw_fixed5_from_qfq_semantic_pilot(self):
        fn=require(validate_fixed_probe_registry,self)
        p=DATA/'FIXED_PROBE_REGISTRY_V1.json'
        self.assertTrue(p.exists(),'FIXED_PROBE_REGISTRY_V1.json is missing')
        doc=json.loads(p.read_text(encoding='utf-8'))
        self.assertEqual(fn(doc),[])
        by={x['probe_id']:x for x in doc['probes']}
        raw=by['RAW_PITST_SOURCE_FIXED5_V482']
        self.assertEqual(raw['ordered_symbols'],self.RAW5)
        self.assertEqual(raw['sorted_symbol_sha256'],'b6b69832cec5e97ac1c8a7bf3e6dd432fca070f4d3e5d28e697f161d9fd615fc')
        self.assertEqual(raw['source_run_id'],34350541625)
        self.assertEqual(raw['source_artifact_id'],10103537004)
        qfq=by['QFQ_SEMANTIC_PILOT_V471_V477']
        self.assertEqual(qfq['ordered_symbols'],['002938.SZ','300592.SZ'])
        self.assertEqual(qfq['contract_status'],'NOT_AN_EXACT_FIXED5_CONTRACT')
        self.assertFalse(qfq['promotion_eligible'])
        self.assertTrue(any(x['status']=='UNVERIFIED_PRIOR_ASSERTION_NOT_FREEZE_ELIGIBLE' for x in doc['unverified_prior_assertions']))


class PitStCoverageTests(unittest.TestCase):
    def test_false_full_audit_claim_is_rejected_when_only_sampled(self):
        fn=require(validate_pitst_coverage,self)
        doc={
            'artifact':'PIT_ST_EVIDENCE_COVERAGE_V1','version':'V1',
            'label':'INDEPENDENT_SAMPLE_CROSSCHECK',
            'observed_transition_symbol_n':233,'observed_transition_n':386,
            'independent_symbol_n':3,'independent_transition_n':6,
            'independent_full_transition_audit_pass':True,
            'sample_transition_ids':['a','b','c','d','e','f'],
        }
        self.assertIn('FALSE_FULL_INDEPENDENT_AUDIT_CLAIM',fn(doc))

    def test_repository_coverage_locks_233_386_and_3_6(self):
        fn=require(validate_pitst_coverage,self)
        p=DATA/'PIT_ST_EVIDENCE_COVERAGE_V1.json'
        self.assertTrue(p.exists(),'PIT_ST_EVIDENCE_COVERAGE_V1.json is missing')
        doc=json.loads(p.read_text(encoding='utf-8'))
        self.assertEqual(fn(doc),[])
        self.assertEqual(doc['observed_transition_symbol_n'],233)
        self.assertEqual(doc['observed_transition_n'],386)
        self.assertEqual(doc['independent_symbol_n'],3)
        self.assertEqual(doc['independent_transition_n'],6)
        self.assertAlmostEqual(doc['transition_coverage_pct'],100*6/386,places=8)
        self.assertEqual(doc['label'],'INDEPENDENT_SAMPLE_CROSSCHECK')


class StatusArtifactTests(unittest.TestCase):
    def test_repository_status_model_has_no_upward_inference(self):
        p=DATA/'AUDIT_STATUS_MODEL_V1.json'
        self.assertTrue(p.exists(),'AUDIT_STATUS_MODEL_V1.json is missing')
        doc=json.loads(p.read_text(encoding='utf-8'))
        self.assertEqual(validate_status_model(doc),[])
        self.assertEqual(doc['implies'],{})
        self.assertFalse(doc['current_state']['feature_input_ready'])
        self.assertFalse(doc['current_state']['strategy_ready'])
        self.assertFalse(doc['current_state']['model_frozen'])
        self.assertFalse(doc['current_state']['oos_admitted'])


if __name__=='__main__':
    unittest.main()
