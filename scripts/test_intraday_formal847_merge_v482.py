import importlib
import importlib.util
import unittest


class IntradayFormal847MergeV482Tests(unittest.TestCase):
    def _load(self):
        spec = importlib.util.find_spec('intraday_formal847_merge_v482')
        self.assertIsNotNone(spec, 'intraday_formal847_merge_v482 module is missing')
        return importlib.import_module('intraday_formal847_merge_v482')

    def _report(self, idx, symbols, required=10, valid=10, review=0, missing=0, invalid=0):
        return {
            'artifact': 'INTRADAY_FORMAL847_MATERIALIZATION_SHARD_V482',
            'version': 'V4.82',
            'status': 'PASS_SHARD_REQUIRED_DATE_COVERAGE' if review == 0 else 'REVIEW_SHARD_REQUIRED_DATE_COVERAGE',
            'formal_start': '2020-06-01',
            'formal_end': '2026-04-17',
            'dataset': 'neigezhu/china-a-share-1min-ohlcv',
            'snapshot_commit': 'f311a5f11569e9d541386982d15f2214d9970b8a',
            'shard_index': idx,
            'shard_count': 2,
            'symbols_selected': len(symbols),
            'symbol_list': symbols,
            'pass_symbols': len(symbols),
            'expected_zero_trade_symbols': 0,
            'review_symbols': review,
            'required_trade_dates': required,
            'valid_trade_dates': valid,
            'missing_trade_dates': missing,
            'invalid_grid_dates': invalid,
            'source_bytes_downloaded': 1234,
            'bars_15m': {'rows': valid * 16, 'sha256': 'a' * 64, 'bytes': 100},
            'bars_60m': {'rows': valid * 4, 'sha256': 'b' * 64, 'bytes': 50},
            'coverage_csv': {'rows': len(symbols), 'sha256': 'c' * 64, 'bytes': 25},
            'shard_required_date_coverage_verified': review == 0,
            'formal_847_minute_byte_coverage_verified': False,
            'formal_847_15m_coverage_verified': False,
            'formal_847_60m_coverage_verified': False,
            'historical_gp_intraday_resampling_contract_recovered': False,
            'factor_formula_recovered': False,
            'model_freeze_allowed': False,
            'oos_metrics_allowed': False,
        }

    def test_complete_partition_promotes_only_formal_data_coverage(self):
        mod = self._load()
        reports = [
            self._report(0, ['000001.SZ', '600001.SH']),
            self._report(1, ['000002.SZ', '600002.SH']),
        ]
        out = mod.aggregate_reports(reports, expected_shards=2, expected_symbols=4)
        self.assertEqual(out['status'], 'PASS_FORMAL847_INTRADAY_COVERAGE')
        self.assertEqual(out['shards'], 2)
        self.assertEqual(out['symbols'], 4)
        self.assertEqual(out['required_trade_dates'], 20)
        self.assertEqual(out['valid_trade_dates'], 20)
        self.assertTrue(out['formal_847_minute_byte_coverage_verified'])
        self.assertTrue(out['formal_847_15m_coverage_verified'])
        self.assertTrue(out['formal_847_60m_coverage_verified'])
        self.assertFalse(out['historical_gp_intraday_resampling_contract_recovered'])
        self.assertFalse(out['factor_formula_recovered'])
        self.assertFalse(out['model_freeze_allowed'])
        self.assertFalse(out['oos_metrics_allowed'])

    def test_missing_shard_fails_closed(self):
        mod = self._load()
        reports = [self._report(0, ['000001.SZ'])]
        with self.assertRaises(ValueError):
            mod.aggregate_reports(reports, expected_shards=2, expected_symbols=1)

    def test_duplicate_symbol_fails_closed(self):
        mod = self._load()
        reports = [
            self._report(0, ['000001.SZ']),
            self._report(1, ['000001.SZ']),
        ]
        with self.assertRaises(ValueError):
            mod.aggregate_reports(reports, expected_shards=2, expected_symbols=2)

    def test_review_or_missing_required_date_fails_closed(self):
        mod = self._load()
        bad = self._report(0, ['000001.SZ'], required=10, valid=9, review=1, missing=1)
        good = self._report(1, ['000002.SZ'])
        with self.assertRaises(ValueError):
            mod.aggregate_reports([bad, good], expected_shards=2, expected_symbols=2)

    def test_bar_row_mismatch_fails_closed(self):
        mod = self._load()
        a = self._report(0, ['000001.SZ'])
        b = self._report(1, ['000002.SZ'])
        b['bars_15m']['rows'] -= 1
        with self.assertRaises(ValueError):
            mod.aggregate_reports([a, b], expected_shards=2, expected_symbols=2)


if __name__ == '__main__':
    unittest.main()
