from __future__ import annotations

import unittest

import gp12_turnover_ratio_v1 as mod


class TurnoverRatioContractTests(unittest.TestCase):
    def test_parse_eastmoney_f61_percent_to_decimal(self):
        payload = {
            "data": {
                "code": "000001",
                "name": "平安银行",
                "klines": [
                    "2026-04-17,10.00,10.10,10.20,9.90,12345,98765432,3.00,1.00,0.10,2.50"
                ],
            }
        }
        rows, meta = mod.parse_turnover_payload("000001.SZ", payload)
        self.assertEqual(rows, [{"date": "2026-04-17", "turnover_ratio": 0.025}])
        self.assertEqual(meta["payload_code"], "000001")
        self.assertEqual(meta["field"], "f61")
        self.assertEqual(meta["source_unit"], "percent")
        self.assertEqual(meta["candidate_unit"], "decimal_ratio")

    def test_empty_historical_kline_is_source_failure_not_date_gap(self):
        payload = {
            "data": {
                "code": "000532",
                "name": "华金资本",
                "klines": [],
            }
        }
        with self.assertRaisesRegex(ValueError, "no historical klines"):
            mod.parse_turnover_payload("000532.SZ", payload)

    def test_exact_trade_date_coverage_and_session_close_pit_pass(self):
        expected = ["2020-06-01", "2020-06-02", "2020-06-03"]
        rows = [
            {"date": "2020-06-01", "turnover_ratio": 0.012},
            {"date": "2020-06-02", "turnover_ratio": 0.009},
            {"date": "2020-06-03", "turnover_ratio": 0.015},
        ]
        out = mod.audit_symbol_rows("000001.SZ", expected, rows)
        self.assertTrue(out["coverage_exact"])
        self.assertTrue(out["pit_policy_valid"])
        self.assertTrue(out["symbol_pass"])
        self.assertEqual(out["known_at_first"], "2020-06-01T15:00:00+08:00")
        self.assertFalse(out["historical_provider_publication_timestamp_proven"])
        self.assertEqual(out["blockers"], [])

    def test_missing_extra_duplicate_or_nonpositive_turnover_fails_closed(self):
        expected = ["2020-06-01", "2020-06-02"]
        cases = [
            ([{"date": "2020-06-01", "turnover_ratio": 0.01}], "TURNOVER_DATE_GAP"),
            ([
                {"date": "2020-06-01", "turnover_ratio": 0.01},
                {"date": "2020-06-02", "turnover_ratio": 0.02},
                {"date": "2020-06-03", "turnover_ratio": 0.03},
            ], "TURNOVER_EXTRA_DATE"),
            ([
                {"date": "2020-06-01", "turnover_ratio": 0.01},
                {"date": "2020-06-01", "turnover_ratio": 0.02},
            ], "TURNOVER_DUPLICATE_DATE"),
            ([
                {"date": "2020-06-01", "turnover_ratio": 0.01},
                {"date": "2020-06-02", "turnover_ratio": 0.0},
            ], "TURNOVER_INVALID_VALUE"),
        ]
        for rows, blocker in cases:
            with self.subTest(blocker=blocker):
                out = mod.audit_symbol_rows("000001.SZ", expected, rows)
                self.assertFalse(out["symbol_pass"])
                self.assertIn(blocker, out["blockers"])

    def test_formal_partition_requires_844_pass_and_exact_three_na(self):
        records = [
            {"symbol": f"X{i:03d}.SZ", "symbol_pass": True, "row_n": 10, "blockers": []}
            for i in range(844)
        ]
        out = mod.summarize_formal_audit(
            records,
            universe_n=847,
            na_symbols=["600074.SH", "600485.SH", "600677.SH"],
            expected_trade_rows=8440,
        )
        self.assertTrue(out["turnover_ratio_candidate_pit_verified"])
        self.assertEqual(out["formal_symbol_n"], 844)
        self.assertEqual(out["pass_n"], 844)
        self.assertEqual(out["fail_n"], 0)
        self.assertEqual(out["observed_turnover_rows"], 8440)
        self.assertEqual(out["blockers"], [])

        bad = mod.summarize_formal_audit(
            records[:-1],
            universe_n=847,
            na_symbols=["600074.SH", "600485.SH", "600677.SH"],
            expected_trade_rows=8440,
        )
        self.assertFalse(bad["turnover_ratio_candidate_pit_verified"])
        self.assertIn("TURNOVER_FORMAL_SYMBOL_COVERAGE_INCOMPLETE", bad["blockers"])
        self.assertIn("TURNOVER_TOTAL_ROW_COVERAGE_MISMATCH", bad["blockers"])

    def test_repair_replaces_only_failed_records_with_passing_retry(self):
        base = [
            {"symbol": "000001.SZ", "symbol_pass": True, "row_n": 3, "blockers": []},
            {"symbol": "000002.SZ", "symbol_pass": False, "row_n": 0, "blockers": ["TURNOVER_SOURCE_FETCH_FAILED"]},
            {"symbol": "000004.SZ", "symbol_pass": False, "row_n": 0, "blockers": ["TURNOVER_SOURCE_FETCH_FAILED"]},
        ]
        repair = [
            {"symbol": "000001.SZ", "symbol_pass": False, "row_n": 0, "blockers": ["TURNOVER_SOURCE_FETCH_FAILED"]},
            {"symbol": "000002.SZ", "symbol_pass": True, "row_n": 4, "blockers": []},
            {"symbol": "000004.SZ", "symbol_pass": False, "row_n": 0, "blockers": ["TURNOVER_SOURCE_FETCH_FAILED"]},
        ]
        merged = mod.merge_repair_records(base, repair)
        by_symbol = {r["symbol"]: r for r in merged["records"]}
        self.assertTrue(by_symbol["000001.SZ"]["symbol_pass"])
        self.assertEqual(by_symbol["000001.SZ"]["row_n"], 3)
        self.assertTrue(by_symbol["000002.SZ"]["symbol_pass"])
        self.assertEqual(by_symbol["000002.SZ"]["row_n"], 4)
        self.assertFalse(by_symbol["000004.SZ"]["symbol_pass"])
        self.assertEqual(merged["repaired_n"], 1)
        self.assertEqual(merged["unresolved_symbols"], ["000004.SZ"])

    def test_repair_rejects_duplicate_or_unknown_symbols(self):
        base = [
            {"symbol": "000001.SZ", "symbol_pass": False, "row_n": 0, "blockers": ["TURNOVER_SOURCE_FETCH_FAILED"]},
        ]
        with self.assertRaisesRegex(ValueError, "duplicate repair symbol"):
            mod.merge_repair_records(base, [
                {"symbol": "000001.SZ", "symbol_pass": True, "row_n": 1, "blockers": []},
                {"symbol": "000001.SZ", "symbol_pass": True, "row_n": 1, "blockers": []},
            ])
        with self.assertRaisesRegex(ValueError, "unknown repair symbol"):
            mod.merge_repair_records(base, [
                {"symbol": "000002.SZ", "symbol_pass": True, "row_n": 1, "blockers": []},
            ])


if __name__ == "__main__":
    unittest.main()
