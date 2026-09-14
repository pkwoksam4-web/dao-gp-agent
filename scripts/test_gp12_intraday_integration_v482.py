from __future__ import annotations

import copy
import json
import pathlib
import unittest

import gp12_formal_input_readiness_v1 as mod


ROOT = pathlib.Path(__file__).resolve().parents[1]
PARAMETERS_PATH = ROOT / 'data' / 'GP12_CANDIDATE_PARAMETERS_V1.json'
FACTORS_PATH = ROOT / 'data' / 'GP12_CANDIDATE_FACTORS_V1.json'
EVIDENCE_PATH = ROOT / 'data' / 'GP12_FORMAL_INPUT_EVIDENCE_V1.json'
INTRADAY_EVIDENCE_PATH = ROOT / 'data' / 'GP12_INTRADAY_FORMAL847_BINDING_V1.json'
INTRADAY_BINDING_SHA256 = 'd65a7dac16525f360a4fc93b104c49e8ba279f7eae7c7ac0ba9fba834fc99573'

EXPECTED_REMAINING_BLOCKERS = sorted([
    'ADJUSTED_CLOSE_PIT_UNVERIFIED',
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


def load_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def with_intraday_binding(evidence: dict, sha256: str = INTRADAY_BINDING_SHA256) -> dict:
    result = copy.deepcopy(evidence)
    for family in ('intraday_15m', 'intraday_60m'):
        result['feature_families'][family] = {
            'binding_state': 'BOUND_VERIFIED_ARTIFACT',
            'pit_state': 'PIT_VERIFIED',
            'source_artifact': 'GP12_INTRADAY_FORMAL847_BINDING_V1',
            'source_sha256': sha256,
            'coverage_start': '2020-06-01',
            'coverage_end': '2026-04-17',
            'blockers': [],
        }
    return result


class GP12IntradayReadinessIntegrationTests(unittest.TestCase):
    def test_intraday_binding_evidence_file_is_canonical_and_fail_closed(self):
        self.assertTrue(INTRADAY_EVIDENCE_PATH.exists())
        binding = load_json(INTRADAY_EVIDENCE_PATH)
        self.assertEqual(mod.canonical_json_sha256(binding), INTRADAY_BINDING_SHA256)
        self.assertTrue(binding['coverage']['formal_847_15m_coverage_verified'])
        self.assertTrue(binding['coverage']['formal_847_60m_coverage_verified'])
        self.assertFalse(binding['coverage']['formal_847_minute_byte_coverage_verified'])
        self.assertFalse(binding['coverage']['historical_gp_intraday_resampling_contract_recovered'])
        self.assertFalse(binding['coverage']['factor_formula_recovered'])
        self.assertEqual(binding['safety']['candidate_adoption_status'], 'UNAPPROVED')
        self.assertFalse(binding['safety']['model_freeze_allowed'])
        self.assertFalse(binding['safety']['oos_metrics_allowed'])

    def test_repository_manifest_binds_formal847_intraday_without_opening_freeze(self):
        evidence = load_json(EVIDENCE_PATH)
        report = mod.build_readiness_report(
            load_json(PARAMETERS_PATH), load_json(FACTORS_PATH), evidence)

        for family in ('intraday_15m', 'intraday_60m'):
            state = report['feature_families'][family]
            self.assertEqual(state['binding_state'], 'BOUND_VERIFIED_ARTIFACT')
            self.assertEqual(state['pit_state'], 'PIT_VERIFIED')
            self.assertTrue(state['formal_feature_ready'])
            self.assertEqual(state['coverage_start'], '2020-06-01')
            self.assertEqual(state['coverage_end'], '2026-04-17')
            self.assertEqual(state['blockers'], [])

        self.assertEqual(
            report['validated_families'],
            ['intraday_15m', 'intraday_60m', 'market_calendar'],
        )
        self.assertEqual(report['ready_factor_ids'], ['F12'])
        self.assertEqual(report['blockers'], EXPECTED_REMAINING_BLOCKERS)
        self.assertFalse(report['candidate_scoring_ready'])
        self.assertEqual(report['candidate_adoption_status'], 'UNAPPROVED')
        self.assertFalse(report['candidate_freeze_ready'])
        self.assertFalse(report['model_freeze_allowed'])
        self.assertFalse(report['oos_metrics_allowed'])

    def test_intraday_binding_identity_tamper_is_rejected(self):
        evidence = with_intraday_binding(load_json(EVIDENCE_PATH), '9' * 64)
        validation = mod.validate_production_evidence_manifest(evidence)
        self.assertIn('INTRADAY_EVIDENCE_INVALID', validation['blockers'])


if __name__ == '__main__':
    unittest.main()
