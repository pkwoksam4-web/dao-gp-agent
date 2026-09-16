from __future__ import annotations

import unittest

import pandas as pd

import gp12_status_full_panel_v1 as sut


class StatusFullPanelTests(unittest.TestCase):
    def test_materializes_strict_boolean_status_and_nontrade_false(self):
        lifecycle = pd.DataFrame([
            {"symbol": "000001.SZ", "date": "2024-01-02", "isST": 0},
            {"symbol": "000001.SZ", "date": "2024-01-03", "isST": 0},
            {"symbol": "000002.SZ", "date": "2024-01-02", "isST": 1},
        ])
        reference = pd.DataFrame([
            {"symbol": "000001.SZ", "date": "2024-01-02", "close": 11.00, "reference_close_cny": 10.00},
            {"symbol": "000002.SZ", "date": "2024-01-02", "close": 2.00, "reference_close_cny": 1.90},
        ])
        panel, audit = sut.build_status_panel(
            lifecycle,
            reference,
            ipo_map={"000001.SZ": "1991-04-03", "000002.SZ": "1991-01-29"},
            special_no_limit_dates=set(),
        )
        self.assertEqual(len(panel), 3)
        rows = panel.set_index(["symbol", "date"])
        self.assertTrue(bool(rows.loc[("000001.SZ", "2024-01-02"), "tradable"]))
        self.assertTrue(bool(rows.loc[("000001.SZ", "2024-01-02"), "upper_limit"]))
        self.assertFalse(bool(rows.loc[("000001.SZ", "2024-01-03"), "tradable"]))
        self.assertFalse(bool(rows.loc[("000001.SZ", "2024-01-03"), "upper_limit"]))
        self.assertTrue(bool(rows.loc[("000002.SZ", "2024-01-02"), "is_st"]))
        self.assertTrue(bool(rows.loc[("000002.SZ", "2024-01-02"), "upper_limit"]))
        self.assertEqual(audit["lifecycle_rows"], 3)
        self.assertEqual(audit["tradable_rows"], 2)
        self.assertEqual(audit["upper_limit_true_rows"], 2)

    def test_explicit_no_limit_override_forces_boolean_false(self):
        lifecycle = pd.DataFrame([
            {"symbol": "000995.SZ", "date": "2020-12-16", "isST": 0},
        ])
        reference = pd.DataFrame([
            {"symbol": "000995.SZ", "date": "2020-12-16", "close": 5.50, "reference_close_cny": 5.00},
        ])
        panel, _ = sut.build_status_panel(
            lifecycle,
            reference,
            ipo_map={"000995.SZ": "2000-08-07"},
            special_no_limit_dates={("000995.SZ", "2020-12-16")},
        )
        self.assertTrue(bool(panel.iloc[0]["tradable"]))
        self.assertFalse(bool(panel.iloc[0]["upper_limit"]))

    def test_informal_ipo_rank_handles_first_day_and_first_five(self):
        dates = ["2023-04-10", "2023-04-11", "2023-04-12", "2023-04-13", "2023-04-14", "2023-04-17"]
        lifecycle = pd.DataFrame([
            {"symbol": "001286.SZ", "date": day, "isST": 0} for day in dates
        ])
        reference = pd.DataFrame([
            {"symbol": "001286.SZ", "date": day, "close": 10.00, "reference_close_cny": 9.09} for day in dates
        ])
        panel, _ = sut.build_status_panel(
            lifecycle,
            reference,
            ipo_map={"001286.SZ": "2023-04-10"},
            special_no_limit_dates=set(),
        )
        self.assertEqual(panel["listing_trade_rank"].tolist(), [1, 2, 3, 4, 5, 6])
        self.assertFalse(panel.iloc[:5]["upper_limit"].any())
        self.assertTrue(bool(panel.iloc[5]["upper_limit"]))

    def test_fails_closed_on_duplicate_reference_or_reference_outside_lifecycle(self):
        lifecycle = pd.DataFrame([
            {"symbol": "000001.SZ", "date": "2024-01-02", "isST": 0},
        ])
        duplicate = pd.DataFrame([
            {"symbol": "000001.SZ", "date": "2024-01-02", "close": 11.00, "reference_close_cny": 10.00},
            {"symbol": "000001.SZ", "date": "2024-01-02", "close": 11.00, "reference_close_cny": 10.00},
        ])
        with self.assertRaises(ValueError):
            sut.build_status_panel(lifecycle, duplicate, {"000001.SZ": "1991-04-03"}, set())

        outside = pd.DataFrame([
            {"symbol": "000002.SZ", "date": "2024-01-02", "close": 11.00, "reference_close_cny": 10.00},
        ])
        with self.assertRaises(ValueError):
            sut.build_status_panel(lifecycle, outside, {"000001.SZ": "1991-04-03", "000002.SZ": "1991-01-29"}, set())


if __name__ == "__main__":
    unittest.main()
