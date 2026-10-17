from __future__ import annotations

import importlib
import json
import pathlib
import unittest

import gp12_formal_input_readiness_v1 as base

ROOT = pathlib.Path(__file__).resolve().parents[1]
PARAMETERS = ROOT / 'data' / 'GP12_CANDIDATE_PARAMETERS_V1.json'
FACTORS = ROOT / 'data' / 'GP12_CANDIDATE_FACTORS_V1.json'
EVIDENCE = ROOT / 'data' / 'GP12_FORMAL_INPUT_EVIDENCE_V1.json'
INTRADAY = ROOT / 'data' / 'GP12_INTRADAY_FORMAL847_BINDING_V1.json'
PIT = ROOT / 'data' / 'GP12_PIT_ADJUSTED_CLOSE_BINDING_V1.json'
TURNOVER = ROOT / 'data' / 'GP12_AMOUNT_TURNOVER_BINDING_V1.json'
TURNOVER_SHA = '14e5f80915305ad5a6293f5cec3606b3d637a30720b0b9f355ffe1baf21fc96f'
REMAINING = sorted([
    'LABEL_PROVENANCE_UNBOUND',
    'MAIN_NET_FLOW_UNBOUND',
    'MARKET_BENCHMARK_UNBOUND',
    'MARKET_BREADTH_UNBOUND',
    'SECTOR_BREADTH_UNBOUND',
    'SECTOR_MEMBERSHIP_PIT_UNBOUND',
    'SECTOR_SERIES_UNBOUND',
    'STATUS_SEMANTICS_INCOMPLETE',
])


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def subject():
    try:
        return importlib.import_module('gp12_turnover_readiness_integration_v482')
    except ModuleNotFoundError as exc:
        raise AssertionError('gp12_turnover_readiness_integration_v482 production module is missing') from exc


class TurnoverReadinessIntegrationTests(unittest.TestCase):
    def test_frozen_v1_manifest_stays_unmodified(self):
        evidence = load(EVIDENCE)
        amount_turnover = evidence['feature_families']['amount_turnover']
        self.assertEqual(amount_turnover['binding_state'], 'UNBOUND')
        self.assertEqual(amount_turnover['pit_state'], 'PIT_UNVERIFIED')
        self.assertEqual(amount_turnover['blockers'], ['TURNOVER_RATIO_UNBOUND'])
        self.assertTrue(base.validate_production_evidence_manifest(evidence)['production_manifest_valid'])

    def test_turnover_binding_pins_amount_and_turnover_sources_and_safety(self):
        m = subject()
        binding = load(TURNOVER)
        self.assertEqual(base.canonical_json_sha256(binding), TURNOVER_SHA)
        self.assertEqual(m.validate_turnover_binding(binding), TURNOVER_SHA)
        self.assertEqual(binding['amount_source']['raw_daily_sha256'], base.RAW_ARTIFACT_SHA256)
        self.assertEqual(binding['amount_source']['liquidity_sha256'], base.LIQUIDITY_ARTIFACT_SHA256)
        self.assertTrue(binding['amount_source']['amount_cny_formal_verified'])
        audit = binding['turnover_source_audit']
        self.assertEqual(audit['workflow_run'], 34937058721)
        self.assertEqual(audit['workflow_head'], 'c8a3db077d3dc73e188937e9c355bc0bfa863382')
        self.assertEqual(audit['artifact_id'], 10383758045)
        self.assertEqual(audit['scope_n'], 847)
        self.assertEqual(audit['turnover_symbol_n'], 844)
        self.assertEqual(audit['turnover_rows'], 1_011_607)
        self.assertEqual(audit['missing_n'], 0)
        self.assertEqual(audit['extra_n'], 0)
        self.assertEqual(audit['duplicate_n'], 0)
        self.assertEqual(audit['bad_turnover_n'], 0)
        self.assertEqual(audit['unresolved_symbol_n'], 0)
        self.assertTrue(audit['source_semantics_verified'])
        self.assertTrue(audit['turnover_ratio_pit_verified'])
        self.assertLessEqual(audit['cross_source_sohu_max_diff_bp'], 0.5)
        self.assertEqual(audit['cross_source_sohu_fail_n'], 0)
        self.assertEqual(binding['safety']['candidate_adoption_status'], 'UNAPPROVED')
        self.assertFalse(binding['safety']['candidate_scoring_ready'])
        self.assertFalse(binding['safety']['model_freeze_allowed'])
        self.assertFalse(binding['safety']['oos_metrics_allowed'])

    def test_checkpoint_closes_only_amount_turnover_after_intraday_and_pit(self):
        m = subject()
        report = m.build_turnover_checkpoint(
            load(PARAMETERS),
            load(FACTORS),
            load(EVIDENCE),
            load(INTRADAY),
            load(PIT),
            load(TURNOVER),
        )
        self.assertEqual(report['artifact'], 'GP12_FORMAL_INPUT_READINESS_INTRADAY_PIT_TURNOVER_V482')
        self.assertEqual(report['turnover_binding_sha256'], TURNOVER_SHA)
        self.assertEqual(report['validated_families'], [
            'amount_turnover', 'intraday_15m', 'intraday_60m',
            'market_calendar', 'stock_adjusted_close',
        ])
        self.assertEqual(report['ready_factor_ids'], ['F6','F7','F8','F9','F10','F12'])
        self.assertEqual(report['factor_readiness']['F11']['dependencies'], [
            'stock_adjusted_close', 'amount_turnover', 'main_net_flow'])
        self.assertEqual(report['factor_readiness']['F11']['missing_dependencies'], ['main_net_flow'])
        self.assertFalse(report['factor_readiness']['F11']['ready'])
        self.assertEqual(report['blockers'], REMAINING)
        self.assertNotIn('TURNOVER_RATIO_UNBOUND', report['blockers'])
        self.assertFalse(report['candidate_scoring_ready'])
        self.assertFalse(report['real_feature_inputs_validated'])
        self.assertEqual(report['candidate_adoption_status'], 'UNAPPROVED')
        self.assertFalse(report['candidate_freeze_ready'])
        self.assertFalse(report['model_freeze_allowed'])
        self.assertFalse(report['oos_metrics_allowed'])

    def test_turnover_binding_rejects_weakened_coverage_or_safety(self):
        m = subject()
        binding = load(TURNOVER)
        broken = json.loads(json.dumps(binding))
        broken['turnover_source_audit']['missing_n'] = 1
        with self.assertRaisesRegex(ValueError, 'TURNOVER_BINDING_IDENTITY_MISMATCH|turnover missing rows remain'):
            m.validate_turnover_binding(broken)

        broken = json.loads(json.dumps(binding))
        broken['safety']['oos_metrics_allowed'] = True
        with self.assertRaisesRegex(ValueError, 'TURNOVER_BINDING_IDENTITY_MISMATCH|turnover binding cannot open OOS metrics'):
            m.validate_turnover_binding(broken)


if __name__ == '__main__':
    unittest.main()
