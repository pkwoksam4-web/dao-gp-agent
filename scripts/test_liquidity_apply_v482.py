import hashlib
import pathlib
import tempfile
import unittest
from unittest.mock import patch

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

    def test_upstream_corrected_trade_row_contract_is_1011607(self):
        self.assertEqual(m.EXPECTED_TRADE_ROWS,1_011_607)

    def test_run_binds_raw_pitst_and_output_panel_exact_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            raw_path=root/'raw.parquet'
            pit_path=root/'pit.csv'
            out=root/'out'
            raw=pd.DataFrame([{'symbol':'000001.SZ','date':'2024-01-02','amount':100_000_000.0,'volume':1_000_000.0}])
            pit=pd.DataFrame([{'symbol':'000001.SZ','date':'2024-01-02','tradestatus':1,'isST':0}])
            raw.to_parquet(raw_path,index=False)
            pit.to_csv(pit_path,index=False)
            panel=pd.DataFrame([{'symbol':'000001.SZ','date':'2024-01-02','eligible_non_st':True}])
            base_report={'artifact':'LIQUIDITY_80M_APPLY_V482','version':'V4.82','formal_admission':False,'oos_metrics_allowed':False}
            with patch.object(m,'build_eligibility_panel',return_value=(panel,base_report)):
                report=m.run(raw_path,pit_path,out)
            panel_path=out/'LIQUIDITY_80M_PANEL_V482.parquet'
            self.assertEqual(report['input_full_raw_sha256'],hashlib.sha256(raw_path.read_bytes()).hexdigest())
            self.assertEqual(report['input_pitst_sha256'],hashlib.sha256(pit_path.read_bytes()).hexdigest())
            self.assertEqual(report['panel_parquet_sha256'],hashlib.sha256(panel_path.read_bytes()).hexdigest())
            self.assertEqual(report['panel_parquet_bytes'],panel_path.stat().st_size)
            self.assertRegex(report['schema_fingerprint'],r'^[0-9a-f]{64}$')

    def test_input_raw_mutation_changes_liquidity_binding(self):
        self.assertTrue(callable(getattr(m,'sha256_file',None)), 'liquidity_apply_v482 must expose/use sha256_file')
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'raw.parquet'
            p.write_bytes(b'raw-a')
            first=m.sha256_file(p)
            p.write_bytes(b'raw-b')
            self.assertNotEqual(m.sha256_file(p),first)


if __name__=='__main__':
    unittest.main()
