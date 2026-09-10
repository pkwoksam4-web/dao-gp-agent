import unittest

import pandas as pd

import intraday_formal847_materialize_v482 as mod
from intraday_minute_materialization_pilot_v482 import resample_day


def make_day(symbol: str, day: str) -> pd.DataFrame:
    d = pd.Timestamp(day)
    times = [d + pd.Timedelta(hours=9, minutes=30)]
    times += list(pd.date_range(d + pd.Timedelta(hours=9, minutes=31), d + pd.Timedelta(hours=11, minutes=30), freq='1min'))
    times += list(pd.date_range(d + pd.Timedelta(hours=13, minutes=1), d + pd.Timedelta(hours=15), freq='1min'))
    n = len(times)
    return pd.DataFrame({
        'symbol': [symbol] * n,
        'timestamp': times,
        'open': [10.0] * n,
        'high': [10.2] * n,
        'low': [9.8] * n,
        'close': [10.1] * n,
        'volume': [100] * n,
        'turnover': [1000.0] * n,
    })


class IntradayFormal847MaterializeV482Tests(unittest.TestCase):
    def test_required_trade_dates_respect_formal_window_and_exact_correction(self):
        pit = pd.DataFrame({
            'symbol': ['002087.SZ'] * 4,
            'date': ['2020-05-29', '2020-06-01', '2024-06-13', '2026-04-18'],
            'tradestatus': [1, 1, 0, 1],
        })
        got = mod.required_trade_dates(pit, '002087.SZ')
        self.assertEqual(got, ['2020-06-01', '2024-06-13'])

    def test_pitst_trade_date_index_prepares_once_with_corrections_and_boundaries(self):
        pit = pd.DataFrame({
            'symbol': ['002087.SZ', '002087.SZ', '002087.SZ', '000001.SZ', '000001.SZ', '600074.SH'],
            'date': ['2020-05-29', '2020-06-01', '2024-06-13', '2026-04-17', '2026-04-18', '2024-01-02'],
            'tradestatus': [1, 1, 0, 1, 1, 0],
        })
        indexed = mod.prepare_required_trade_date_index(pit)
        self.assertEqual(indexed['002087.SZ'], ['2020-06-01', '2024-06-13'])
        self.assertEqual(indexed['000001.SZ'], ['2026-04-17'])
        self.assertNotIn('600074.SH', indexed)
        self.assertNotIn('2026-04-18', indexed['000001.SZ'])

    def test_required_day_index_groups_once_and_ignores_nonrequired_dates(self):
        src = pd.concat([
            make_day('000001', '2024-01-02'),
            make_day('000001', '2024-01-03'),
            make_day('000001', '2024-01-04'),
        ], ignore_index=True)
        src['timestamp'] = pd.to_datetime(src['timestamp'])
        src['_date'] = src['timestamp'].dt.strftime('%Y-%m-%d')
        indexed = mod._index_required_days(src, ['2024-01-02', '2024-01-04'])
        self.assertEqual(sorted(indexed), ['2024-01-02', '2024-01-04'])
        self.assertEqual(len(indexed['2024-01-02']), 241)
        self.assertEqual(len(indexed['2024-01-04']), 241)
        self.assertNotIn('2024-01-03', indexed)

    def test_dual_resample_validates_once_and_matches_legacy_outputs(self):
        day = make_day('000001', '2024-01-02')
        got15, got60 = mod._resample_day_both(day)
        exp15 = resample_day(day, 15)
        exp60 = resample_day(day, 60)
        pd.testing.assert_frame_equal(got15.reset_index(drop=True), exp15.reset_index(drop=True), check_dtype=True)
        pd.testing.assert_frame_equal(got60.reset_index(drop=True), exp60.reset_index(drop=True), check_dtype=True)

    def test_valid_required_days_materialize_exact_15m_60m_counts(self):
        src = pd.concat([make_day('000001', '2024-01-02'), make_day('000001', '2024-01-03')], ignore_index=True)
        bars15, bars60, audit = mod.audit_source_frame(src, ['2024-01-02', '2024-01-03'], '000001.SZ')
        self.assertEqual(audit['status'], 'PASS_REQUIRED_TRADE_DATES_EXACT')
        self.assertEqual(audit['required_trade_dates'], 2)
        self.assertEqual(audit['valid_trade_dates'], 2)
        self.assertEqual(audit['missing_trade_dates'], [])
        self.assertEqual(audit['invalid_grid_dates'], [])
        self.assertEqual(len(bars15), 32)
        self.assertEqual(len(bars60), 8)
        self.assertTrue((bars15['symbol'] == '000001.SZ').all())
        self.assertTrue((bars60['symbol'] == '000001.SZ').all())

    def test_extra_nonrequired_source_dates_do_not_fail(self):
        src = pd.concat([make_day('000001', '2024-01-02'), make_day('000001', '2024-01-03')], ignore_index=True)
        bars15, bars60, audit = mod.audit_source_frame(src, ['2024-01-03'], '000001.SZ')
        self.assertEqual(audit['status'], 'PASS_REQUIRED_TRADE_DATES_EXACT')
        self.assertEqual(audit['required_trade_dates'], 1)
        self.assertEqual(audit['valid_trade_dates'], 1)
        self.assertEqual(len(bars15), 16)
        self.assertEqual(len(bars60), 4)

    def test_missing_required_day_fails_closed_but_keeps_valid_day_evidence(self):
        src = make_day('000001', '2024-01-02')
        bars15, bars60, audit = mod.audit_source_frame(src, ['2024-01-02', '2024-01-03'], '000001.SZ')
        self.assertEqual(audit['status'], 'REVIEW_REQUIRED_TRADE_DATES')
        self.assertEqual(audit['missing_trade_dates'], ['2024-01-03'])
        self.assertEqual(audit['valid_trade_dates'], 1)
        self.assertEqual(len(bars15), 16)
        self.assertEqual(len(bars60), 4)

    def test_bad_required_day_grid_is_reported_and_not_materialized(self):
        src = make_day('000001', '2024-01-02').iloc[:-1].copy()
        bars15, bars60, audit = mod.audit_source_frame(src, ['2024-01-02'], '000001.SZ')
        self.assertEqual(audit['status'], 'REVIEW_REQUIRED_TRADE_DATES')
        self.assertEqual(audit['missing_trade_dates'], [])
        self.assertEqual(audit['valid_trade_dates'], 0)
        self.assertEqual(len(audit['invalid_grid_dates']), 1)
        self.assertTrue(bars15.empty)
        self.assertTrue(bars60.empty)

    def test_zero_trade_symbol_is_explicit_na_not_pass_by_accident(self):
        bars15, bars60, audit = mod.audit_source_frame(pd.DataFrame(), [], '600074.SH')
        self.assertEqual(audit['status'], 'EXPECTED_ZERO_TRADE_NA')
        self.assertEqual(audit['required_trade_dates'], 0)
        self.assertEqual(audit['valid_trade_dates'], 0)
        self.assertTrue(audit['coverage_accounted'])
        self.assertTrue(bars15.empty)
        self.assertTrue(bars60.empty)


if __name__ == '__main__':
    unittest.main()
