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

FORMAL_SHA256 = 'e642481399a05635d07b1baa39f57d3aa84dfd1c18e315edd927ec42da553796'
CALENDAR_SHA256 = '5a872a47cf7a338cc48aa628b8de46053fddc3ed161a2617550199d0607efae7'
UNIVERSE_SHA256 = 'dfe5c75692d38e5fde7cd5c32eb2ed090a8ab6dffcfd41d5ebda07dc2d6d96fb'
RAW_ARTIFACT_SHA256 = 'cee7e91f1fda605f7c3bdf41c3f4a7796feeae83f8c3702e50900e6af3fa9550'
LIQUIDITY_ARTIFACT_SHA256 = 'a041d50ab2c9bbbe5f129d9afae87e817de0b1d8073c86cf829427f031bbc37b'


def load_parameters():
    return json.loads(PARAMETERS_PATH.read_text(encoding='utf-8'))


def load_factors():
    return json.loads(FACTORS_PATH.read_text(encoding='utf-8'))


def unbound_family(blocker):
    return {
        'binding_state': 'UNBOUND',
        'pit_state': 'PIT_UNVERIFIED',
        'source_artifact': None,
        'source_sha256': None,
        'coverage_start': None,
        'coverage_end': None,
        'blockers': [blocker],
    }


def production_evidence():
    return {
        'artifact': 'GP12_FORMAL_INPUT_EVIDENCE_V1',
        'version': '1.0',
        'strategy_id': 'GP12_REBUILD_CANDIDATE_V1',
        'formal_end': '2026-04-17',
        'formal_artifact_sha256': FORMAL_SHA256,
        'formal_calendar_sha256': CALENDAR_SHA256,
        'universe_sha256': UNIVERSE_SHA256,
        'supporting_evidence': {
            'formal_universe': {
                'binding_state': 'BOUND_VERIFIED_ARTIFACT',
                'pit_state': 'PIT_NOT_APPLICABLE',
                'source_artifact': 'PIT_ST_SCOPE_V480',
                'source_sha256': UNIVERSE_SHA256,
                'ready': True,
                'blockers': [],
            },
            'raw_daily_panel': {
                'binding_state': 'BOUND_VERIFIED_ARTIFACT',
                'pit_state': 'PIT_PARTIAL',
                'source_artifact': 'gp-sohu-full-raw-v482-reaudit',
                'source_sha256': RAW_ARTIFACT_SHA256,
                'ready': True,
                'blockers': [],
            },
            'liquidity_contract': {
                'binding_state': 'BOUND_VERIFIED_ARTIFACT',
                'pit_state': 'PIT_VERIFIED',
                'source_artifact': 'gp-liquidity-80m-v482',
                'source_sha256': LIQUIDITY_ARTIFACT_SHA256,
                'ready': True,
                'blockers': [],
            },
            'historical_label_provenance': {
                'binding_state': 'UNBOUND',
                'pit_state': 'PIT_UNVERIFIED',
                'source_artifact': None,
                'source_sha256': None,
                'ready': False,
                'blockers': ['LABEL_PROVENANCE_UNBOUND'],
            },
            'sector_membership_pit': {
                'binding_state': 'UNBOUND',
                'pit_state': 'PIT_UNVERIFIED',
                'source_artifact': None,
                'source_sha256': None,
                'ready': False,
                'blockers': ['SECTOR_MEMBERSHIP_PIT_UNBOUND'],
            },
        },
        'feature_families': {
            'market_calendar': {
                'binding_state': 'BOUND_VERIFIED_ARTIFACT',
                'pit_state': 'PIT_VERIFIED',
                'source_artifact': 'OFFICIAL_A_SHARE_OPEN_DATES_V357',
                'source_sha256': CALENDAR_SHA256,
                'coverage_start': '2020-06-01',
                'coverage_end': '2026-04-17',
                'blockers': [],
            },
            'stock_adjusted_close': {
                'binding_state': 'BOUND_STRUCTURAL_ONLY',
                'pit_state': 'PIT_UNVERIFIED',
                'source_artifact': 'FORMAL_READINESS_FINAL_V482',
                'source_sha256': FORMAL_SHA256,
                'coverage_start': '2020-06-01',
                'coverage_end': '2026-04-17',
                'blockers': ['ADJUSTED_CLOSE_PIT_UNVERIFIED'],
            },
            'market_adjusted_close': unbound_family('MARKET_BENCHMARK_UNBOUND'),
            'sector_adjusted_close': unbound_family('SECTOR_SERIES_UNBOUND'),
            'amount_turnover': unbound_family('TURNOVER_RATIO_UNBOUND'),
            'main_net_flow': unbound_family('MAIN_NET_FLOW_UNBOUND'),
            'market_breadth': unbound_family('MARKET_BREADTH_UNBOUND'),
            'sector_breadth': unbound_family('SECTOR_BREADTH_UNBOUND'),
            'status': {
                'binding_state': 'BOUND_STRUCTURAL_ONLY',
                'pit_state': 'PIT_PARTIAL',
                'source_artifact': 'gp-liquidity-80m-v482',
                'source_sha256': LIQUIDITY_ARTIFACT_SHA256,
                'coverage_start': '2020-06-01',
                'coverage_end': '2026-04-17',
                'blockers': ['STATUS_SEMANTICS_INCOMPLETE'],
            },
            'intraday_15m': unbound_family('INTRADAY_15M_UNBOUND'),
            'intraday_60m': unbound_family('INTRADAY_60M_UNBOUND'),
        },
    }


