import hashlib
import json
import pathlib
import unittest

import pandas as pd


ROOT = pathlib.Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'data' / 'INTRADAY_FORMAL847_INVENTORY_AUDIT_V482.json'
MAP = ROOT / 'data' / 'FORMAL847_NEIGEZHU_INVENTORY_ROWS_V482.csv'
SYMBOLS = ROOT / 'data' / 'FORMAL847_SYMBOLS_V482.txt'


class IntradayFormal847InventoryEvidenceV482Tests(unittest.TestCase):
    def test_audit_identity_and_membership_are_exact(self):
        raw = AUDIT.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), '25593756ef0b625c9995e1816f1e5e8d64eaa184256313acc35425b1e7c8ae83')
        doc = json.loads(raw.decode('utf-8'))
        self.assertEqual(doc['artifact'], 'INTRADAY_FORMAL847_INVENTORY_AUDIT_V482')
        self.assertEqual(doc['version'], 'V4.82')
        self.assertEqual(doc['status'], 'INVENTORY_ONLY_NOT_BYTE_COVERAGE')
        formal = doc['formal_raw']
        self.assertEqual(formal['sha256'], 'bc72238d046378cf3b6fa61723e86fb43f1c491ac3da86d76932e3185f60e1eb')
        self.assertEqual(formal['raw_row_level_symbols'], 844)
        self.assertEqual(formal['expected_zero_trade_symbols'], ['600074.SH', '600485.SH', '600677.SH'])
        self.assertEqual(formal['formal_universe_symbols'], 847)
        inv = doc['minute_inventory']
        self.assertEqual(inv['snapshot_commit'], 'f311a5f11569e9d541386982d15f2214d9970b8a')
        self.assertEqual(inv['sha256'], '31a058c1019e1b097d99e862db68a028ec9d191adb09839c35365f4cb390dc32')
        self.assertEqual(inv['rows'], 5795)
        self.assertEqual(inv['selected_symbol_column'], 'symbol')
        self.assertTrue(inv['symbol_dtype_preserved_as_string'])
        inter = doc['formal847_inventory_intersection']
        self.assertEqual(inter['matched_symbols'], 847)
        self.assertEqual(inter['missing_symbols'], 0)
        self.assertEqual(inter['missing_symbol_list'], [])
        self.assertTrue(doc['formal_847_minute_inventory_membership_verified'])
        self.assertFalse(doc['formal_847_minute_byte_coverage_verified'])
        self.assertFalse(doc['formal_847_15m_coverage_verified'])
        self.assertFalse(doc['formal_847_60m_coverage_verified'])
        self.assertFalse(doc['historical_gp_resampling_contract_recovered'])
        self.assertFalse(doc['factor_formula_recovered'])
        self.assertFalse(doc['model_freeze_allowed'])
        self.assertFalse(doc['oos_metrics_allowed'])

    def test_inventory_map_is_exactly_847_unique_symbols(self):
        raw = MAP.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), 'bb637ac1db53c3546fba072227832799b84487187840e6421f5ba29319b68aed')
        df = pd.read_csv(MAP, dtype='string', keep_default_na=False)
        self.assertEqual(len(df), 847)
        self.assertEqual(df['_norm_symbol'].nunique(), 847)
        self.assertEqual(set(df['_norm_symbol']), set(SYMBOLS.read_text(encoding='utf-8').splitlines()))
        self.assertTrue(df['file'].str.startswith('data/stock_1m/').all())
        self.assertTrue(df['file'].str.endswith('.parquet').all())

    def test_formal_symbol_set_identity_is_exact(self):
        raw = SYMBOLS.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), '9e64e111c5eeff1f43fcce6e920d7e5590aa5bb14268c482bbdfe1a936affef8')
        symbols = raw.decode('utf-8').splitlines()
        self.assertEqual(len(symbols), 847)
        self.assertEqual(len(set(symbols)), 847)
        self.assertEqual(set(['600074.SH', '600485.SH', '600677.SH']) & set(symbols), {'600074.SH', '600485.SH', '600677.SH'})


if __name__ == '__main__':
    unittest.main()
