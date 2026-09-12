import io
import unittest

import pandas as pd

import intraday_formal847_inventory_audit_v482 as mod


class IntradayFormal847InventoryAuditV482Tests(unittest.TestCase):
    def test_read_inventory_preserves_leading_zero_stock_codes(self):
        csv_text = (
            'symbol,exchange,file\n'
            '000001,SZ,data/stock_1m/SZ/000001.parquet\n'
            '001201,SZ,data/stock_1m/SZ/001201.parquet\n'
            '002002,SZ,data/stock_1m/SZ/002002.parquet\n'
            '600000,SH,data/stock_1m/SH/600000.parquet\n'
        )
        df = mod.read_inventory_csv(io.StringIO(csv_text))
        self.assertEqual(df['symbol'].tolist(), ['000001', '001201', '002002', '600000'])
        self.assertTrue(pd.api.types.is_string_dtype(df['symbol'].dtype))

    def test_normalization_maps_six_digit_codes_without_losing_exchange(self):
        self.assertEqual(mod.norm_symbol('000001'), '000001.SZ')
        self.assertEqual(mod.norm_symbol('001201'), '001201.SZ')
        self.assertEqual(mod.norm_symbol('002002'), '002002.SZ')
        self.assertEqual(mod.norm_symbol('600000'), '600000.SH')
        self.assertEqual(mod.norm_symbol('000001.XSHE'), '000001.SZ')
        self.assertEqual(mod.norm_symbol('600000.XSHG'), '600000.SH')

    def test_symbol_column_selection_finds_all_formal_symbols_in_string_inventory(self):
        csv_text = (
            'symbol,exchange,file\n'
            '000001,SZ,a\n'
            '001201,SZ,b\n'
            '002002,SZ,c\n'
            '600000,SH,d\n'
        )
        inv = mod.read_inventory_csv(io.StringIO(csv_text))
        formal = {'000001.SZ', '001201.SZ', '002002.SZ', '600000.SH'}
        best_col, inventory_set, stats = mod.select_inventory_symbol_column(inv, formal)
        self.assertEqual(best_col, 'symbol')
        self.assertEqual(inventory_set, formal)
        self.assertEqual(stats[0]['formal847_matches'], 4)


if __name__ == '__main__':
    unittest.main()
