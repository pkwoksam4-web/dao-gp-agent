from __future__ import annotations

import unittest

import gp12_upper_limit_rule_v1 as sut


class UpperLimitRuleTests(unittest.TestCase):
    def test_mainboard_registration_ipo_first_five_are_no_limit(self):
        for rank in range(1, 6):
            self.assertIsNone(sut.limit_percent(
                "001286.SZ", "2023-04-10", False,
                ipo_date="2023-04-10", listing_trade_rank=rank,
            ))
        self.assertEqual(sut.limit_percent(
            "001286.SZ", "2023-04-17", False,
            ipo_date="2023-04-10", listing_trade_rank=6,
        ), 10.0)

    def test_legacy_mainboard_ipo_first_day_is_44_percent(self):
        self.assertEqual(sut.limit_percent(
            "001267.SZ", "2021-11-17", False,
            ipo_date="2021-11-17", listing_trade_rank=1,
        ), 44.0)
        self.assertEqual(sut.limit_percent(
            "001267.SZ", "2021-11-18", False,
            ipo_date="2021-11-17", listing_trade_rank=2,
        ), 10.0)

    def test_chinext_reform_switch(self):
        self.assertEqual(sut.limit_percent(
            "300123.SZ", "2020-08-21", False,
            ipo_date="2010-01-01", listing_trade_rank=None,
        ), 10.0)
        self.assertEqual(sut.limit_percent(
            "300123.SZ", "2020-08-21", True,
            ipo_date="2010-01-01", listing_trade_rank=None,
        ), 5.0)
        self.assertEqual(sut.limit_percent(
            "300123.SZ", "2020-08-24", True,
            ipo_date="2010-01-01", listing_trade_rank=None,
        ), 20.0)
        for rank in range(1, 6):
            self.assertIsNone(sut.limit_percent(
                "300999.SZ", "2020-08-24", False,
                ipo_date="2020-08-24", listing_trade_rank=rank,
            ))

    def test_star_first_five_no_limit_then_20(self):
        self.assertIsNone(sut.limit_percent(
            "688086.SH", "2020-01-01", False,
            ipo_date="2020-01-01", listing_trade_rank=1,
        ))
        self.assertEqual(sut.limit_percent(
            "688086.SH", "2020-01-10", False,
            ipo_date="2020-01-01", listing_trade_rank=6,
        ), 20.0)

    def test_mainboard_st_is_5_percent_through_formal_end(self):
        self.assertEqual(sut.limit_percent(
            "600001.SH", "2026-04-17", True,
            ipo_date="1990-01-01", listing_trade_rank=None,
        ), 5.0)
        self.assertEqual(sut.limit_percent(
            "000001.SZ", "2026-04-17", True,
            ipo_date="1990-01-01", listing_trade_rank=None,
        ), 5.0)

    def test_explicit_special_no_limit_date_overrides_normal_regime(self):
        self.assertIsNone(sut.limit_percent(
            "000995.SZ", "2020-12-16", False,
            ipo_date="2000-08-07", listing_trade_rank=None,
            special_no_limit=True,
        ))

    def test_decimal_limit_price_and_boolean(self):
        self.assertEqual(sut.limit_price_cny("1.90", 5.0), 2.00)
        self.assertTrue(sut.is_upper_limit("2.00", "1.90", 5.0))
        self.assertFalse(sut.is_upper_limit("1.99", "1.90", 5.0))
        self.assertFalse(sut.is_upper_limit("99.00", "1.90", None))

    def test_unknown_board_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unsupported board"):
            sut.limit_percent(
                "900001.SH", "2024-01-02", False,
                ipo_date="1990-01-01", listing_trade_rank=None,
            )


if __name__ == "__main__":
    unittest.main()
