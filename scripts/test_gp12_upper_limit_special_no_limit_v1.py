from __future__ import annotations

import unittest

import gp12_upper_limit_special_no_limit_v1 as sut


EXPECTED = {
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


class UpperLimitSpecialNoLimitEvidenceTests(unittest.TestCase):
    def test_default_evidence_has_exact_nine_verified_keys(self):
        evidence = sut.load_evidence()
        keys = {(row["symbol"], row["date"]) for row in evidence}
        self.assertEqual(keys, EXPECTED)
        self.assertEqual(len(evidence), len(EXPECTED))

    def test_every_row_has_explicit_official_evidence_and_event_type(self):
        evidence = sut.load_evidence()
        allowed_events = {
            "RESTORED_LISTING_FIRST_DAY",
            "RELISTING_FIRST_DAY",
            "MERGER_LISTING_FIRST_DAY",
            "DELISTING_ARRANGEMENT_FIRST_DAY",
        }
        for row in evidence:
            self.assertIn(row["event_type"], allowed_events)
            self.assertIn(row["source_authority"], {"SZSE", "SSE", "CNINFO"})
            self.assertTrue(row["evidence_url"].startswith("https://"))
            self.assertTrue(row["evidence_statement"])

    def test_lookup_is_exact_and_does_not_expand_to_adjacent_dates(self):
        evidence = sut.load_evidence()
        for symbol, trade_date in EXPECTED:
            self.assertTrue(sut.is_special_no_limit(symbol, trade_date, evidence=evidence))
        self.assertFalse(sut.is_special_no_limit("000670.SZ", "2022-08-23", evidence=evidence))
        self.assertFalse(sut.is_special_no_limit("600190.SH", "2025-07-01", evidence=evidence))
        self.assertFalse(sut.is_special_no_limit("000001.SZ", "2022-08-22", evidence=evidence))

    def test_loader_rejects_duplicate_symbol_date(self):
        row = {
            "symbol": "000670.SZ",
            "date": "2022-08-22",
            "event_type": "RESTORED_LISTING_FIRST_DAY",
            "source_authority": "CNINFO",
            "evidence_url": "https://example.invalid/a",
            "evidence_statement": "x",
        }
        with self.assertRaisesRegex(ValueError, "duplicate"):
            sut.validate_evidence([row, dict(row)])


if __name__ == "__main__":
    unittest.main()
