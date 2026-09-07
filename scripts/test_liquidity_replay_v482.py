import unittest
import pandas as pd

import liquidity_replay_v482 as m


class LiquidityReplayTests(unittest.TestCase):
    def test_market_day_zero_variant_allows_four_nontraded_days(self):
        dates=pd.date_range('2026-01-01', periods=20, freq='D')
        x=pd.DataFrame({'date':dates,'amount':[100_000_000.0]*20,'traded':[True]*20})
        for i in (2,6,10,14):
            x.loc[i,'amount']=0.0; x.loc[i,'traded']=False
        out=m.evaluate_one_calendar_series(x,80_000_000.0,'market_day_zero',min_actual_before=1)
        self.assertTrue(bool(out.iloc[-1]['eligible']))
        self.assertEqual(float(out.iloc[-1]['trade_density20']),0.8)
        self.assertEqual(float(out.iloc[-1]['median_amount20']),100_000_000.0)

    def test_nan_variant_requires_twenty_observed_amounts(self):
        dates=pd.date_range('2026-01-01', periods=20, freq='D')
        x=pd.DataFrame({'date':dates,'amount':[100_000_000.0]*20,'traded':[True]*20})
        for i in (2,6,10,14):
            x.loc[i,'amount']=float('nan'); x.loc[i,'traded']=False
        out=m.evaluate_one_calendar_series(x,80_000_000.0,'market_day_nan',min_actual_before=1)
        self.assertFalse(bool(out.iloc[-1]['eligible']))
        self.assertTrue(pd.isna(out.iloc[-1]['median_amount20']))

    def test_market_day_positive_ignores_nontraded_amounts_but_requires_density(self):
        dates=pd.date_range('2026-01-01', periods=20, freq='D')
        x=pd.DataFrame({'date':dates,'amount':[100_000_000.0]*20,'traded':[True]*20})
        for i in (2,6,10,14):
            x.loc[i,'amount']=0.0; x.loc[i,'traded']=False
        out=m.evaluate_one_calendar_series(x,80_000_000.0,'market_day_positive',min_actual_before=1)
        self.assertTrue(bool(out.iloc[-1]['eligible']))
        self.assertEqual(float(out.iloc[-1]['trade_density20']),0.8)
        self.assertEqual(float(out.iloc[-1]['median_amount20']),100_000_000.0)

    def test_last20_traded_uses_actual_traded_observations_with_market_density(self):
        dates=pd.date_range('2026-01-01', periods=25, freq='D')
        x=pd.DataFrame({'date':dates,'amount':[100_000_000.0]*25,'traded':[True]*25})
        for i in (2,6,10,14,18):
            x.loc[i,'amount']=0.0; x.loc[i,'traded']=False
        out=m.evaluate_one_calendar_series(x,80_000_000.0,'last20_traded',min_actual_before=1)
        self.assertTrue(bool(out.iloc[-1]['eligible']))
        self.assertEqual(float(out.iloc[-1]['trade_density20']),0.8)
        self.assertEqual(float(out.iloc[-1]['median_amount20']),100_000_000.0)

    def test_current_day_must_be_traded_and_120_rule(self):
        dates=pd.date_range('2026-01-01', periods=121, freq='D')
        x=pd.DataFrame({'date':dates,'amount':[100_000_000.0]*121,'traded':[True]*121})
        out=m.evaluate_one_calendar_series(x,80_000_000.0,'market_day_zero',min_actual_before=120)
        self.assertFalse(bool(out.iloc[118]['eligible']))
        self.assertTrue(bool(out.iloc[119]['eligible']))
        x.loc[120,'amount']=0.0; x.loc[120,'traded']=False
        out=m.evaluate_one_calendar_series(x,80_000_000.0,'market_day_zero',min_actual_before=120)
        self.assertFalse(bool(out.iloc[120]['eligible']))


if __name__=='__main__':
    unittest.main()
