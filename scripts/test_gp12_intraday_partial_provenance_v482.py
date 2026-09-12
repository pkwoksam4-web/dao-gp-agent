import unittest

from gp12_intraday_partial_provenance_v482 import build_intraday_partial_provenance


class IntradayPartialProvenanceV482Test(unittest.TestCase):
    def shard_reports(self):
        reports=[]
        for i in range(17):
            reports.append({
                'artifact':'INTRADAY_FORMAL847_MATERIALIZATION_SHARD_V482',
                'version':'V4.82',
                'dataset':'neigezhu/china-a-share-1min-ohlcv',
                'snapshot_commit':'f311a5f11569e9d541386982d15f2214d9970b8a',
                'shard_index':i,'shard_count':17,
                'symbols_selected':50 if i < 14 else 49,
                'pass_symbols':50 if i < 14 else 49,
                'expected_zero_trade_symbols':0,
                'review_symbols':0,
                'required_trade_dates':0,'valid_trade_dates':0,
                'missing_trade_dates':0,'invalid_grid_dates':0,
                'bars_15m':{'rows':0,'sha256':f'{i+1:064x}'},
                'bars_60m':{'rows':0,'sha256':f'{i+18:064x}'},
                'records':[],
            })
        # Replace summary counts with exact frozen global cardinalities while preserving 17 unique shards.
        r=reports[0]
        r.update({
            'symbols_selected':50,'pass_symbols':46,'expected_zero_trade_symbols':3,'review_symbols':1,
            'required_trade_dates':1011607,'valid_trade_dates':1011606,
            'missing_trade_dates':1,'invalid_grid_dates':0,
            'bars_15m':{'rows':16185696,'sha256':'a'*64},
            'bars_60m':{'rows':4046424,'sha256':'b'*64},
            'records':[
                {'symbol':'000638.SZ','status':'REVIEW_REQUIRED_TRADE_DATES','missing_trade_dates':['2026-04-13'],'invalid_grid_dates':[]},
                {'symbol':'600074.SH','status':'EXPECTED_ZERO_TRADE_NA','missing_trade_dates':[],'invalid_grid_dates':[]},
                {'symbol':'600485.SH','status':'EXPECTED_ZERO_TRADE_NA','missing_trade_dates':[],'invalid_grid_dates':[]},
                {'symbol':'600677.SH','status':'EXPECTED_ZERO_TRADE_NA','missing_trade_dates':[],'invalid_grid_dates':[]},
            ],
        })
        # Zero out other shard contributions to global summaries.
        for rr in reports[1:]:
            rr.update({'required_trade_dates':0,'valid_trade_dates':0,'bars_15m':{'rows':0,'sha256':rr['bars_15m']['sha256']},'bars_60m':{'rows':0,'sha256':rr['bars_60m']['sha256']}})
        # Keep exact global symbol totals 847 and pass total 843.
        reports[0]['symbols_selected']=50
        for i in range(1,14): reports[i]['symbols_selected']=50
        for i in range(14,17): reports[i]['symbols_selected']=49
        reports[0]['pass_symbols']=46
        for i in range(1,14): reports[i]['pass_symbols']=50
        for i in range(14,17): reports[i]['pass_symbols']=49
        return reports

    def baostock(self):
        return {
            'artifact':'INTRADAY_000638_BAOSTOCK_PROBE_V482','version':'V4.82',
            'symbol':'000638.SZ','date':'2026-04-13','provider':'BaoStock','query_code':'sz.000638','adjustflag':'3',
            'formal_fill_allowed':False,'minute_byte_coverage_verified':False,
            'frequencies':{
                '5':{'error_code':'0','count':48,'response_canonical_sha256':'6cb7243bf6b535a6dd3ef9991025a1394a2c1913f5ae963c06c63f139e6347db'},
                '15':{'error_code':'0','count':16,'response_canonical_sha256':'f4aaa1728793a02b3e8804789ec0cee1ca1c1e15d7bdda1a22247ac295e6420c'},
                '60':{'error_code':'0','count':4,'response_canonical_sha256':'f6ef9280856e0946d1970ea13f680fff14139a258a6aaf9b811fb2da0a4cc6d7'},
            },
        }

    def sina(self):
        return {
            'artifact':'SINA_000638_1M_PROBE_V482','version':'V4.82','symbol':'000638.SZ','target_date':'2026-04-13',
            'target_present':True,'target_rows':238,'target_first_timestamp':'2026-04-13 09:31:00','target_last_timestamp':'2026-04-13 15:00:00',
            'target_rows_sha256':'72eac61af5dcd6b9d35e890f26f122e30905db1459da1f91d8557857de2faacc',
            'eligible_as_fallback_source':False,'formal_847_coverage_promoted':False,'model_freeze_allowed':False,'oos_metrics_allowed':False,
        }

    def test_exact_single_gap_closes_aggregate_bars_only(self):
        x=build_intraday_partial_provenance(self.shard_reports(),self.baostock(),self.sina())
        self.assertEqual(x['status'],'PASS_FORMAL847_15M_60M_COVERAGE_PARTIAL_INTRADAY_PROVENANCE')
        self.assertEqual(x['primary_snapshot']['symbol_n'],847)
        self.assertEqual(x['primary_snapshot']['required_trade_dates'],1011607)
        self.assertEqual(x['primary_snapshot']['valid_trade_dates'],1011606)
        self.assertEqual(x['primary_snapshot']['missing_trade_dates'],1)
        self.assertEqual(x['primary_snapshot']['invalid_grid_dates'],0)
        self.assertEqual(x['primary_snapshot']['bars_15m_rows'],16185696)
        self.assertEqual(x['primary_snapshot']['bars_60m_rows'],4046424)
        self.assertEqual(x['exact_gap'],{'symbol':'000638.SZ','date':'2026-04-13'})
        self.assertTrue(x['formal_847_15m_coverage_verified'])
        self.assertTrue(x['formal_847_60m_coverage_verified'])
        self.assertFalse(x['formal_847_minute_byte_coverage_verified'])
        self.assertFalse(x['historical_gp_intraday_resampling_contract_recovered'])
        self.assertFalse(x['factor_formula_recovered'])
        self.assertFalse(x['blocker_closed'])
        self.assertFalse(x['model_freeze_allowed'])
        self.assertFalse(x['oos_metrics_allowed'])

    def test_only_three_known_zero_trade_symbols_are_allowed(self):
        r=self.shard_reports()
        r[0]['records'][1]['symbol']='600000.SH'
        with self.assertRaisesRegex(ValueError,'zero-trade'):
            build_intraday_partial_provenance(r,self.baostock(),self.sina())

    def test_second_missing_day_fails_closed(self):
        r=self.shard_reports(); r[1]['missing_trade_dates']=1; r[1]['review_symbols']=1
        r[1]['records']=[{'symbol':'000001.SZ','status':'REVIEW_REQUIRED_TRADE_DATES','missing_trade_dates':['2026-04-14'],'invalid_grid_dates':[]}]
        with self.assertRaises(ValueError):
            build_intraday_partial_provenance(r,self.baostock(),self.sina())

    def test_baostock_identity_hash_or_count_change_fails(self):
        p=self.baostock(); p['frequencies']['15']['count']=15
        with self.assertRaisesRegex(ValueError,'BaoStock'):
            build_intraday_partial_provenance(self.shard_reports(),p,self.sina())

    def test_sina_remains_corroboration_not_minute_fill(self):
        s=self.sina(); s['eligible_as_fallback_source']=True
        with self.assertRaisesRegex(ValueError,'Sina'):
            build_intraday_partial_provenance(self.shard_reports(),self.baostock(),s)


if __name__=='__main__':
    unittest.main()
