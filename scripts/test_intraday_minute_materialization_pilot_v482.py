import importlib
import unittest
from datetime import datetime, timedelta

import pandas as pd


class IntradayMinuteMaterializationPilotV482Tests(unittest.TestCase):
    def load_module(self):
        try:
            return importlib.import_module('intraday_minute_materialization_pilot_v482')
        except ModuleNotFoundError:
            self.fail('intraday_minute_materialization_pilot_v482 module is missing')

    @staticmethod
    def synthetic_day(date='2024-01-02'):
        day = pd.Timestamp(date)
        stamps = [day + pd.Timedelta(hours=9, minutes=30)]
        stamps += list(pd.date_range(day + pd.Timedelta(hours=9, minutes=31), day + pd.Timedelta(hours=11, minutes=30), freq='1min'))
        stamps += list(pd.date_range(day + pd.Timedelta(hours=13, minutes=1), day + pd.Timedelta(hours=15), freq='1min'))
        n = len(stamps)
        return pd.DataFrame({
            'symbol': ['002002'] * n,
            'timestamp': stamps,
            'open': [100.0 + i for i in range(n)],
            'high': [100.5 + i for i in range(n)],
            'low': [99.5 + i for i in range(n)],
            'close': [100.25 + i for i in range(n)],
            'volume': [1] * n,
            'turnover': [10.0] * n,
        })

    def test_exact_source_day_contract_excludes_only_0930_opening_marker(self):
        mod = self.load_module()
        day = self.synthetic_day()
        continuous, marker = mod.split_and_validate_day(day)
        self.assertEqual(len(day), 241)
        self.assertEqual(len(marker), 1)
        self.assertEqual(str(marker.iloc[0]['timestamp'].time()), '09:30:00')
        self.assertEqual(len(continuous), 240)
        self.assertEqual(str(continuous.iloc[0]['timestamp'].time()), '09:31:00')
        self.assertEqual(str(continuous.iloc[119]['timestamp'].time()), '11:30:00')
        self.assertEqual(str(continuous.iloc[120]['timestamp'].time()), '13:01:00')
        self.assertEqual(str(continuous.iloc[-1]['timestamp'].time()), '15:00:00')

    def test_15m_resample_is_16_bars_and_never_crosses_lunch(self):
        mod = self.load_module()
        bars = mod.resample_day(self.synthetic_day(), 15)
        self.assertEqual(len(bars), 16)
        self.assertEqual(str(bars.iloc[0]['source_start'].time()), '09:31:00')
        self.assertEqual(str(bars.iloc[0]['bar_end'].time()), '09:45:00')
        self.assertEqual(str(bars.iloc[7]['source_start'].time()), '11:16:00')
        self.assertEqual(str(bars.iloc[7]['bar_end'].time()), '11:30:00')
        self.assertEqual(str(bars.iloc[8]['source_start'].time()), '13:01:00')
        self.assertEqual(str(bars.iloc[8]['bar_end'].time()), '13:15:00')
        self.assertTrue((bars['source_rows'] == 15).all())
        self.assertTrue(((bars['session'] == 'AM') | (bars['session'] == 'PM')).all())
        self.assertEqual(int(bars['volume'].sum()), 240)

    def test_60m_resample_is_4_bars_with_correct_ohlcv_aggregation(self):
        mod = self.load_module()
        bars = mod.resample_day(self.synthetic_day(), 60)
        self.assertEqual(len(bars), 4)
        first = bars.iloc[0]
        self.assertEqual(str(first['source_start'].time()), '09:31:00')
        self.assertEqual(str(first['bar_end'].time()), '10:30:00')
        self.assertEqual(first['open'], 101.0)
        self.assertEqual(first['high'], 160.5)
        self.assertEqual(first['low'], 100.5)
        self.assertEqual(first['close'], 160.25)
        self.assertEqual(int(first['volume']), 60)
        self.assertEqual(float(first['turnover']), 600.0)
        self.assertTrue((bars['source_rows'] == 60).all())

    def test_missing_continuous_minute_fails_closed(self):
        mod = self.load_module()
        day = self.synthetic_day()
        broken = day[day['timestamp'] != pd.Timestamp('2024-01-02 10:00:00')].copy()
        with self.assertRaisesRegex(ValueError, 'continuous session minute grid mismatch'):
            mod.resample_day(broken, 15)

    def test_duplicate_timestamp_fails_closed(self):
        mod = self.load_module()
        day = self.synthetic_day()
        dup = pd.concat([day, day.iloc[[10]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, 'duplicate timestamp'):
            mod.resample_day(dup, 60)

    def test_unsupported_interval_fails_closed(self):
        mod = self.load_module()
        with self.assertRaisesRegex(ValueError, 'interval_minutes must be 15 or 60'):
            mod.resample_day(self.synthetic_day(), 30)


if __name__ == '__main__':
    unittest.main()
