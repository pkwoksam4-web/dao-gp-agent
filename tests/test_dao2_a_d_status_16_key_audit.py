from __future__ import annotations

import unittest

from scripts.dao2_a_d_status_16_key_audit import classify_key, to_baostock_code


class DStatusResidualAuditTests(unittest.TestCase):
    def test_symbol_conversion_matches_frozen_d_semantics(self):
        self.assertEqual(to_baostock_code("000157.SZ"), "sz.000157")
        self.assertEqual(to_baostock_code("600306.SH"), "sh.600306")

    def test_present_tradable_row_is_not_na(self):
        result = classify_key(
            trade_date="2021-09-24",
            formal_amount_cny=737075800,
            status_row={"date":"2021-09-24","code":"sz.000157","tradestatus":"1","isST":"0"},
            basic_rows=[{"ipoDate":"2000-04-27","outDate":""}],
        )
        self.assertEqual(result["classification"], "D_STATUS_VALID_TRADABLE")
        self.assertFalse(result["na_allowed"])
        self.assertFalse(result["expected_axis_review_required"])

    def test_nontradable_status_with_nonzero_formal_turnover_is_conflict(self):
        result = classify_key(
            trade_date="2021-09-24",
            formal_amount_cny=1000,
            status_row={"date":"2021-09-24","code":"sz.000157","tradestatus":"0","isST":"0"},
            basic_rows=[{"ipoDate":"2000-04-27","outDate":""}],
        )
        self.assertEqual(result["classification"], "EXPECTED_AXIS_EVIDENCE_CONFLICT")
        self.assertTrue(result["expected_axis_review_required"])
        self.assertFalse(result["na_allowed"])

    def test_absent_status_row_with_nonzero_formal_turnover_is_conflict_not_na(self):
        result = classify_key(
            trade_date="2021-09-24",
            formal_amount_cny=1000,
            status_row=None,
            basic_rows=[{"ipoDate":"2000-04-27","outDate":""}],
        )
        self.assertEqual(result["classification"], "EXPECTED_AXIS_EVIDENCE_CONFLICT")
        self.assertTrue(result["expected_axis_review_required"])
        self.assertFalse(result["na_allowed"])

    def test_outside_lifecycle_with_nonzero_formal_turnover_is_conflict_not_auto_na(self):
        result = classify_key(
            trade_date="2020-06-08",
            formal_amount_cny=314500,
            status_row=None,
            basic_rows=[{"ipoDate":"2021-01-01","outDate":""}],
        )
        self.assertEqual(result["classification"], "EXPECTED_AXIS_EVIDENCE_CONFLICT")
        self.assertEqual(result["lifecycle_status"], "OUTSIDE_LIFECYCLE")
        self.assertFalse(result["na_allowed"])

    def test_st_row_remains_valid_status_evidence_not_automatic_exclusion(self):
        result = classify_key(
            trade_date="2021-02-24",
            formal_amount_cny=534300,
            status_row={"date":"2021-02-24","code":"sh.603996","tradestatus":"1","isST":"1"},
            basic_rows=[{"ipoDate":"2016-12-22","outDate":""}],
        )
        self.assertEqual(result["classification"], "D_STATUS_VALID_TRADABLE")
        self.assertTrue(result["is_st"])
        self.assertFalse(result["na_allowed"])


if __name__ == "__main__":
    unittest.main()
