from __future__ import annotations

import json
import pathlib
import unittest

import gp12_formal_input_readiness_v1 as base
import gp12_pit_readiness_integration_v482 as integ

ROOT = pathlib.Path(__file__).resolve().parents[1]
PARAMETERS = ROOT / 'data' / 'GP12_CANDIDATE_PARAMETERS_V1.json'
FACTORS = ROOT / 'data' / 'GP12_CANDIDATE_FACTORS_V1.json'
EVIDENCE = ROOT / 'data' / 'GP12_FORMAL_INPUT_EVIDENCE_V1.json'
INTRADAY = ROOT / 'data' / 'GP12_INTRADAY_FORMAL847_BINDING_V1.json'
PIT = ROOT / 'data' / 'GP12_PIT_ADJUSTED_CLOSE_BINDING_V1.json'
PIT_SHA = 'c06d22448f43ffcb47568cce60db0c3da18aa14c7b022a35997cdfdc3f5b66c0'
REMAINING = sorted([
    'LABEL_PROVENANCE_UNBOUND',
    'MAIN_NET_FLOW_UNBOUND',
    'MARKET_BENCHMARK_UNBOUND',
    'MARKET_BREADTH_UNBOUND',
    'SECTOR_BREADTH_UNBOUND',
    'SECTOR_MEMBERSHIP_PIT_UNBOUND',
    'SECTOR_SERIES_UNBOUND',
    'STATUS_SEMANTICS_INCOMPLETE',
    'TURNOVER_RATIO_UNBOUND',
])


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


class PitReadinessIntegrationTests(unittest.TestCase):
    def test_frozen_v1_manifest_stays_unmodified(self):
        evidence = load(EVIDENCE)
        stock = evidence['feature_families']['stock_adjusted_close']
        self.assertEqual(stock['binding_state'], 'BOUND_STRUCTURAL_ONLY')
        self.assertEqual(stock['pit_state'], 'PIT_UNVERIFIED')
        self.assertEqual(stock['source_artifact'], 'FORMAL_READINESS_FINAL_V482')
        self.assertEqual(stock['blockers'], ['ADJUSTED_CLOSE_PIT_UNVERIFIED'])
        self.assertEqual(evidence['feature_families']['intraday_15m']['binding_state'], 'UNBOUND')
        self.assertEqual(evidence['feature_families']['intraday_60m']['binding_state'], 'UNBOUND')
        self.assertTrue(base.validate_production_evidence_manifest(evidence)['production_manifest_valid'])

    def test_pit_binding_identity_and_safety(self):
        binding = load(PIT)
        self.assertEqual(base.canonical_json_sha256(binding), PIT_SHA)
        self.assertEqual(binding['source_audit']['workflow_run'], 34928104668)
        self.assertEqual(binding['source_audit']['artifact_id'], 10380675799)
        self.assertEqual(binding['source_audit']['audit_json_sha256'], '2d75ace7461d4e7879e49a1678bb0d51f0acc3ca3abdc380c068876c1c569c6e')
        self.assertEqual(binding['source_audit']['universe_n'], 847)
        self.assertEqual(binding['source_audit']['formal_symbol_n'], 844)
        self.assertEqual(binding['source_audit']['raw_trade_rows'], 1011607)
        self.assertEqual(binding['source_audit']['constant_scale_pass_n'], 844)
        self.assertEqual(binding['source_audit']['constant_scale_fail_n'], 0)
        self.assertLessEqual(binding['source_audit']['max_constant_scale_diff_bp'], 5.0)
        self.assertEqual(binding['source_audit']['special_prev_close_pass_n'], 11)
        self.assertTrue(binding['source_audit']['adjusted_close_pit_verified'])
        self.assertTrue(binding['coverage']['stock_adjusted_close_pit_verified'])
        self.assertTrue(binding['coverage']['f6_f10_scale_invariance_verified'])
        self.assertEqual(binding['safety']['candidate_adoption_status'], 'UNAPPROVED')
        self.assertFalse(binding['safety']['candidate_scoring_ready'])
        self.assertFalse(binding['safety']['model_freeze_allowed'])
        self.assertFalse(binding['safety']['oos_metrics_allowed'])

    def test_downstream_checkpoint_closes_only_adjusted_close_after_intraday(self):
        report = integ.build_pit_checkpoint(
            load(PARAMETERS), load(FACTORS), load(EVIDENCE), load(INTRADAY), load(PIT))
        self.assertEqual(report['artifact'], 'GP12_FORMAL_INPUT_READINESS_INTRADAY_PIT_V482')
        self.assertEqual(report['upstream_artifact'], 'GP12_FORMAL_INPUT_READINESS_INTRADAY_V482')
        self.assertEqual(report['pit_binding_sha256'], PIT_SHA)
        self.assertEqual(report['validated_families'], [
            'intraday_15m', 'intraday_60m', 'market_calendar', 'stock_adjusted_close'])
        self.assertEqual(report['ready_factor_ids'], ['F6','F7','F8','F9','F10','F12'])
        self.assertEqual(report['blockers'], REMAINING)
        self.assertFalse(report['candidate_scoring_ready'])
        self.assertFalse(report['real_feature_inputs_validated'])
        self.assertEqual(report['candidate_adoption_status'], 'UNAPPROVED')
        self.assertFalse(report['candidate_freeze_ready'])
        self.assertFalse(report['model_freeze_allowed'])
        self.assertFalse(report['oos_metrics_allowed'])


if __name__ == '__main__':
    unittest.main()
