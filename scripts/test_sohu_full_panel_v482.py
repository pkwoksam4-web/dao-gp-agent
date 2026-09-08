import unittest

import pandas as pd

import sohu_full_panel_v482 as m


class SohuFullPanelV482Tests(unittest.TestCase):
    def test_shard_partition_is_complete_disjoint_and_deterministic(self):
        symbols=[f'{i:06d}.SZ' for i in range(17)]
        shards=[m.select_shard(symbols,i,4) for i in range(4)]
        flat=[s for part in shards for s in part]
        self.assertEqual(sorted(flat),sorted(symbols))
        self.assertEqual(len(flat),len(set(flat)))
        self.assertEqual(shards[0],symbols[0::4])

    def test_exact_trade_date_audit_passes_only_on_equal_sets(self):
        expected=['2020-06-01','2020-06-02','2020-06-04']
        actual=[{'date':'2020-06-01'},{'date':'2020-06-02'},{'date':'2020-06-04'}]
        a=m.audit_trade_dates('000001.SZ',expected,actual)
        self.assertEqual(a['status'],'PASS_EXACT_TRADE_DATES')
        self.assertEqual(a['missing_dates_n'],0)
        self.assertEqual(a['extra_dates_n'],0)

    def test_missing_or_extra_trade_date_fails_closed(self):
        expected=['2020-06-01','2020-06-02']
        a=m.audit_trade_dates('000001.SZ',expected,[{'date':'2020-06-01'}])
        self.assertEqual(a['status'],'REVIEW_TRADE_DATES')
        self.assertEqual(a['missing_dates'],['2020-06-02'])
        b=m.audit_trade_dates('000001.SZ',expected,[{'date':'2020-06-01'},{'date':'2020-06-02'},{'date':'2020-06-03'}])
        self.assertEqual(b['status'],'REVIEW_TRADE_DATES')
        self.assertEqual(b['extra_dates'],['2020-06-03'])

    def test_zero_trade_symbol_requires_zero_raw_rows(self):
        a=m.audit_trade_dates('600074.SH',[],[])
        self.assertEqual(a['status'],'PASS_EXACT_TRADE_DATES')
        b=m.audit_trade_dates('600074.SH',[],[{'date':'2020-06-01'}])
        self.assertEqual(b['status'],'REVIEW_TRADE_DATES')

    def test_expected_dates_from_pitst_uses_only_tradestatus_one(self):
        df=pd.DataFrame({
            'symbol':['000001.SZ']*3,
            'date':['2020-06-01','2020-06-02','2020-06-03'],
            'tradestatus':[1,0,1],
            'isST':[0,0,0],
        })
        self.assertEqual(m.expected_trade_dates(df,'000001.SZ'),['2020-06-01','2020-06-03'])

    def test_v482_pitst_corrections_are_exact_and_do_not_broaden_other_zero_rows(self):
        targets=[
            ('002087.SZ','2024-06-13'),
            ('600647.SH','2024-06-13'),
            ('600766.SH','2024-06-13'),
            ('603133.SH','2024-06-13'),
            ('300356.SZ','2023-06-20'),
        ]
        df=pd.DataFrame({
            'symbol':[s for s,_ in targets]+['000001.SZ'],
            'date':[d for _,d in targets]+['2024-06-13'],
            'tradestatus':[0]*6,
            'isST':[0]*6,
        })
        fixed=m.apply_pitst_trade_corrections(df)
        corrected=fixed.iloc[:len(targets)]
        self.assertTrue((corrected['tradestatus']==1).all())
        self.assertEqual(int(fixed.loc[fixed['symbol']=='000001.SZ','tradestatus'].iloc[0]),0)
        self.assertEqual(m.PITST_TRADESTATUS_ONE_CORRECTIONS,set(targets))
        self.assertEqual(m.EXPECTED_TRADE_ROWS,1_011_607)


if __name__=='__main__':
    unittest.main()
