from __future__ import annotations

import json
import unittest
from unittest import mock

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

    def test_plan_chunks_is_stable_and_non_overlapping(self):
        chunks = sut.plan_chunks("2020-06-01", "2020-09-01", max_calendar_days=90)
        self.assertEqual(chunks, [("2020-06-01", "2020-08-29"), ("2020-08-30", "2020-09-01")])

    def test_select_shard_partitions_without_overlap(self):
        symbols = [f"{i:06d}.SZ" for i in range(17)]
        shards = [sut.select_shard(symbols, i, 4) for i in range(4)]
        flattened = [symbol for shard in shards for symbol in shard]
        self.assertEqual(sorted(flattened), sorted(symbols))
        self.assertEqual(len(flattened), len(set(flattened)))

    def test_audit_expected_dates_fails_closed_on_missing_extra_or_duplicate(self):
        good = [
            {"symbol": "000001.SZ", "date": "2024-01-02"},
            {"symbol": "000001.SZ", "date": "2024-01-03"},
        ]
        audit = sut.audit_expected_dates("000001.SZ", ["2024-01-02", "2024-01-03"], good)
        self.assertEqual(audit["status"], "PASS_EXACT_DATES")
        self.assertEqual(audit["duplicate_dates_n"], 0)
        bad = good + [{"symbol": "000001.SZ", "date": "2024-01-03"}]
        audit = sut.audit_expected_dates("000001.SZ", ["2024-01-02", "2024-01-03"], bad)
        self.assertEqual(audit["status"], "REVIEW_DATE_AXIS")
        self.assertEqual(audit["duplicate_dates_n"], 1)

    def test_fetch_symbol_reference_propagates_source_failure(self):
        with mock.patch.object(sut, "fetch_chunk_reference", side_effect=RuntimeError("source down")):
            with self.assertRaisesRegex(RuntimeError, "source down"):
                sut.fetch_symbol_reference(
                    "000001.SZ", "2024-01-02", "2024-01-03",
                    max_calendar_days=90, retries=1, delay=0,
                )

    def test_resilient_split_recovers_wide_range_failure(self):
        def fake_fetch(symbol, start, end, **kwargs):
            if (start, end) == ("2024-01-01", "2024-01-04"):
                raise RuntimeError("wide request failed")
            return [
                {"symbol": symbol, "date": day}
                for day in ("2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04")
                if start <= day <= end
            ]

        with mock.patch.object(sut, "fetch_chunk_reference", side_effect=fake_fetch):
            rows, meta = sut.fetch_chunk_reference_resilient(
                "000001.SZ", "2024-01-01", "2024-01-04", retries=1
            )
        self.assertEqual([row["date"] for row in rows], [
            "2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"
        ])
        self.assertEqual(meta["split_recovery_n"], 1)
        self.assertEqual(meta["leaf_chunk_n"], 2)

    def test_resilient_single_day_failure_stays_hard_failure(self):
        with mock.patch.object(sut, "fetch_chunk_reference", side_effect=RuntimeError("single day failed")):
            with self.assertRaisesRegex(RuntimeError, "single day failed"):
                sut.fetch_chunk_reference_resilient(
                    "000001.SZ", "2024-01-02", "2024-01-02", retries=1
                )


if __name__ == "__main__":
    unittest.main()
