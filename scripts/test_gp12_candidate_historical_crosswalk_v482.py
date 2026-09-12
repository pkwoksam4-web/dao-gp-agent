import json
import pathlib
import unittest


EXPECTED_STATUS = {
    'F1': 'UNVERIFIED_NEW_PROPOSAL',
    'F2': 'PARTIAL_OVERLAP',
    'F3': 'CONFIRMED_IDENTITY_ONLY',
    'F4': 'CONFIRMED_IDENTITY_ONLY',
    'F5': 'CONFIRMED_IDENTITY_ONLY',
    'F6': 'PARTIAL_OVERLAP',
    'F7': 'CONFLICT_WITH_RECOVERED_SOURCE',
    'F8': 'CONFLICT_WITH_RECOVERED_SOURCE',
    'F9': 'PARTIAL_OVERLAP',
    'F10': 'PARTIAL_OVERLAP',
    'F11': 'UNVERIFIED_NEW_PROPOSAL',
    'F12': 'UNVERIFIED_NEW_PROPOSAL',
}


class CandidateHistoricalCrosswalkV482Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = pathlib.Path(__file__).resolve().parents[1] / 'data' / 'GP12_CANDIDATE_HISTORICAL_CROSSWALK_V482.json'
        cls.doc = json.loads(path.read_text(encoding='utf-8'))

    def test_candidate_identity_is_bound_and_remains_unapproved(self):
        self.assertEqual(cls_get(self.doc, 'artifact'), 'GP12_CANDIDATE_HISTORICAL_CROSSWALK_V482')
        self.assertEqual(self.doc['candidate']['strategy_id'], 'GP12_REBUILD_CANDIDATE_V1')
        self.assertEqual(self.doc['candidate']['head_sha'], 'fbba9345fec544b05da6a14f4c2aff43c81d2c95')
        self.assertEqual(self.doc['candidate']['adoption_status'], 'UNAPPROVED')
        self.assertFalse(self.doc['historical_strategy_recovered'])
        self.assertFalse(self.doc['model_freeze_allowed'])
        self.assertFalse(self.doc['oos_metrics_allowed'])

    def test_all_12_candidate_formulas_have_explicit_historical_status(self):
        observed = {x['factor_id']: x['historical_status'] for x in self.doc['factors']}
        self.assertEqual(observed, EXPECTED_STATUS)
        self.assertEqual(len(self.doc['factors']), 12)
        self.assertNotIn('AUTHORITATIVE_FORMULA_RECOVERED', set(observed.values()))

    def test_weight_vector_is_the_only_candidate_parameter_promoted_as_historical(self):
        promoted = self.doc['promoted_from_candidate_package']
        self.assertEqual(promoted, ['factor_names_and_weights_v1_0'])
        self.assertEqual(self.doc['authoritative_weight_vector'], [8, 4, 10, 7, 8, 12, 10, 8, 7, 8, 10, 8])
        self.assertEqual(sum(self.doc['authoritative_weight_vector']), 100)

    def test_new_candidate_policy_is_rejected_as_historical_parameters(self):
        policy = self.doc['candidate_policy_disposition']
        self.assertEqual(policy['historical_status'], 'REJECT_AS_HISTORICAL_PARAMETERS')
        self.assertEqual(policy['entry_score_min'], 60)
        self.assertEqual(policy['exit_score_below'], 45)
        self.assertEqual(policy['top_n'], 10)
        self.assertEqual(policy['max_holding_market_sessions'], 3)
        self.assertEqual(policy['one_way_basis_points'], 10)
        self.assertFalse(policy['freeze_eligible'])

    def test_recovered_source_conflicts_are_specific(self):
        by_id = {x['factor_id']: x for x in self.doc['factors']}
        self.assertIn('r120', by_id['F7']['recovered_source_difference'])
        self.assertIn('raw_strength', by_id['F7']['recovered_source_difference'])
        self.assertIn('slope20', by_id['F8']['recovered_source_difference'])
        self.assertIn('er20', by_id['F8']['recovered_source_difference'])
        self.assertIn('close_loc', by_id['F8']['recovered_source_difference'])


def cls_get(doc, key):
    return doc[key]


if __name__ == '__main__':
    unittest.main()
