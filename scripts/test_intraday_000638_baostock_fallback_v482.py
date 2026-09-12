import unittest

import pandas as pd

import intraday_000638_baostock_fallback_v482 as mod


class BaoStockFallbackV482Tests(unittest.TestCase):
    def probe(self):
        rows15 = []
        for t in ['0945','1000','1015','1030','1045','1100','1115','1130','1315','1330','1345','1400','1415','1430','1445','1500']:
            rows15.append({'date':'2026-04-13','time':f'20260413{t}00000','code':'sz.000638','open':'0.8900','high':'0.8900','low':'0.8900','close':'0.8900','volume':'100','amount':'89.0000','adjustflag':'3'})
        rows60 = []
        for t in ['1030','1130','1400','1500']:
            rows60.append({'date':'2026-04-13','time':f'20260413{t}00000','code':'sz.000638','open':'0.8900','high':'0.8900','low':'0.8900','close':'0.8900','volume':'400','amount':'356.0000','adjustflag':'3'})
        return {
            'artifact':'INTRADAY_000638_BAOSTOCK_PROBE_V482','version':'V4.82','symbol':'000638.SZ','date':'2026-04-13',
            'provider':'BaoStock','query_code':'sz.000638','adjustflag':'3','formal_fill_allowed':False,
            'minute_byte_coverage_verified':False,
            'frequencies':{
                '15':{'error_code':'0','count':16,'rows':rows15,'response_canonical_sha256':mod.BAOSTOCK_15M_CANONICAL_SHA256},
                '60':{'error_code':'0','count':4,'rows':rows60,'response_canonical_sha256':mod.BAOSTOCK_60M_CANONICAL_SHA256},
                '5':{'error_code':'0','count':48,'rows':[],'response_canonical_sha256':mod.BAOSTOCK_5M_CANONICAL_SHA256},
            },
        }

    def test_only_exact_symbol_date_provider_adjustflag_are_allowed(self):
        p = self.probe()
        mod.validate_baostock_probe_identity(p)
        for key, bad in [('symbol','000001.SZ'),('date','2026-04-14'),('provider','Other'),('adjustflag','2')]:
            x = {**p, key: bad}
            with self.assertRaises(ValueError):
                mod.validate_baostock_probe_identity(x)

    def test_exact_source_identity_constants_are_locked(self):
        self.assertEqual(mod.SINA_RUN_ID, 34444014051)
        self.assertEqual(mod.SINA_ARTIFACT_ID, 10138954337)
        self.assertEqual(mod.SINA_ARTIFACT_ZIP_SHA256, 'a42b71995fdc355a920dc062a40c6294db129c2c41f3dbdc29b2d8a80fb5a7eb')
        self.assertEqual(mod.SINA_TARGET_ROWS_SHA256, '72eac61af5dcd6b9d35e890f26f122e30905db1459da1f91d8557857de2faacc')
        self.assertEqual(mod.BAOSTOCK_RUN_ID, 34452654219)
        self.assertEqual(mod.BAOSTOCK_ARTIFACT_ID, 10142164418)
        self.assertEqual(mod.BAOSTOCK_ARTIFACT_ZIP_SHA256, 'eaf42fa65436c874e252fc7426612f40b46597f6be2c1738fb2bfc3fbb823e60')

    def test_overlay_matches_primary_bar_schema_and_exact_counts(self):
        b15, b60 = mod.build_overlay(self.probe())
        self.assertEqual(list(b15.columns), mod.BAR_COLUMNS)
        self.assertEqual(list(b60.columns), mod.BAR_COLUMNS)
        self.assertEqual(len(b15), 16)
        self.assertEqual(len(b60), 4)
        self.assertEqual(set(b15['symbol']), {'000638.SZ'})
        self.assertEqual(set(b60['symbol']), {'000638.SZ'})
        self.assertEqual(set(b15['trade_date'].dt.strftime('%Y-%m-%d')), {'2026-04-13'})
        self.assertEqual(set(b60['trade_date'].dt.strftime('%Y-%m-%d')), {'2026-04-13'})
        self.assertEqual(list(b15['bar_end'].dt.strftime('%H:%M')), ['09:45','10:00','10:15','10:30','10:45','11:00','11:15','11:30','13:15','13:30','13:45','14:00','14:15','14:30','14:45','15:00'])
        self.assertEqual(list(b60['bar_end'].dt.strftime('%H:%M')), ['10:30','11:30','14:00','15:00'])

    def test_overlay_is_aggregate_source_not_fake_minute_rows(self):
        b15, b60 = mod.build_overlay(self.probe())
        self.assertTrue((b15['source_rows'] == 1).all())
        self.assertTrue((b60['source_rows'] == 1).all())

    def test_final_flags_keep_minute_strategy_freeze_oos_closed(self):
        flags = mod.coverage_flags_after_exact_overlay(primary_valid_days=1011606, required_days=1011607, overlay_days=1)
        self.assertTrue(flags['formal_847_15m_coverage_verified'])
        self.assertTrue(flags['formal_847_60m_coverage_verified'])
        self.assertFalse(flags['formal_847_minute_byte_coverage_verified'])
        self.assertFalse(flags['historical_gp_intraday_resampling_contract_recovered'])
        self.assertFalse(flags['factor_formula_recovered'])
        self.assertFalse(flags['model_freeze_allowed'])
        self.assertFalse(flags['oos_metrics_allowed'])

    def test_wrong_overlay_cardinality_fails_closed(self):
        with self.assertRaises(ValueError):
            mod.coverage_flags_after_exact_overlay(primary_valid_days=1011606, required_days=1011607, overlay_days=0)
        with self.assertRaises(ValueError):
            mod.coverage_flags_after_exact_overlay(primary_valid_days=1011606, required_days=1011607, overlay_days=2)


if __name__ == '__main__':
    unittest.main()
