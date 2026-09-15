from __future__ import annotations

import unittest

import gp12_baostock_turnover_v1 as mod


class BaoStockTurnoverContractTests(unittest.TestCase):
    def test_symbol_mapping_is_exchange_qualified(self):
        self.assertEqual(mod.symbol_to_baostock_code("000001.SZ"), "sz.000001")
        self.assertEqual(mod.symbol_to_baostock_code("600000.SH"), "sh.600000")
        with self.assertRaises(ValueError):
            mod.symbol_to_baostock_code("000001")

    def test_active_trade_turn_percent_converts_to_decimal(self):
        row = {"date": "2026-04-17", "code": "sz.000001", "turn": "2.500000", "tradestatus": "1"}
        out = mod.parse_baostock_row("000001.SZ", row)
        self.assertEqual(out, {"date": "2026-04-17", "turnover_ratio": 0.025})

    def test_nontrading_row_is_ignored(self):
        row = {"date": "2026-04-17", "code": "sz.000001", "turn": "", "tradestatus": "0"}
        self.assertIsNone(mod.parse_baostock_row("000001.SZ", row))

    def test_active_trade_blank_zero_or_bad_turn_fails_closed(self):
        for value in ("", "0", "0.0", "nan", "bad"):
            with self.subTest(turn=value):
                row = {"date": "2026-04-17", "code": "sz.000001", "turn": value, "tradestatus": "1"}
                with self.assertRaises(ValueError):
                    mod.parse_baostock_row("000001.SZ", row)

    def test_payload_code_mismatch_fails_closed(self):
        row = {"date": "2026-04-17", "code": "sh.600000", "turn": "1.0", "tradestatus": "1"}
        with self.assertRaisesRegex(ValueError, "code mismatch"):
            mod.parse_baostock_row("000001.SZ", row)

    def test_exact_date_audit_and_session_close_pit(self):
        expected = ["2020-06-01", "2020-06-02"]
        rows = [
            {"date": "2020-06-01", "turnover_ratio": 0.01},
            {"date": "2020-06-02", "turnover_ratio": 0.02},
        ]
        out = mod.audit_symbol_rows("000001.SZ", expected, rows)
        self.assertTrue(out["symbol_pass"])
        self.assertTrue(out["coverage_exact"])
        self.assertEqual(out["known_at_first"], "2020-06-01T15:00:00+08:00")
        self.assertFalse(out["same_session_turnover_usable_before_close"])
        self.assertFalse(out["historical_provider_publication_timestamp_proven"])

    def test_materialized_rows_include_source_and_known_at(self):
        rows = [{"date": "2020-06-01", "turnover_ratio": 0.0123}]
        out = mod.materialize_rows("000001.SZ", rows)
        self.assertEqual(out, [{
            "symbol": "000001.SZ",
            "date": "2020-06-01",
            "turnover_ratio": 0.0123,
            "known_at": "2020-06-01T15:00:00+08:00",
            "source": "BAOSTOCK_TURN_DAILY_UNADJUSTED",
        }])

    def test_full_summary_requires_844_exact_rows_and_panel(self):
        records = [
            {"symbol": f"X{i:03d}.SZ", "symbol_pass": True, "row_n": 10, "blockers": []}
            for i in range(844)
        ]
        out = mod.summarize_full_audit(records, expected_trade_rows=8440, materialized_rows=8440)
        self.assertTrue(out["turnover_ratio_candidate_pit_verified"])
        self.assertTrue(out["panel_complete"])
        self.assertEqual(out["pass_n"], 844)
        self.assertEqual(out["fail_n"], 0)
        self.assertEqual(out["blockers"], [])

        bad = mod.summarize_full_audit(records, expected_trade_rows=8440, materialized_rows=8439)
        self.assertFalse(bad["turnover_ratio_candidate_pit_verified"])
        self.assertFalse(bad["panel_complete"])
        self.assertIn("TURNOVER_PANEL_ROW_COVERAGE_MISMATCH", bad["blockers"])

    def test_candidate_source_semantics_never_claim_historical_recovery(self):
        meta = mod.provider_metadata()
        self.assertEqual(meta["provider"], "BaoStock")
        self.assertEqual(meta["field"], "turn")
        self.assertEqual(meta["source_unit"], "percent")
        self.assertEqual(meta["candidate_unit"], "decimal_ratio")
        self.assertEqual(meta["adjustflag"], "3")
        self.assertEqual(meta["origin"], "NEW_RECONSTRUCTION_CANDIDATE")
        self.assertFalse(meta["historical_gp_v11_source_recovered"])
        self.assertFalse(meta["historical_provider_publication_timestamp_proven"])


if __name__ == "__main__":
    unittest.main()
