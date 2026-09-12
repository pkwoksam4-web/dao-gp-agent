import json
import pathlib
import unittest


class StrategyPolicyRecoveryMatrixV482Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = pathlib.Path(__file__).resolve().parents[1] / 'data' / 'GP_V11_DECISION_POLICY_RECOVERY_MATRIX_V482.json'
        cls.doc = json.loads(path.read_text(encoding='utf-8'))

    def test_daily_base_probability_calibration_is_file_backed_but_not_full_gp12_mapping(self):
        self.assertEqual(self.doc['artifact'], 'GP_V11_DECISION_POLICY_RECOVERY_MATRIX_V482')
        src = self.doc['daily_base_probability_source']
        self.assertEqual(src['archive_sha256'], 'd526b1341694e14b13ee753200165c0701c3948f984a2e96211bb812f856f03d')
        self.assertEqual(src['run_panel_backtest_sha256'], '62229450e488a75ba4352a239fc762a2b9f48034f765966242632970937278c2')
        self.assertEqual(src['make_edges_sha256'], 'e0202d76f5a4aae98bf6c4877316dfba3a4313187e3bf2cc6fbb55be268ce8a4')
        self.assertEqual(src['calibrate_fold_sha256'], 'fc989c4de8b792bcb97644342f17ca770f3edef737a0f969b9709186bac5f1ef')
        self.assertEqual(src['walk_forward_panel_sha256'], '80a2af8f9a4ceb95691b52bd58f409b24f768c70ba4f66ba28b1acabe67e3a48')
        self.assertEqual(src['minimum_train_market_days'], 720)
        self.assertEqual(src['step_market_days'], 63)
        self.assertEqual(src['default_quantile_bins'], 10)
        self.assertEqual(src['shrinkage_equivalent_rows'], 20)
        self.assertTrue(src['target_specific_purge'])
        self.assertFalse(src['full_gp12_probability_mapping_recovered'])

    def test_recovered_probability_targets_are_exact_daily_base_targets(self):
        self.assertEqual(
            self.doc['daily_base_probability_source']['targets'],
            ['up_close_1', 'up_close_2', 'up_close_3', 'hit_up2_3d', 'hit_up4_3d', 'hit_dn2_3d'],
        )
        prob = next(x for x in self.doc['components'] if x['component'] == 'probability_mapping')
        self.assertEqual(prob['recovery_status'], 'PARTIAL_FILE_BACKED')
        self.assertIn('binary target probabilities', prob['known'])
        self.assertIn('P-up/P-range/P-down', prob['missing'])

    def test_candidate_policy_values_remain_rejected_as_historical(self):
        rejected = self.doc['rejected_candidate_policy_values']
        self.assertEqual(rejected['entry_score_min'], 60)
        self.assertEqual(rejected['exit_score_below'], 45)
        self.assertEqual(rejected['top_n'], 10)
        self.assertEqual(rejected['max_holding_market_sessions'], 3)
        self.assertEqual(rejected['one_way_basis_points'], 10)
        self.assertEqual(rejected['historical_status'], 'REJECT_AS_HISTORICAL_PARAMETERS')
        self.assertFalse(rejected['freeze_eligible'])

    def test_missing_policy_components_cannot_be_inferred_from_forecast_horizons(self):
        by_name = {x['component']: x for x in self.doc['components']}
        self.assertEqual(by_name['ranking_topn']['recovery_status'], 'MISSING')
        self.assertEqual(by_name['entry_exit_thresholds']['recovery_status'], 'MISSING')
        self.assertEqual(by_name['holding_rebalance_policy']['recovery_status'], 'MISSING')
        self.assertEqual(by_name['position_sizing_risk']['recovery_status'], 'MISSING')
        self.assertIn('forecast horizons are not a holding policy', by_name['holding_rebalance_policy']['missing'])

    def test_execution_diagnostics_are_partial_not_fill_rules(self):
        x = next(x for x in self.doc['components'] if x['component'] == 'execution_diagnostics')
        self.assertEqual(x['recovery_status'], 'PARTIAL_FILE_BACKED')
        self.assertIn('exact-horizon executable masks', x['known'])
        self.assertIn('actual fill-price mechanics', x['missing'])

    def test_freeze_and_oos_remain_closed(self):
        self.assertFalse(self.doc['full_parameter_set_recovered'])
        self.assertFalse(self.doc['full_strategy_probability_mapping_recovered'])
        self.assertFalse(self.doc['model_freeze_allowed'])
        self.assertFalse(self.doc['oos_metrics_allowed'])


if __name__ == '__main__':
    unittest.main()
