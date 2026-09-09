import copy
import unittest

import formal_readiness_finalize_v482 as mod


class FormalReadinessFinalizeV482Tests(unittest.TestCase):
    def _market_docs(self):
        raw_sha='a'*64
        pit_sha='b'*64
        panel_sha='c'*64
        raw={
            'artifact':'SOHU_RAW_FULL_V482','version':'V4.82','status':'PASS_FULL_RAW_V482',
            'symbol_n':847,'raw_rows':1_011_607,'expected_trade_rows':1_011_607,
            'duplicate_symbol_dates':0,'missing_trade_dates_n':0,'extra_trade_dates_n':0,
            'bad_ohlc_rows':0,'bad_volume_rows':0,'bad_amount_rows':0,'shard_error_n':0,
            'global_reaudit_pass':True,'zero_trade_symbols':['600074.SH','600485.SH','600677.SH'],
            'full_parquet_sha256':raw_sha,'full_parquet_bytes':123456,'schema_fingerprint':'d'*64,
            'formal_admission':False,'oos_metrics_allowed':False,
        }
        liq={
            'artifact':'LIQUIDITY_80M_APPLY_V482','version':'V4.82','threshold_cny':80_000_000,
            'symbol_n':847,'calendar_days':1426,'panel_rows':1_207_822,
            'pitst_source_rows':1_022_100,'pitst_observed_rows':1_022_100,'lifecycle_padding_rows':185_722,
            'corrected_trade_rows':1_011_607,'raw_trade_rows':1_011_607,
            'current_trade_violation_n':0,'st_overlay_violation_n':0,
            'input_full_raw_sha256':raw_sha,'input_pitst_sha256':pit_sha,
            'panel_parquet_sha256':panel_sha,'panel_parquet_bytes':654321,'schema_fingerprint':'e'*64,
            'raw_pitst_audit':{
                'status':'PASS_EXACT_RAW_PITST','expected_trade_rows':1_011_607,'raw_trade_rows':1_011_607,
                'duplicate_raw_symbol_dates':0,'missing_trade_dates_n':0,'extra_trade_dates_n':0,
                'bad_amount_rows':0,'bad_volume_rows':0,
            },
            'formal_admission':False,'oos_metrics_allowed':False,
        }
        return raw,liq

    def test_merge_requires_exact_key_price_and_materialized_sha(self):
        special=[{'symbol':'000430.SZ','ex_date':'2025-12-29','adjusted_reference_price':6.87,'corrected_event_ratio':0.86}]
        report={'target_n':1,'materialized_n':1,'unresolved_n':0,'records':[{
            'symbol':'000430.SZ','ex_date':'2025-12-29','adjusted_reference_price':6.87,'status':'PASS_CNINFO_MATERIALIZED',
            'provenance':{'source':'CNINFO_OFFICIAL_PDF','announcement_id':'123','materialized_sha256':'a'*64}
        }]}
        rows=mod.enrich_special_rows(special,report,expected_n=1)
        self.assertEqual(rows[0]['materialized_sha256'],'a'*64)
        self.assertEqual(rows[0]['announcement_id'],'123')

    def test_unresolved_special_blocks_enrichment(self):
        special=[{'symbol':'000430.SZ','ex_date':'2025-12-29','adjusted_reference_price':6.87,'corrected_event_ratio':0.86}]
        report={'target_n':1,'materialized_n':0,'unresolved_n':1,'records':[{
            'symbol':'000430.SZ','ex_date':'2025-12-29','status':'UNRESOLVED','provenance':None
        }]}
        with self.assertRaises(ValueError):
            mod.enrich_special_rows(special,report,expected_n=1)

    def test_market_data_readiness_requires_exact_full_raw_and_frozen_liquidity(self):
        raw,liq=self._market_docs()
        out=mod.validate_market_data_readiness(raw,liq)
        self.assertTrue(out['market_data_ready'])
        self.assertEqual(out['raw_trade_rows'],1_011_607)
        self.assertEqual(out['panel_rows'],1_207_822)
        self.assertEqual(out['lifecycle_padding_rows'],185_722)
        self.assertEqual(out['byte_bindings'],{
            'full_raw_sha256':'a'*64,
            'liquidity_panel_sha256':'c'*64,
            'pitst_sha256':'b'*64,
        })

        bad=dict(raw); bad['missing_trade_dates_n']=1
        with self.assertRaises(ValueError):
            mod.validate_market_data_readiness(bad,liq)

    def test_summary_only_market_data_is_rejected(self):
        raw,liq=self._market_docs()
        for key in ('full_parquet_sha256','full_parquet_bytes','schema_fingerprint'):
            raw.pop(key)
        for key in ('input_full_raw_sha256','input_pitst_sha256','panel_parquet_sha256','panel_parquet_bytes','schema_fingerprint'):
            liq.pop(key)
        with self.assertRaises(ValueError):
            mod.validate_market_data_readiness(raw,liq)

    def test_raw_to_liquidity_hash_mismatch_is_rejected(self):
        raw,liq=self._market_docs()
        liq=copy.deepcopy(liq)
        liq['input_full_raw_sha256']='f'*64
        with self.assertRaises(ValueError):
            mod.validate_market_data_readiness(raw,liq)

    def test_malformed_market_data_hash_is_rejected(self):
        raw,liq=self._market_docs()
        raw=dict(raw); raw['full_parquet_sha256']='NOT-A-SHA'
        with self.assertRaises(ValueError):
            mod.validate_market_data_readiness(raw,liq)


if __name__=='__main__': unittest.main()
