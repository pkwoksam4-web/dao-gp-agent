from __future__ import annotations

import json
import pathlib
import unittest

import gp12_formal_input_readiness_v1 as mod

ROOT = pathlib.Path(__file__).resolve().parents[1]
PARAMETERS = ROOT / 'data' / 'GP12_CANDIDATE_PARAMETERS_V1.json'
FACTORS = ROOT / 'data' / 'GP12_CANDIDATE_FACTORS_V1.json'
EVIDENCE = ROOT / 'data' / 'GP12_FORMAL_INPUT_EVIDENCE_V1.json'
BINDING = ROOT / 'data' / 'GP12_INTRADAY_FORMAL847_BINDING_V1.json'
BINDING_SHA = 'd65a7dac16525f360a4fc93b104c49e8ba279f7eae7c7ac0ba9fba834fc99573'
REMAINING = sorted([
    'ADJUSTED_CLOSE_PIT_UNVERIFIED', 'LABEL_PROVENANCE_UNBOUND',
    'MAIN_NET_FLOW_UNBOUND', 'MARKET_BENCHMARK_UNBOUND',
    'MARKET_BREADTH_UNBOUND', 'SECTOR_BREADTH_UNBOUND',
    'SECTOR_MEMBERSHIP_PIT_UNBOUND', 'SECTOR_SERIES_UNBOUND',
    'STATUS_SEMANTICS_INCOMPLETE', 'TURNOVER_RATIO_UNBOUND',
])


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


class IntradayIntegrationTests(unittest.TestCase):
    def test_binding_file_identity_and_safety(self):
        binding = load(BINDING)
        self.assertEqual(mod.canonical_json_sha256(binding), BINDING_SHA)
        self.assertEqual(binding['primary_source']['formal_symbols'], 847)
        self.assertEqual(binding['primary_source']['required_trade_dates'], 1011607)
        self.assertEqual(binding['primary_source']['primary_valid_trade_dates'], 1011606)
        self.assertEqual(binding['primary_source']['unique_gap'], '000638.SZ/2026-04-13')
        self.assertEqual(binding['exact_fallback']['bars_15m_count'], 16)
        self.assertEqual(binding['exact_fallback']['bars_60m_count'], 4)
        self.assertTrue(binding['coverage']['formal_847_15m_coverage_verified'])
        self.assertTrue(binding['coverage']['formal_847_60m_coverage_verified'])
        self.assertFalse(binding['coverage']['formal_847_minute_byte_coverage_verified'])
        self.assertFalse(binding['safety']['model_freeze_allowed'])
        self.assertFalse(binding['safety']['oos_metrics_allowed'])

    def test_readiness_closes_only_intraday_blockers(self):
        report = mod.build_readiness_report(load(PARAMETERS), load(FACTORS), load(EVIDENCE))
        for family in ('intraday_15m', 'intraday_60m'):
            state = report['feature_families'][family]
            self.assertEqual(state['binding_state'], 'BOUND_VERIFIED_ARTIFACT')
            self.assertEqual(state['pit_state'], 'PIT_VERIFIED')
            self.assertEqual(state['source_artifact'], 'GP12_INTRADAY_FORMAL847_BINDING_V1')
            self.assertEqual(state['source_sha256'], BINDING_SHA)
            self.assertTrue(state['formal_feature_ready'])
            self.assertEqual(state['blockers'], [])
        self.assertEqual(report['validated_families'], ['intraday_15m', 'intraday_60m', 'market_calendar'])
        self.assertEqual(report['ready_factor_ids'], ['F12'])
        self.assertEqual(report['blockers'], REMAINING)
        self.assertFalse(report['candidate_scoring_ready'])
        self.assertEqual(report['candidate_adoption_status'], 'UNAPPROVED')
        self.assertFalse(report['model_freeze_allowed'])
        self.assertFalse(report['oos_metrics_allowed'])


if __name__ == '__main__':
    unittest.main()
