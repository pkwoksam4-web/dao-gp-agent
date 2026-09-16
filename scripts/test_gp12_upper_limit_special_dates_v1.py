from __future__ import annotations

import unittest

import gp12_upper_limit_special_dates_v1 as sut


class UpperLimitSpecialDatesTests(unittest.TestCase):
    def test_exact_evidence_dates_are_special_no_limit(self):
        expected = {
            ("000670.SZ", "2022-08-22"),
            ("000792.SZ", "2021-08-10"),
            ("000995.SZ", "2020-12-16"),
            ("001267.SZ", "2021-11-17"),
            ("001289.SZ", "2022-01-24"),
            ("600190.SH", "2025-06-30"),
            ("600200.SH", "2025-12-09"),
            ("600387.SH", "2025-06-16"),
            ("600462.SH", "2025-06-24"),
        }
        self.assertEqual(sut.special_no_limit_keys(), expected)
        for symbol, trade_date in expected:
            self.assertTrue(sut.is_special_no_limit(symbol, trade_date))
            evidence = sut.special_no_limit_evidence(symbol, trade_date)
            self.assertEqual(evidence["symbol"], symbol)
            self.assertEqual(evidence["date"], trade_date)
            self.assertTrue(evidence["source_url"].startswith("https://"))
            self.assertIn(evidence["event_type"], {
                "RESUME_LISTING_FIRST_DAY",
                "RELISTING_FIRST_DAY",
                "ABSORPTION_MERGER_LISTING_FIRST_DAY",
                "DELISTING_PERIOD_FIRST_DAY",
            })

    def test_adjacent_and_unknown_dates_do_not_match(self):
        self.assertFalse(sut.is_special_no_limit("000670.SZ", "2022-08-23"))
        self.assertFalse(sut.is_special_no_limit("600190.SH", "2025-07-01"))
        self.assertFalse(sut.is_special_no_limit("000001.SZ", "2024-01-02"))

    def test_unknown_evidence_fails_closed(self):
        with self.assertRaises(KeyError):
            sut.special_no_limit_evidence("000001.SZ", "2024-01-02")

    def test_registry_contains_only_exchange_or_issuer_primary_sources(self):
        for row in sut.special_no_limit_registry():
            host = row["source_url"]
            self.assertTrue(
                "szse.cn" in host or "sse.com.cn" in host,
                row,
            )
            self.assertEqual(row["evidence_status"], "PRIMARY_SOURCE_VERIFIED")


if __name__ == "__main__":
    unittest.main()
