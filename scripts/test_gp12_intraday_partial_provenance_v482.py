import unittest

from gp12_intraday_partial_provenance_v482 import build_intraday_partial_provenance


class IntradayPartialProvenanceV482Test(unittest.TestCase):
    def _pass_record(self, seq):
        symbol=f'X{seq:06d}.SZ'
        return {
            'symbol':symbol,
            'status':'PASS_REQUIRED_TRADE_DATES_EXACT',
            'required_trade_dates':1,
            'missing_trade_dates':[],
            'invalid_grid_dates':[],
            'canonical_path':f'data/{symbol}.parquet',
            'source_downloaded':True,
            'source_sha256':f'{seq+1000:064x}',
            'source_bytes':1000+seq,
            'source_rows_total':240,
        }

    def shard_reports(self):
        reports=[]
        seq=1
        for i in range(17):
            selected=50 if i < 14 else 49
            pass_n=46 if i == 0 else selected
            records=[]
            for _ in range(pass_n):
                records.append(self._pass_record(seq)); seq += 1
            if i == 0:
                records.extend([
                    {
                        'symbol':'000638.SZ','status':'REVIEW_REQUIRED_TRADE_DATES',
                        'required_trade_dates':1419,
                        'missing_trade_dates':['2026-04-13'],'invalid_grid_dates':[],
                        'canonical_path':'data/000638.SZ.parquet','source_downloaded':True,
                        'source_sha256':'c'*64,'source_bytes':123456,'source_rows_total':300000,
                    },
                    {
                        'symbol':'600074.SH','status':'EXPECTED_ZERO_TRADE_NA','required_trade_dates':0,
                        'missing_trade_dates':[],'invalid_grid_dates':[],'canonical_path':'data/600074.SH.parquet',
                        'source_downloaded':False,'source_sha256':None,'source_bytes':0,
                    },
                    {
                        'symbol':'600485.SH','status':'EXPECTED_ZERO_TRADE_NA','required_trade_dates':0,
                        'missing_trade_dates':[],'invalid_grid_dates':[],'canonical_path':'data/600485.SH.parquet',
                        'source_downloaded':False,'source_sha256':None,'source_bytes':0,
                    },
                    {
                        'symbol':'600677.SH','status':'EXPECTED_ZERO_TRADE_NA','required_trade_dates':0,
                        'missing_trade_dates':[],'invalid_grid_dates':[],'canonical_path':'data/600677.SH.parquet',
                        'source_downloaded':False,'source_sha256':None,'source_bytes':0,
                    },
                ])
            reports.append({
                'artifact':'INTRADAY_FORMAL847_MATERIALIZATION_SHARD_V482',
                'version':'V4.82',
                'dataset':'neigezhu/china-a-share-1min-ohlcv',
                'snapshot_commit':'f311a5f11569e9d541386982d15f2214d9970b8a',
                'shard_index':i,'shard_count':17,
                'symbols_selected':selected,
                'pass_symbols':pass_n,
                'expected_zero_trade_symbols':3 if i == 0 else 0,
                'review_symbols':1 if i == 0 else 0,
                'required_trade_dates':1011607 if i == 0 else 0,
                'valid_trade_dates':1011606 if i == 0 else 0,
                'missing_trade_dates':1 if i == 0 else 0,
                'invalid_grid_dates':0,
                'bars_15m':{'rows':16185696 if i == 0 else 0,'sha256':'a'*64 if i == 0 else f'{i+1:064x}'},
                'bars_60m':{'rows':4046424 if i == 0 else 0,'sha256':'b'*64 if i == 0 else f'{i+18:064x}'},
                'records':records,
                'source_bytes_downloaded':sum(int(r.get('source_bytes',0)) for r in records),
            })
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

    def test_all_row_bearing_source_files_are_hash_bound_separately_from_date_coverage(self):
        x=build_intraday_partial_provenance(self.shard_reports(),self.baostock(),self.sina())
        self.assertTrue(x['formal_847_source_files_bytes_hash_bound'])
        self.assertEqual(x['primary_snapshot']['source_files_hash_bound'],844)
        self.assertGreater(x['primary_snapshot']['source_bytes_hash_bound'],0)
        self.assertEqual(len(x['primary_snapshot']['source_file_binding_semantic_sha256']),64)
        self.assertFalse(x['formal_847_required_minute_date_coverage_complete'])
        self.assertEqual(x['exact_gap'],{'symbol':'000638.SZ','date':'2026-04-13'})

    def test_missing_source_sha_fails_source_byte_binding(self):
        r=self.shard_reports()
        r[1]['records'][0]['source_sha256']=None
        with self.assertRaisesRegex(ValueError,'source byte'):
            build_intraday_partial_provenance(r,self.baostock(),self.sina())

    def test_only_three_known_zero_trade_symbols_are_allowed(self):
        r=self.shard_reports()
        r[0]['records'][-3]['symbol']='600000.SH'
        with self.assertRaisesRegex(ValueError,'zero-trade'):
            build_intraday_partial_provenance(r,self.baostock(),self.sina())

    def test_second_missing_day_fails_closed(self):
        r=self.shard_reports(); r[1]['missing_trade_dates']=1; r[1]['review_symbols']=1
        r[1]['records'][0]['status']='REVIEW_REQUIRED_TRADE_DATES'
        r[1]['records'][0]['missing_trade_dates']=['2026-04-14']
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
