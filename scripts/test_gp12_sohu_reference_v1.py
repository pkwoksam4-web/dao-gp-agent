from __future__ import annotations

import json
import unittest

import gp12_sohu_reference_v1 as sut


class SohuReferenceContractTests(unittest.TestCase):
    def _payload(self, row):
        obj = [{"status": 0, "hq": [row]}]
        return ("historySearchHandler(" + json.dumps(obj, ensure_ascii=False) + ")").encode("utf-8")

    def test_parser_retains_change_pct_turnover_and_exact_reference(self):
        raw = self._payload([
            "2023-06-21", "5.61", "5.61", "0.51", "10.00%",
            "5.61", "5.61", "48540", "2723.07", "0.78%",
        ])
        rows = sut.parse_hishq_reference_bytes("000790.SZ", raw)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["symbol"], "000790.SZ")
        self.assertEqual(row["date"], "2023-06-21")
        self.assertEqual(row["close"], 5.61)
        self.assertEqual(row["change_cny"], 0.51)
        self.assertEqual(row["pct_percent"], 10.00)
        self.assertEqual(row["turnover_percent"], 0.78)
        self.assertEqual(row["reference_close_cny"], 5.10)

    def test_negative_change_recovers_rights_issue_reference(self):
        raw = self._payload([
            "2023-12-08", "29.99", "27.35", "-1.89", "-6.46%",
            "26.61", "30.00", "90572", "24883.18", "3.03%",
        ])
        row = sut.parse_hishq_reference_bytes("000049.SZ", raw)[0]
        self.assertEqual(row["reference_close_cny"], 29.24)
        self.assertEqual(row["change_cny"], -1.89)

    def test_reference_arithmetic_is_decimal_half_up_not_binary_float(self):
        self.assertEqual(sut.reference_close_cny("1.90", "-0.09"), 1.99)
        self.assertEqual(sut.limit_price_cny("1.90", "5.00"), 2.00)
        self.assertEqual(sut.limit_price_cny("15.35", "10.00"), 16.89)

    def test_malformed_percentage_fails_closed(self):
        raw = self._payload([
            "2024-01-02", "9.39", "9.21", "-0.18", "BAD",
            "9.21", "9.42", "1158366", "107574.22", "0.60%",
        ])
        with self.assertRaises(ValueError):
            sut.parse_hishq_reference_bytes("000001.SZ", raw)


if __name__ == "__main__":
    unittest.main()
