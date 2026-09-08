import unittest

import pandas as pd

import liquidity_apply_v482 as m


class LiquidityApplyV482Tests(unittest.TestCase):
    def test_uses_frozen_80m_market_day_zero_prior120_semantics(self):
        dates=pd.date_range('2024-01-01',periods=141,freq='D')
        # 120 prior traded days are required. All days trade and amount is well above threshold.
        x=pd.DataFrame({'date':dates,'amount':[100_000_000.0]*141,'traded':[True]*141})
        out=m.apply_frozen_80m_one_symbol(x)
        self.assertFalse(bool(out.loc[119,'liquidity_80m_pre_st']))
        self.assertTrue(bool(out.loc[120,'liquidity_80m_pre_st']))
        self.assertEqual(float(out.loc[120,'median_amount20']),100_000_000.0)
        self.assertEqual(float(out.loc[120,'trade_density20']),1.0)

    def test_halt_is_zero_inside_20_market_day_median_and_current_halt_fails(self):
        dates=pd.date_range('2024-01-01',periods=141,freq='D')
        traded=[True]*141
        traded[130]=False
        amount=[100_000_000.0 if t else None for t in traded]
        x=pd.DataFrame({'date':dates,'amount':amount,'traded':traded})
        out=m.apply_frozen_80m_one_symbol(x)
        self.assertFalse(bool(out.loc[130,'liquidity_80m_pre_st']))
        self.assertEqual(float(out.loc[130,'median_amount20']),100_000_000.0)

    def test_non_st_overlay_is_separate_from_pre_st_liquidity(self):
        df=pd.DataFrame({
            'liquidity_80m_pre_st':[True,True,False],
            'isST':[0,1,0],
        })
        out=m.apply_non_st_overlay(df)
        self.assertEqual(out['eligible_non_st'].tolist(),[True,False,False])
        self.assertEqual(out['liquidity_80m_pre_st'].tolist(),[True,True,False])

    def test_exact_raw_pitst_date_contract_is_fail_closed(self):
        pit=pd.DataFrame({
            'symbol':['000001.SZ']*3,
            'date':['2024-01-01','2024-01-02','2024-01-03'],
            'tradestatus':[1,0,1],
            'isST':[0,0,0],
        })
        raw=pd.DataFrame({
            'symbol':['000001.SZ','000001.SZ'],
            'date':['2024-01-01','2024-01-03'],
            'amount':[100_000_000.0,100_000_000.0],
            'volume':[1_000_000.0,1_000_000.0],
        })
        audit=m.audit_raw_vs_pitst(raw,pit)
        self.assertEqual(audit['missing_trade_dates_n'],0)
        self.assertEqual(audit['extra_trade_dates_n'],0)
        self.assertEqual(audit['duplicate_raw_symbol_dates'],0)
        self.assertEqual(audit['status'],'PASS_EXACT_RAW_PITST')

    def test_sparse_lifecycle_pitst_expands_to_full_market_calendar_without_inventing_st_state(self):
        pit=pd.DataFrame({
            'symbol':['000001.SZ','000001.SZ','000002.SZ'],
            'date':['2024-01-01','2024-01-02','2024-01-02'],
            'tradestatus':[1,1,1],
            'isST':[0,0,0],
        })
        out=m.expand_pitst_to_market_calendar(
            pit,
            symbols=['000001.SZ','000002.SZ'],
            calendar=['2024-01-01','2024-01-02'],
        )
        self.assertEqual(len(out),4)
        self.assertEqual(int(out['pitst_observed'].sum()),3)
        padded=out[(out['symbol']=='000002.SZ')&(out['date']=='2024-01-01')].iloc[0]
        self.assertFalse(bool(padded['pitst_observed']))
        self.assertEqual(int(padded['tradestatus']),0)
        self.assertTrue(pd.isna(padded['isST']))


if __name__=='__main__':
    unittest.main()
