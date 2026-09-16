from __future__ import annotations

import unittest

import pandas as pd

import gp12_status_panel_v1 as sut


class StatusPanelContractTests(unittest.TestCase):
    def _lifecycle(self):
        return pd.DataFrame([
            {"symbol": "000001.SZ", "date": "2024-01-02", "isST": 0},
            {"symbol": "000002.SZ", "date": "2024-01-02", "isST": 1},
            {"symbol": "300001.SZ", "date": "2024-01-02", "isST": 0},
            {"symbol": "001369.SZ", "date": "2025-12-30", "isST": 0},
            {"symbol": "000670.SZ", "date": "2022-08-22", "isST": 0},
            {"symbol": "000001.SZ", "date": "2024-01-03", "isST": 0},
        ])

    def _trade(self):
        return pd.DataFrame([
            {"symbol": "000001.SZ", "date": "2024-01-02", "close": 11.00},
            {"symbol": "000002.SZ", "date": "2024-01-02", "close": 10.50},
            {"symbol": "300001.SZ", "date": "2024-01-02", "close": 12.00},
            {"symbol": "001369.SZ", "date": "2025-12-30", "close": 19.68},
            {"symbol": "000670.SZ", "date": "2022-08-22", "close": 2.42},
        ])

    def _reference(self):
        return pd.DataFrame([
            {"symbol": "000001.SZ", "date": "2024-01-02", "close": 11.00, "reference_close_cny": 10.00},
            {"symbol": "000002.SZ", "date": "2024-01-02", "close": 10.50, "reference_close_cny": 10.00},
            {"symbol": "300001.SZ", "date": "2024-01-02", "close": 12.00, "reference_close_cny": 10.00},
            {"symbol": "001369.SZ", "date": "2025-12-30", "close": 19.68, "reference_close_cny": 15.20},
            {"symbol": "000670.SZ", "date": "2022-08-22", "close": 2.42, "reference_close_cny": 2.10},
        ])

    def _basics(self):
        return {
            "000001.SZ": {"ipoDate": "1991-04-03"},
            "000002.SZ": {"ipoDate": "1991-01-29"},
            "300001.SZ": {"ipoDate": "2009-10-30"},
            "001369.SZ": {"ipoDate": "2025-12-30"},
            "000670.SZ": {"ipoDate": "1996-12-17"},
        }

    def _special(self):
        return {("000670.SZ", "2022-08-22")}

    def test_build_panel_applies_board_st_ipo_and_special_rules(self):
        panel, audit = sut.build_status_panel(
            self._lifecycle(), self._trade(), self._reference(), self._basics(), self._special()
        )
        by_key = panel.set_index(["symbol", "date"])

        mature = by_key.loc[("000001.SZ", "2024-01-02")]
        self.assertTrue(mature["tradable"])
        self.assertEqual(mature["limit_pct_percent"], 10.0)
        self.assertEqual(mature["limit_price_cny"], 11.0)
        self.assertTrue(mature["upper_limit"])

        st = by_key.loc[("000002.SZ", "2024-01-02")]
        self.assertEqual(st["limit_pct_percent"], 5.0)
        self.assertEqual(st["limit_price_cny"], 10.5)
        self.assertTrue(st["upper_limit"])

        chinext = by_key.loc[("300001.SZ", "2024-01-02")]
        self.assertEqual(chinext["limit_pct_percent"], 20.0)
        self.assertTrue(chinext["upper_limit"])

        registered_ipo = by_key.loc[("001369.SZ", "2025-12-30")]
        self.assertIsNone(registered_ipo["limit_pct_percent"])
        self.assertIsNone(registered_ipo["limit_price_cny"])
        self.assertFalse(registered_ipo["upper_limit"])
        self.assertEqual(registered_ipo["listing_trade_rank"], 1)

        special = by_key.loc[("000670.SZ", "2022-08-22")]
        self.assertTrue(special["special_no_limit"])
        self.assertIsNone(special["limit_pct_percent"])
        self.assertFalse(special["upper_limit"])

        nontrade = by_key.loc[("000001.SZ", "2024-01-03")]
        self.assertFalse(nontrade["tradable"])
        self.assertFalse(nontrade["upper_limit"])
        self.assertIsNone(nontrade["limit_pct_percent"])
        self.assertIsNone(nontrade["limit_price_cny"])

        self.assertEqual(audit["status"], "PASS_EXACT_STATUS_PANEL")
        self.assertEqual(audit["lifecycle_rows"], 6)
        self.assertEqual(audit["tradable_rows"], 5)
        self.assertEqual(audit["nontradable_rows"], 1)
        self.assertEqual(audit["special_no_limit_rows"], 1)

    def test_listing_rank_is_constructed_only_for_formal_window_ipos(self):
        panel, _ = sut.build_status_panel(
            self._lifecycle(), self._trade(), self._reference(), self._basics(), self._special()
        )
        by_key = panel.set_index(["symbol", "date"])
        self.assertTrue(pd.isna(by_key.loc[("000001.SZ", "2024-01-02"), "listing_trade_rank"]))
        self.assertEqual(by_key.loc[("001369.SZ", "2025-12-30"), "listing_trade_rank"], 1)

    def test_missing_reference_trade_key_fails_closed(self):
        reference = self._reference().query("not (symbol == '000001.SZ' and date == '2024-01-02')")
        with self.assertRaisesRegex(ValueError, "reference key mismatch"):
            sut.build_status_panel(
                self._lifecycle(), self._trade(), reference, self._basics(), self._special()
            )

    def test_reference_close_field_must_match_pinned_trade_close(self):
        reference = self._reference().copy()
        reference.loc[0, "close"] = 10.99
        with self.assertRaisesRegex(ValueError, "close mismatch"):
            sut.build_status_panel(
                self._lifecycle(), self._trade(), reference, self._basics(), self._special()
            )

    def test_duplicate_lifecycle_key_fails_closed(self):
        lifecycle = pd.concat([self._lifecycle(), self._lifecycle().iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate lifecycle"):
            sut.build_status_panel(
                lifecycle, self._trade(), self._reference(), self._basics(), self._special()
            )

    def test_duplicate_trade_or_reference_key_fails_closed(self):
        trade = pd.concat([self._trade(), self._trade().iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate trade"):
            sut.build_status_panel(
                self._lifecycle(), trade, self._reference(), self._basics(), self._special()
            )
        reference = pd.concat([self._reference(), self._reference().iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate reference"):
            sut.build_status_panel(
                self._lifecycle(), self._trade(), reference, self._basics(), self._special()
            )

    def test_missing_basic_metadata_fails_closed(self):
        basics = self._basics().copy()
        basics.pop("300001.SZ")
        with self.assertRaisesRegex(ValueError, "missing basic"):
            sut.build_status_panel(
                self._lifecycle(), self._trade(), self._reference(), basics, self._special()
            )

    def test_special_key_outside_lifecycle_fails_closed(self):
        special = self._special() | {("000001.SZ", "2024-02-01")}
        with self.assertRaisesRegex(ValueError, "special key outside lifecycle"):
            sut.build_status_panel(
                self._lifecycle(), self._trade(), self._reference(), self._basics(), special
            )


if __name__ == "__main__":
    unittest.main()
