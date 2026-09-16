from __future__ import annotations

import unittest

import pandas as pd

import gp12_upper_limit_full_v1 as sut


class UpperLimitFullMaterializerTests(unittest.TestCase):
    def test_listing_rank_only_for_ipos_inside_formal_window(self):
        reference = pd.DataFrame([
            {"symbol": "000001.SZ", "date": "2020-06-01", "close": 10.0, "reference_close_cny": 9.5},
            {"symbol": "000001.SZ", "date": "2020-06-02", "close": 10.1, "reference_close_cny": 10.0},
            {"symbol": "001267.SZ", "date": "2021-11-17", "close": 20.0, "reference_close_cny": 10.0},
            {"symbol": "001267.SZ", "date": "2021-11-18", "close": 19.0, "reference_close_cny": 20.0},
        ])
        ipo = {"000001.SZ": "1991-04-03", "001267.SZ": "2021-11-17"}
        ranked = sut.attach_listing_trade_rank(reference, ipo, formal_start="2020-06-01")
        old = ranked[ranked.symbol.eq("000001.SZ")]
        new = ranked[ranked.symbol.eq("001267.SZ")]
        self.assertTrue(old["listing_trade_rank"].isna().all())
        self.assertEqual(new["listing_trade_rank"].tolist(), [1, 2])

    def test_materialize_applies_normal_rule_and_exact_special_override(self):
        reference = pd.DataFrame([
            {"symbol": "000001.SZ", "date": "2024-01-02", "close": 11.0, "reference_close_cny": 10.0},
            {"symbol": "000001.SZ", "date": "2024-01-03", "close": 10.5, "reference_close_cny": 10.0},
            {"symbol": "000670.SZ", "date": "2022-08-22", "close": 9.0, "reference_close_cny": 5.0},
        ])
        pit = pd.DataFrame([
            {"symbol": "000001.SZ", "date": "2024-01-02", "isST": 0},
            {"symbol": "000001.SZ", "date": "2024-01-03", "isST": 1},
            {"symbol": "000670.SZ", "date": "2022-08-22", "isST": 0},
        ])
        ipo = {"000001.SZ": "1991-04-03", "000670.SZ": "1996-12-10"}
        special = {("000670.SZ", "2022-08-22")}
        out, audit = sut.materialize_upper_limit_panel(reference, pit, ipo, special_keys=special)
        a = out[(out.symbol == "000001.SZ") & (out.date == "2024-01-02")].iloc[0]
        b = out[(out.symbol == "000001.SZ") & (out.date == "2024-01-03")].iloc[0]
        c = out[(out.symbol == "000670.SZ") & (out.date == "2022-08-22")].iloc[0]
        self.assertEqual(a.limit_pct_percent, 10.0)
        self.assertEqual(a.limit_price_cny, 11.0)
        self.assertTrue(bool(a.upper_limit))
        self.assertEqual(b.limit_pct_percent, 5.0)
        self.assertEqual(b.limit_price_cny, 10.5)
        self.assertTrue(bool(b.upper_limit))
        self.assertTrue(bool(c.special_no_limit))
        self.assertTrue(pd.isna(c.limit_pct_percent))
        self.assertTrue(pd.isna(c.limit_price_cny))
        self.assertFalse(bool(c.upper_limit))
        self.assertEqual(audit["status"], "PASS_UPPER_LIMIT_PANEL")
        self.assertEqual(audit["special_no_limit_rows"], 1)

    def test_registration_ipo_first_five_positive_trade_rows_are_no_limit(self):
        dates = ["2023-04-10", "2023-04-11", "2023-04-12", "2023-04-13", "2023-04-14", "2023-04-17"]
        reference = pd.DataFrame([
            {"symbol": "001286.SZ", "date": d, "close": 10.0, "reference_close_cny": 9.0}
            for d in dates
        ])
        pit = pd.DataFrame([{"symbol": "001286.SZ", "date": d, "isST": 0} for d in dates])
        out, _ = sut.materialize_upper_limit_panel(reference, pit, {"001286.SZ": "2023-04-10"}, special_keys=set())
        self.assertEqual(out["listing_trade_rank"].tolist(), [1, 2, 3, 4, 5, 6])
        self.assertTrue(out.iloc[:5]["limit_pct_percent"].isna().all())
        self.assertEqual(out.iloc[5]["limit_pct_percent"], 10.0)

    def test_missing_status_join_fails_closed(self):
        reference = pd.DataFrame([
            {"symbol": "000001.SZ", "date": "2024-01-02", "close": 10.0, "reference_close_cny": 9.5},
        ])
        pit = pd.DataFrame(columns=["symbol", "date", "isST"])
        with self.assertRaisesRegex(ValueError, "missing PIT status"):
            sut.materialize_upper_limit_panel(reference, pit, {"000001.SZ": "1991-04-03"}, special_keys=set())

    def test_duplicate_reference_key_fails_closed(self):
        reference = pd.DataFrame([
            {"symbol": "000001.SZ", "date": "2024-01-02", "close": 10.0, "reference_close_cny": 9.5},
            {"symbol": "000001.SZ", "date": "2024-01-02", "close": 10.0, "reference_close_cny": 9.5},
        ])
        pit = pd.DataFrame([{"symbol": "000001.SZ", "date": "2024-01-02", "isST": 0}])
        with self.assertRaisesRegex(ValueError, "duplicate reference"):
            sut.materialize_upper_limit_panel(reference, pit, {"000001.SZ": "1991-04-03"}, special_keys=set())


if __name__ == "__main__":
    unittest.main()
