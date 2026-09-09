import hashlib
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

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

    def test_global_reaudit_supersedes_stale_shard_review_but_not_shard_errors(self):
        common=dict(
            unique_symbol_n=847,
            symbol_list_n=847,
            raw_rows=1_011_607,
            duplicate_rows=0,
            missing_n=0,
            extra_n=0,
            bad_ohlc=0,
            bad_volume=0,
            bad_amount=0,
        )
        self.assertTrue(m.full_raw_global_gate(**common,shard_error=0))
        self.assertFalse(m.full_raw_global_gate(**common,shard_error=1))

    def test_merge_report_binds_exact_full_parquet_bytes_and_schema(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            shards=root/'shards'; shards.mkdir()
            out=root/'out'
            pit=root/'pit.csv'
            pd.DataFrame([{
                'symbol':'000001.SZ','date':'2020-06-01','tradestatus':1,'isST':0,
            }]).to_csv(pit,index=False)
            raw=pd.DataFrame([{
                'symbol':'000001.SZ','date':'2020-06-01','open':10.0,'high':11.0,
                'low':9.5,'close':10.5,'volume':1000.0,'amount':10000.0,'source':'SOHU_RAW',
            }],columns=m.RAW_FIELDS)
            raw.to_parquet(shards/'SOHU_RAW_SHARD_00_V482.parquet',index=False)
            (shards/'SOHU_RAW_SHARD_00_AUDIT_V482.json').write_text(json.dumps({
                'shard_index':0,'shard_count':1,'symbol_list':['000001.SZ'],
                'review_n':0,'error_n':0,
            }),encoding='utf-8')
            with patch.object(m,'EXPECTED_SYMBOL_N',1), patch.object(m,'EXPECTED_TRADE_ROWS',1), patch.object(m,'PITST_TRADESTATUS_ONE_CORRECTIONS',set()):
                report=m.merge_shards(shards,pit,out)
            full=out/'SOHU_RAW_FULL_V482.parquet'
            expected_sha=hashlib.sha256(full.read_bytes()).hexdigest()
            self.assertEqual(report['full_parquet_sha256'],expected_sha)
            self.assertEqual(report['full_parquet_bytes'],full.stat().st_size)
            self.assertRegex(report['schema_fingerprint'],r'^[0-9a-f]{64}$')

    def test_one_byte_mutation_changes_full_parquet_identity(self):
        self.assertTrue(callable(getattr(m,'sha256_file',None)), 'sohu_full_panel_v482 must expose/use sha256_file')
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'raw.parquet'
            p.write_bytes(b'abc')
            first=m.sha256_file(p)
            p.write_bytes(b'abd')
            self.assertNotEqual(m.sha256_file(p),first)


if __name__=='__main__':
    unittest.main()
