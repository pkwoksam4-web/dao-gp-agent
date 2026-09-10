import json
import pathlib
import unittest


EXPECTED = [
    ('Market Regime', 8),
    ('Market Breadth/Diffusion', 4),
    ('Sector RS', 10),
    ('Sector Slope x R2', 7),
    ('Sector Breadth', 8),
    ('Position', 12),
    ('Multi-Momentum', 10),
    ('Trend Quality', 8),
    ('Efficiency Ratio', 7),
    ('Drawdown Recovery', 8),
    ('Price/Fund Efficiency', 10),
    ('Intraday Confirmation', 8),
]


class FactorRecoveryMatrixV482Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = pathlib.Path(__file__).resolve().parents[1] / 'data' / 'GP_V11_FACTOR_RECOVERY_MATRIX_V482.json'
        cls.doc = json.loads(path.read_text(encoding='utf-8'))

    def test_exact_frozen_factor_library_and_weights(self):
        self.assertEqual(self.doc['artifact'], 'GP_V11_FACTOR_RECOVERY_MATRIX_V482')
        self.assertEqual(self.doc['version'], 'V4.82')
        self.assertEqual(self.doc['factor_library_version'], 'V1.0')
        observed = [(x['name'], x['weight_pct']) for x in self.doc['factors']]
        self.assertEqual(observed, EXPECTED)
        self.assertEqual(sum(w for _, w in observed), 100)
        self.assertTrue(self.doc['authoritative_weight_vector_recovered'])

    def test_no_partial_component_can_be_called_complete(self):
        allowed = {'PARTIAL_FILE_BACKED', 'USER_CONFIRMED_DEFINITION_ONLY', 'MISSING'}
        self.assertTrue(all(x['recovery_status'] in allowed for x in self.doc['factors']))
        self.assertFalse(any(x['recovery_status'] == 'COMPLETE' for x in self.doc['factors']))
        self.assertFalse(self.doc['complete_factor_definitions_recovered'])
        self.assertFalse(self.doc['full_strategy_source_recovered'])
        self.assertFalse(self.doc['model_freeze_allowed'])
        self.assertFalse(self.doc['oos_metrics_allowed'])

    def test_daily_source_components_are_explicit_and_non_daily_gaps_remain(self):
        by_name = {x['name']: x for x in self.doc['factors']}
        for name in ('Market Regime', 'Market Breadth/Diffusion', 'Position', 'Multi-Momentum', 'Trend Quality', 'Efficiency Ratio', 'Drawdown Recovery'):
            self.assertEqual(by_name[name]['recovery_status'], 'PARTIAL_FILE_BACKED')
            self.assertTrue(by_name[name]['known_components'])
            self.assertTrue(by_name[name]['missing'])
        for name in ('Sector RS', 'Sector Slope x R2', 'Sector Breadth', 'Price/Fund Efficiency', 'Intraday Confirmation'):
            self.assertIn(by_name[name]['recovery_status'], {'USER_CONFIRMED_DEFINITION_ONLY', 'MISSING'})
            self.assertTrue(by_name[name]['missing'])

    def test_matrix_binds_exact_recovered_source_identity(self):
        src = self.doc['daily_base_source']
        self.assertEqual(src['archive_sha256'], 'd526b1341694e14b13ee753200165c0701c3948f984a2e96211bb812f856f03d')
        self.assertEqual(src['run_backtest_sha256'], '6b81feaa37ade4970fcda62601e2a699951fe00ef678ee83fa84f84928d69ff1')
        self.assertEqual(src['run_panel_backtest_sha256'], '62229450e488a75ba4352a239fc762a2b9f48034f765966242632970937278c2')
        self.assertEqual(src['market_breadth_function_sha256'], 'b60d7afcb881bd1903e6cdeb5e80af895e5d337b1094988be110fca9f83d543a')


if __name__ == '__main__':
    unittest.main()
