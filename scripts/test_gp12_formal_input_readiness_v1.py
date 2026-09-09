from __future__ import annotations

import copy
import json
import pathlib
import unittest

import gp12_formal_input_readiness_v1 as mod


ROOT = pathlib.Path(__file__).resolve().parents[1]
PARAMETERS_PATH = ROOT / 'data' / 'GP12_CANDIDATE_PARAMETERS_V1.json'
FACTORS_PATH = ROOT / 'data' / 'GP12_CANDIDATE_FACTORS_V1.json'

PARAMETERS_SHA256 = '22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204'
FACTORS_SHA256 = 'b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e'
FORMAL_SHA256 = 'e642481399a05635d07b1baa39f57d3aa84dfd1c18e315edd927ec42da553796'
CALENDAR_SHA256 = '5a872a47cf7a338cc48aa628b8de46053fddc3ed161a2617550199d0607efae7'
UNIVERSE_SHA256 = 'dfe5c75692d38e5fde7cd5c32eb2ed090a8ab6dffcfd41d5ebda07dc2d6d96fb'

FEATURE_FAMILIES = (
    'market_calendar',
    'stock_adjusted_close',
    'market_adjusted_close',
    'sector_adjusted_close',
    'amount_turnover',
    'main_net_flow',
    'market_breadth',
    'sector_breadth',
    'status',
    'intraday_15m',
    'intraday_60m',
)


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


def minimal_evidence():
    families = {
        'market_calendar': {
            'binding_state': 'BOUND_VERIFIED_ARTIFACT',
            'pit_state': 'PIT_VERIFIED',
            'source_artifact': 'OFFICIAL_A_SHARE_OPEN_DATES_V357',
            'source_sha256': CALENDAR_SHA256,
            'coverage_start': '2020-06-01',
            'coverage_end': '2026-04-17',
            'blockers': [],
        },
        'stock_adjusted_close': unbound_family('ADJUSTED_CLOSE_PIT_UNVERIFIED'),
        'market_adjusted_close': unbound_family('MARKET_BENCHMARK_UNBOUND'),
        'sector_adjusted_close': unbound_family('SECTOR_SERIES_UNBOUND'),
        'amount_turnover': unbound_family('TURNOVER_RATIO_UNBOUND'),
        'main_net_flow': unbound_family('MAIN_NET_FLOW_UNBOUND'),
        'market_breadth': unbound_family('MARKET_BREADTH_UNBOUND'),
        'sector_breadth': unbound_family('SECTOR_BREADTH_UNBOUND'),
        'status': unbound_family('STATUS_SEMANTICS_INCOMPLETE'),
        'intraday_15m': unbound_family('INTRADAY_15M_UNBOUND'),
        'intraday_60m': unbound_family('INTRADAY_60M_UNBOUND'),
    }
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
                'source_artifact': 'SOHU_RAW_FULL_V482',
                'source_sha256': 'a' * 64,
                'ready': True,
                'blockers': [],
            },
            'liquidity_contract': {
                'binding_state': 'BOUND_VERIFIED_ARTIFACT',
                'pit_state': 'PIT_VERIFIED',
                'source_artifact': 'LIQUIDITY_80M_APPLY_V482',
                'source_sha256': 'b' * 64,
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
        'feature_families': families,
    }


