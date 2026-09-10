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

EXPECTED_FLOW_COLS = [
    'dde_l', 'l_net_value', 'net_flow_rate', 'act_buy_xl', 'pas_buy_xl', 'act_sell_xl', 'pas_sell_xl',
    'act_buy_l', 'pas_buy_l', 'act_sell_l', 'pas_sell_l', 'act_buy_m', 'pas_buy_m', 'act_sell_m',
    'pas_sell_m', 'buy_l', 'sell_l',
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

    def test_all_12_factors_have_file_backed_partial_components(self):
        by_name = {x['name']: x for x in self.doc['factors']}
        for name, _ in EXPECTED:
            self.assertEqual(by_name[name]['recovery_status'], 'PARTIAL_FILE_BACKED')
            self.assertTrue(by_name[name]['known_components'])
            self.assertTrue(by_name[name]['missing'])

    def test_matrix_binds_exact_recovered_source_identity(self):
        src = self.doc['daily_base_source']
        self.assertEqual(src['archive_sha256'], 'd526b1341694e14b13ee753200165c0701c3948f984a2e96211bb812f856f03d')
        self.assertEqual(src['run_backtest_sha256'], '6b81feaa37ade4970fcda62601e2a699951fe00ef678ee83fa84f84928d69ff1')
        self.assertEqual(src['run_panel_backtest_sha256'], '62229450e488a75ba4352a239fc762a2b9f48034f765966242632970937278c2')
        self.assertEqual(src['market_breadth_function_sha256'], 'b60d7afcb881bd1903e6cdeb5e80af895e5d337b1094988be110fca9f83d543a')

    def test_fund_flow_adapter_identity_and_columns_are_exact(self):
        src = self.doc['fund_flow_partial_source']
        self.assertEqual(src['archive_sha256'], 'd526b1341694e14b13ee753200165c0701c3948f984a2e96211bb812f856f03d')
        self.assertEqual(src['prepare_ashare21_hf_sha256'], '739e5e24a817283dcd6234e067a73c2ee12b46cb1e13bd9e3857cf864ec3cfe7')
        self.assertEqual(src['flow_columns'], EXPECTED_FLOW_COLS)
        self.assertEqual(len(src['flow_columns']), 17)
        self.assertEqual(src['scope'], 'INPUT_PRESERVATION_ONLY_NOT_FACTOR_FORMULA')
        self.assertFalse(src['factor_formula_recovered'])

    def test_sector_membership_adapter_identity_is_exact_and_pit_remains_unverified(self):
        src = self.doc['sector_membership_partial_source']
        self.assertEqual(src['archive_sha256'], 'd526b1341694e14b13ee753200165c0701c3948f984a2e96211bb812f856f03d')
        self.assertEqual(src['prepare_datalake_silver_sha256'], '4e41c7f0da2de74f3243b3ab433c94c87fe38fc344eb4f87834d898afdbb2175')
        self.assertEqual(src['normalize_silver_sha256'], '913988b740fe64f5bf406e2689afa4ca165dc5959dccbb444a760168f5f1c797')
        self.assertEqual(src['sector_columns'], ['citic_l1', 'citic_l3'])
        self.assertEqual(src['scope'], 'ROW_LEVEL_PASSTHROUGH_ONLY_NOT_PIT_MEMBERSHIP_PROOF')
        self.assertFalse(src['pit_membership_verified'])
        self.assertFalse(src['sector_series_recovered'])
        self.assertFalse(src['factor_formula_recovered'])

    def test_sector_factor_gaps_still_include_pit_and_series_requirements(self):
        by_name = {x['name']: x for x in self.doc['factors']}
        for name in ('Sector RS', 'Sector Slope x R2', 'Sector Breadth'):
            missing = ' '.join(by_name[name]['missing']).lower()
            self.assertIn('pit', missing)
            self.assertIn('sector', missing)

    def test_intraday_source_is_partial_only(self):
        src = self.doc['intraday_source_partial']
        self.assertEqual(src['snapshot_commit_full'], 'f311a5f11569e9d541386982d15f2214d9970b8a')
        self.assertEqual(src['frequency'], '1min')
        self.assertTrue(src['actual_minute_bytes_materialized'])
        self.assertEqual(src['actual_minute_bytes_materialized_scope'], 'SINGLE_SYMBOL_002002_ONLY')
        self.assertFalse(src['formal_15m_coverage_verified'])
        self.assertFalse(src['formal_60m_coverage_verified'])
        self.assertFalse(src['resampling_contract_recovered'])
        self.assertFalse(src['factor_formula_recovered'])


if __name__ == '__main__':
    unittest.main()
