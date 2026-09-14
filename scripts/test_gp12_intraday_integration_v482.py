from __future__ import annotations

import json
import pathlib
import unittest

import gp12_formal_input_readiness_v1 as mod


ROOT = pathlib.Path(__file__).resolve().parents[1]
PARAMETERS_PATH = ROOT / 'data' / 'GP12_CANDIDATE_PARAMETERS_V1.json'
FACTORS_PATH = ROOT / 'data' / 'GP12_CANDIDATE_FACTORS_V1.json'
EVIDENCE_PATH = ROOT / 'data' / 'GP12_FORMAL_INPUT_EVIDENCE_V1.json'

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


class GP12IntradayReadinessIntegrationTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