class FormalInputReadinessIdentityTests(unittest.TestCase):
    def test_exact_candidate_package_identity_is_accepted(self):
        report = mod.build_readiness_report(
            load_parameters(), load_factors(), minimal_evidence())
        self.assertEqual(report['candidate_parameters_sha256'], PARAMETERS_SHA256)
        self.assertEqual(report['candidate_factors_sha256'], FACTORS_SHA256)
        self.assertEqual(report['strategy_id'], 'GP12_REBUILD_CANDIDATE_V1')
        self.assertEqual(report['formal_end'], '2026-04-17')

    def test_candidate_parameter_tampering_is_rejected(self):
        parameters = load_parameters()
        parameters['policy']['top_n'] = 11
        with self.assertRaises(ValueError):
            mod.build_readiness_report(parameters, load_factors(), minimal_evidence())

    def test_candidate_factor_tampering_is_rejected(self):
        factors = load_factors()
        factors['factors'][0]['formula_version'] = '9.9'
        with self.assertRaises(ValueError):
            mod.build_readiness_report(load_parameters(), factors, minimal_evidence())

    def test_recursive_oos_or_performance_field_is_rejected(self):
        evidence = minimal_evidence()
        evidence['supporting_evidence']['raw_daily_panel']['nested'] = {
            'sharpe': 1.2,
        }
        with self.assertRaises(ValueError):
            mod.build_readiness_report(load_parameters(), load_factors(), evidence)

    def test_unknown_top_level_evidence_field_is_rejected(self):
        evidence = minimal_evidence()
        evidence['mystery'] = True
        with self.assertRaises(ValueError):
            mod.build_readiness_report(load_parameters(), load_factors(), evidence)


class FormalInputReadinessFamilyStateTests(unittest.TestCase):
    def test_structural_source_is_not_formal_feature_ready(self):
        evidence = minimal_evidence()
        evidence['feature_families']['main_net_flow'] = {
            'binding_state': 'BOUND_STRUCTURAL_ONLY',
            'pit_state': 'PIT_UNVERIFIED',
            'source_artifact': 'eastmoney-probe',
            'source_sha256': 'c' * 64,
            'coverage_start': '2020-06-01',
            'coverage_end': '2026-04-17',
            'blockers': [],
        }
        report = mod.build_readiness_report(load_parameters(), load_factors(), evidence)
        self.assertFalse(
            report['feature_families']['main_net_flow']['formal_feature_ready'])

    def test_verified_and_pit_verified_family_is_ready(self):
        report = mod.build_readiness_report(
            load_parameters(), load_factors(), minimal_evidence())
        self.assertTrue(
            report['feature_families']['market_calendar']['formal_feature_ready'])

    def test_family_coverage_may_not_extend_past_formal_end(self):
        evidence = minimal_evidence()
        evidence['feature_families']['market_calendar']['coverage_end'] = '2026-04-20'
        with self.assertRaises(ValueError):
            mod.build_readiness_report(load_parameters(), load_factors(), evidence)

    def test_invalid_sha_is_rejected(self):
        evidence = minimal_evidence()
        evidence['feature_families']['market_calendar']['source_sha256'] = 'not-a-sha'
        with self.assertRaises(ValueError):
            mod.build_readiness_report(load_parameters(), load_factors(), evidence)

    def test_duplicate_blockers_are_normalized_sorted_unique(self):
        evidence = minimal_evidence()
        evidence['feature_families']['main_net_flow']['blockers'] = [
            'MAIN_NET_FLOW_UNBOUND', 'A_BLOCKER', 'MAIN_NET_FLOW_UNBOUND']
        report = mod.build_readiness_report(load_parameters(), load_factors(), evidence)
        self.assertEqual(
            report['feature_families']['main_net_flow']['blockers'],
            ['A_BLOCKER', 'MAIN_NET_FLOW_UNBOUND'])

    def test_scorer_family_cannot_be_not_directly_required(self):
        evidence = minimal_evidence()
        evidence['feature_families']['main_net_flow']['binding_state'] = 'NOT_DIRECTLY_REQUIRED'
        with self.assertRaises(ValueError):
            mod.build_readiness_report(load_parameters(), load_factors(), evidence)

    def test_v1_never_approves_or_opens_model_freeze_or_oos(self):
        report = mod.build_readiness_report(
            load_parameters(), load_factors(), minimal_evidence())
        self.assertEqual(report['candidate_adoption_status'], 'UNAPPROVED')
        self.assertFalse(report['candidate_freeze_ready'])
        self.assertFalse(report['model_freeze_allowed'])
        self.assertFalse(report['oos_metrics_allowed'])

    def test_all_required_feature_families_are_reported(self):
        report = mod.build_readiness_report(
            load_parameters(), load_factors(), minimal_evidence())
        self.assertEqual(set(report['feature_families']), set(FEATURE_FAMILIES))


if __name__ == '__main__':
    unittest.main()
