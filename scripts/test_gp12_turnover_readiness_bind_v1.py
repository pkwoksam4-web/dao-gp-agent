import copy
import json
import pathlib
import unittest

import gp12_formal_input_readiness_v1 as readiness_mod
import gp12_turnover_formal_v1 as turnover_mod
import gp12_turnover_readiness_bind_v1 as mod


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_json(name):
    return json.loads((ROOT / 'data' / name).read_text(encoding='utf-8'))


def parent_evidence():
    return load_json('GP12_FORMAL_INPUT_EVIDENCE_V1.json')


def candidate_parameters():
    return load_json('GP12_CANDIDATE_PARAMETERS_V1.json')


def candidate_factors():
    return load_json('GP12_CANDIDATE_FACTORS_V1.json')


def passing_turnover():
    return {
        'artifact': 'GP12_TURNOVER_FORMAL_V1',
        'version': '1.0',
        'strategy_id': 'GP12_REBUILD_CANDIDATE_V1',
        'formal_start': '2020-06-01',
        'formal_end': '2026-04-17',
        'formal_artifact_sha256': 'e642481399a05635d07b1baa39f57d3aa84dfd1c18e315edd927ec42da553796',
        'formal_calendar_sha256': '5a872a47cf7a338cc48aa628b8de46053fddc3ed161a2617550199d0607efae7',
        'universe_sha256': 'dfe5c75692d38e5fde7cd5c32eb2ed090a8ab6dffcfd41d5ebda07dc2d6d96fb',
        'candidate_parameters_sha256': '22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204',
        'candidate_factors_sha256': 'b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e',
        'raw_volume_source_artifact': 'gp-sohu-full-raw-v482-reaudit',
        'raw_volume_source_sha256': 'cee7e91f1fda605f7c3bdf41c3f4a7796feeae83f8c3702e50900e6af3fa9550',
        'share_manifest_sha256': 'a' * 64,
        'turnover_rows_sha256': 'b' * 64,
        'symbol_n': 847,
        'expected_trade_rows': 1_011_607,
        'materialized_trade_rows': 1_011_607,
        'duplicate_row_n': 0,
        'missing_turnover_row_n': 0,
        'extra_turnover_row_n': 0,
        'nonpositive_volume_n': 0,
        'nonpositive_outstanding_share_n': 0,
        'nonfinite_turnover_n': 0,
        'future_share_record_violation_n': 0,
        'unresolved_prior_share_record_n': 0,
        'pit_state': 'PIT_VERIFIED',
        'status': 'PASS_FORMAL_TURNOVER_V1',
        'blockers': [],
        'formal_feature_ready': True,
        'candidate_freeze_ready': False,
        'model_freeze_allowed': False,
        'oos_metrics_allowed': False,
    }


def blocked_turnover():
    out = passing_turnover()
    out['status'] = 'BLOCKED_FORMAL_TURNOVER_V1'
    out['formal_feature_ready'] = False
    out['pit_state'] = 'PIT_UNVERIFIED'
    out['blockers'] = ['SINA_SHARE_DATE_SEMANTICS_UNVERIFIED']
    return out


class TurnoverReadinessBindV1Tests(unittest.TestCase):
    def test_blocked_turnover_does_not_modify_parent_evidence(self):
        before = parent_evidence()
        out = mod.bind_turnover(before, blocked_turnover())
        self.assertEqual(out, before)
        self.assertIsNot(out, before)

    def test_pass_changes_only_amount_turnover(self):
        before = parent_evidence()
        after = mod.bind_turnover(before, passing_turnover())
        self.assertEqual(after['supporting_evidence'], before['supporting_evidence'])
        for name in before['feature_families']:
            if name != 'amount_turnover':
                self.assertEqual(after['feature_families'][name], before['feature_families'][name])
        family = after['feature_families']['amount_turnover']
        self.assertEqual(family['binding_state'], 'BOUND_VERIFIED_ARTIFACT')
        self.assertEqual(family['pit_state'], 'PIT_VERIFIED')
        self.assertEqual(family['source_artifact'], 'GP12_TURNOVER_FORMAL_V1')
        self.assertEqual(family['source_sha256'], turnover_mod.canonical_json_sha256(passing_turnover()))
        self.assertEqual(family['coverage_start'], '2020-06-01')
        self.assertEqual(family['coverage_end'], '2026-04-17')
        self.assertEqual(family['blockers'], [])

    def test_main_net_flow_and_adjusted_close_blockers_remain(self):
        evidence = mod.bind_turnover(parent_evidence(), passing_turnover())
        report = readiness_mod.build_readiness_report(
            candidate_parameters(), candidate_factors(), evidence)
        self.assertNotIn('TURNOVER_RATIO_UNBOUND', report['blockers'])
        self.assertIn('MAIN_NET_FLOW_UNBOUND', report['blockers'])
        self.assertIn('ADJUSTED_CLOSE_PIT_UNVERIFIED', report['blockers'])
        self.assertIn('F11', report['blocked_factor_ids'])
        self.assertFalse(report['candidate_scoring_ready'])
        self.assertFalse(report['model_freeze_allowed'])
        self.assertFalse(report['oos_metrics_allowed'])

    def test_identity_mismatch_cannot_modify_parent(self):
        bad = passing_turnover()
        bad['raw_volume_source_sha256'] = '0' * 64
        before = parent_evidence()
        out = mod.bind_turnover(before, bad)
        self.assertEqual(out, before)

    def test_non_pit_pass_cannot_modify_parent(self):
        bad = passing_turnover()
        bad['pit_state'] = 'PIT_UNVERIFIED'
        before = parent_evidence()
        self.assertEqual(mod.bind_turnover(before, bad), before)

    def test_false_feature_ready_cannot_modify_parent(self):
        bad = passing_turnover()
        bad['formal_feature_ready'] = False
        before = parent_evidence()
        self.assertEqual(mod.bind_turnover(before, bad), before)

    def test_parent_input_is_not_mutated(self):
        before = parent_evidence()
        snapshot = copy.deepcopy(before)
        mod.bind_turnover(before, passing_turnover())
        self.assertEqual(before, snapshot)


if __name__ == '__main__':
    unittest.main()