class ProductionEvidenceBindingTests(unittest.TestCase):
    def test_exact_production_manifest_validates(self):
        validation = mod.validate_production_evidence_manifest(production_evidence())
        self.assertEqual(validation['blockers'], [])
        self.assertTrue(validation['production_manifest_valid'])

    def test_formal_identity_mismatch_is_deterministically_blocked(self):
        evidence = production_evidence()
        evidence['formal_artifact_sha256'] = '1' * 64
        validation = mod.validate_production_evidence_manifest(evidence)
        self.assertIn('FORMAL_EVIDENCE_INVALID', validation['blockers'])

    def test_calendar_identity_mismatch_is_deterministically_blocked(self):
        evidence = production_evidence()
        evidence['formal_calendar_sha256'] = '2' * 64
        validation = mod.validate_production_evidence_manifest(evidence)
        self.assertIn('CALENDAR_BINDING_INVALID', validation['blockers'])

    def test_universe_identity_mismatch_is_deterministically_blocked(self):
        evidence = production_evidence()
        evidence['universe_sha256'] = '3' * 64
        validation = mod.validate_production_evidence_manifest(evidence)
        self.assertIn('UNIVERSE_BINDING_INVALID', validation['blockers'])

    def test_raw_artifact_digest_mismatch_is_deterministically_blocked(self):
        evidence = production_evidence()
        evidence['supporting_evidence']['raw_daily_panel']['source_sha256'] = '4' * 64
        validation = mod.validate_production_evidence_manifest(evidence)
        self.assertIn('RAW_PANEL_EVIDENCE_INVALID', validation['blockers'])

    def test_liquidity_artifact_digest_mismatch_is_deterministically_blocked(self):
        evidence = production_evidence()
        evidence['supporting_evidence']['liquidity_contract']['source_sha256'] = '5' * 64
        validation = mod.validate_production_evidence_manifest(evidence)
        self.assertIn('LIQUIDITY_EVIDENCE_INVALID', validation['blockers'])

    def test_repository_manifest_exists_and_matches_contract(self):
        self.assertTrue(EVIDENCE_PATH.exists())
        evidence = json.loads(EVIDENCE_PATH.read_text(encoding='utf-8'))
        self.assertEqual(evidence, production_evidence())
        validation = mod.validate_production_evidence_manifest(evidence)
        self.assertTrue(validation['production_manifest_valid'])


class ProductionReadinessSemanticsTests(unittest.TestCase):
    def test_raw_panel_does_not_satisfy_adjusted_turnover_flow_or_breadth(self):
        report = mod.build_readiness_report(
            load_parameters(), load_factors(), production_evidence())
        for family in (
            'stock_adjusted_close', 'amount_turnover', 'main_net_flow',
            'market_breadth', 'sector_breadth'):
            self.assertFalse(report['feature_families'][family]['formal_feature_ready'])

    def test_qfq_formal_chain_does_not_prove_pit_adjusted_close(self):
        report = mod.build_readiness_report(
            load_parameters(), load_factors(), production_evidence())
        state = report['feature_families']['stock_adjusted_close']
        self.assertEqual(state['binding_state'], 'BOUND_STRUCTURAL_ONLY')
        self.assertEqual(state['pit_state'], 'PIT_UNVERIFIED')
        self.assertFalse(state['formal_feature_ready'])
        self.assertIn('ADJUSTED_CLOSE_PIT_UNVERIFIED', report['blockers'])
        self.assertEqual(report['ready_factor_ids'], [])

    def test_liquidity_is_support_only_and_not_turnover_ratio(self):
        report = mod.build_readiness_report(
            load_parameters(), load_factors(), production_evidence())
        self.assertTrue(report['supporting_evidence']['liquidity_contract']['ready'])
        self.assertFalse(report['feature_families']['amount_turnover']['formal_feature_ready'])
        self.assertIn('TURNOVER_RATIO_UNBOUND', report['blockers'])

    def test_status_remains_incomplete_without_upper_limit_semantics(self):
        report = mod.build_readiness_report(
            load_parameters(), load_factors(), production_evidence())
        state = report['feature_families']['status']
        self.assertEqual(state['pit_state'], 'PIT_PARTIAL')
        self.assertFalse(state['formal_feature_ready'])
        self.assertIn('STATUS_SEMANTICS_INCOMPLETE', report['blockers'])

    def test_production_candidate_scoring_remains_closed(self):
        report = mod.build_readiness_report(
            load_parameters(), load_factors(), production_evidence())
        self.assertEqual(report['validated_families'], ['market_calendar'])
        self.assertFalse(report['candidate_scoring_ready'])
        self.assertFalse(report['real_feature_inputs_validated'])
        self.assertFalse(report['candidate_freeze_ready'])
        self.assertFalse(report['model_freeze_allowed'])
        self.assertFalse(report['oos_metrics_allowed'])


if __name__ == '__main__':
    unittest.main()
