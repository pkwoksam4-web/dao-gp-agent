import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class StrategyIntradayInventoryBindingV482Tests(unittest.TestCase):
    def test_source_recovery_binds_formal847_inventory_without_promoting_byte_coverage(self):
        doc = json.loads((ROOT / 'data' / 'GP_V11_INTRADAY_SOURCE_RECOVERY_V482.json').read_text(encoding='utf-8'))
        inv = doc['formal847_inventory_audit']
        self.assertEqual(inv['audit_artifact'], 'INTRADAY_FORMAL847_INVENTORY_AUDIT_V482')
        self.assertEqual(inv['audit_sha256'], '25593756ef0b625c9995e1816f1e5e8d64eaa184256313acc35425b1e7c8ae83')
        self.assertEqual(inv['inventory_map_sha256'], 'bb637ac1db53c3546fba072227832799b84487187840e6421f5ba29319b68aed')
        self.assertEqual(inv['formal_symbols_sha256'], '9e64e111c5eeff1f43fcce6e920d7e5590aa5bb14268c482bbdfe1a936affef8')
        self.assertEqual(inv['source_snapshot_commit'], 'f311a5f11569e9d541386982d15f2214d9970b8a')
        self.assertEqual(inv['source_inventory_sha256'], '31a058c1019e1b097d99e862db68a028ec9d191adb09839c35365f4cb390dc32')
        self.assertEqual(inv['formal_universe_symbols'], 847)
        self.assertEqual(inv['matched_inventory_symbols'], 847)
        self.assertEqual(inv['missing_inventory_symbols'], 0)
        self.assertTrue(inv['formal_847_minute_inventory_membership_verified'])
        self.assertFalse(inv['formal_847_minute_byte_coverage_verified'])
        self.assertFalse(inv['formal_847_15m_coverage_verified'])
        self.assertFalse(inv['formal_847_60m_coverage_verified'])

        self.assertTrue(doc['formal_847_minute_inventory_membership_verified'])
        self.assertFalse(doc['formal_847_minute_byte_coverage_verified'])
        self.assertFalse(doc['formal_847_15m_coverage_verified'])
        self.assertFalse(doc['formal_847_60m_coverage_verified'])
        self.assertFalse(doc['model_freeze_allowed'])
        self.assertFalse(doc['oos_metrics_allowed'])

    def test_factor_matrix_binds_inventory_membership_only(self):
        matrix = json.loads((ROOT / 'data' / 'GP_V11_FACTOR_RECOVERY_MATRIX_V482.json').read_text(encoding='utf-8'))
        src = matrix['intraday_source_partial']
        self.assertTrue(src['formal_847_inventory_membership_verified'])
        self.assertEqual(src['formal_847_inventory_audit_sha256'], '25593756ef0b625c9995e1816f1e5e8d64eaa184256313acc35425b1e7c8ae83')
        self.assertEqual(src['formal_847_inventory_map_sha256'], 'bb637ac1db53c3546fba072227832799b84487187840e6421f5ba29319b68aed')
        self.assertEqual(src['formal_847_inventory_symbols'], 847)
        self.assertFalse(src['formal_847_minute_byte_coverage_verified'])
        self.assertFalse(src['formal_15m_coverage_verified'])
        self.assertFalse(src['formal_60m_coverage_verified'])
        self.assertFalse(src['resampling_contract_recovered'])
        self.assertFalse(src['factor_formula_recovered'])
        intraday = {x['name']: x for x in matrix['factors']}['Intraday Confirmation']
        known = ' '.join(intraday['known_components']).lower()
        missing = ' '.join(intraday['missing']).lower()
        self.assertIn('847', known)
        self.assertIn('byte', missing)
        self.assertIn('15', missing)
        self.assertIn('60', missing)
        self.assertIn('formula', missing)
        self.assertFalse(matrix['model_freeze_allowed'])
        self.assertFalse(matrix['oos_metrics_allowed'])


if __name__ == '__main__':
    unittest.main()
