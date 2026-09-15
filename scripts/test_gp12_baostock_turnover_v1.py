from __future__ import annotations

import json
import pathlib
import unittest

import gp12_baostock_turnover_v1 as mod


ROOT = pathlib.Path(__file__).resolve().parent.parent
RESIDUAL_BINDING_PATH = ROOT / "data" / "GP12_CANDIDATE_TURNOVER_RESIDUAL_DENOMINATORS_V1.json"


class BaoStockTurnoverContractTests(unittest.TestCase):
    def test_symbol_mapping_is_exchange_qualified(self):
        self.assertEqual(mod.symbol_to_baostock_code("000001.SZ"), "sz.000001")
        self.assertEqual(mod.symbol_to_baostock_code("600000.SH"), "sh.600000")
        with self.assertRaises(ValueError):
            mod.symbol_to_baostock_code("000001")

    def test_query_contract_requests_trade_evidence_for_status_override(self):
        self.assertEqual(
            mod.BAOSTOCK_QUERY_FIELDS,
            "date,code,volume,amount,turn,tradestatus",
        )

    def test_active_trade_turn_percent_converts_to_decimal(self):
        row = {"date": "2026-04-17", "code": "sz.000001", "turn": "2.500000", "tradestatus": "1"}
        out = mod.parse_baostock_row("000001.SZ", row)
        self.assertEqual(out, {"date": "2026-04-17", "turnover_ratio": 0.025})

    def test_status_zero_with_positive_trade_evidence_is_accepted_and_traced(self):
        row = {
            "date": "2024-06-13",
            "code": "sz.002087",
            "volume": "20061549",
            "amount": "3286917.8400",
            "turn": "2.459600",
            "tradestatus": "0",
        }
        out = mod.parse_baostock_row("002087.SZ", row)
        self.assertEqual(out, {
            "date": "2024-06-13",
            "turnover_ratio": 0.024596,
            "provider_status_override": True,
        })

    def test_status_zero_without_complete_positive_trade_evidence_is_ignored(self):
        cases = [
            {"volume": "", "amount": "", "turn": ""},
            {"volume": "0", "amount": "3286917.84", "turn": "2.4596"},
            {"volume": "20061549", "amount": "0", "turn": "2.4596"},
            {"volume": "20061549", "amount": "3286917.84", "turn": "0"},
            {"volume": "bad", "amount": "3286917.84", "turn": "2.4596"},
        ]
        for evidence in cases:
            with self.subTest(evidence=evidence):
                row = {
                    "date": "2024-06-13",
                    "code": "sz.002087",
                    "tradestatus": "0",
                    **evidence,
                }
                self.assertIsNone(mod.parse_baostock_row("002087.SZ", row))

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

    def test_residual_binding_file_is_candidate_only_and_pit_safe(self):
        binding = json.loads(RESIDUAL_BINDING_PATH.read_text(encoding="utf-8"))
        index = mod.validate_residual_denominator_binding(binding)
        self.assertEqual(binding["artifact"], "GP12_CANDIDATE_TURNOVER_RESIDUAL_DENOMINATORS_V1")
        self.assertEqual(binding["status"], "CANDIDATE_ONLY_UNAPPROVED")
        self.assertEqual(binding["origin"], "NEW_RECONSTRUCTION_CANDIDATE")
        self.assertEqual(binding["source_turn_precision_percentage_points"], 0.0001)
        self.assertEqual(set(index), {"300216.SZ", "002604.SZ"})
        self.assertEqual(index["300216.SZ"]["floating_shares"], 291_684_518)
        self.assertEqual(index["002604.SZ"]["floating_shares"], 512_281_847)
        for entry in index.values():
            self.assertLess(entry["source_publication_date"], entry["coverage_start"])
        self.assertFalse(binding["historical_gp_v11_source_recovered"])
        self.assertFalse(binding["model_freeze_allowed"])
        self.assertFalse(binding["oos_metrics_allowed"])

    def test_residual_denominator_reproduces_positive_source_turn_precision(self):
        entry = {
            "symbol": "300216.SZ",
            "coverage_start": "2020-08-05",
            "coverage_end": "2020-09-15",
            "floating_shares": 291_684_518,
            "source_publication_date": "2020-06-30",
        }
        rows = [
            {"date": "2020-09-04", "volume": "108800", "amount": "36992", "turn": "0.037300", "tradestatus": "1"},
            {"date": "2020-09-14", "volume": "24593100", "amount": "4672689", "turn": "8.431400", "tradestatus": "1"},
            {"date": "2020-09-15", "volume": "106728927", "amount": "18945649.29", "turn": "36.590500", "tradestatus": "1"},
        ]
        out = mod.validate_residual_precision_neighbors(entry, rows)
        self.assertTrue(out["valid"])
        self.assertEqual(out["checked_n"], 3)
        self.assertLessEqual(out["max_abs_percentage_point_error"], 0.00005)

    def test_precision_zero_recovery_requires_bound_denominator_and_quantized_zero(self):
        entry = {
            "symbol": "300216.SZ",
            "coverage_start": "2020-08-05",
            "coverage_end": "2020-09-15",
            "floating_shares": 291_684_518,
            "source_publication_date": "2020-06-30",
        }
        row = {
            "date": "2020-08-05",
            "code": "sz.300216",
            "volume": "100",
            "amount": "343",
            "turn": "0.000000",
            "tradestatus": "1",
        }
        out = mod.parse_baostock_row("300216.SZ", row, residual_denominator=entry)
        self.assertAlmostEqual(out["turnover_ratio"], 100 / 291_684_518)
        self.assertTrue(out["turnover_precision_reconstruction"])
        self.assertEqual(out["residual_denominator_shares"], 291_684_518)
        self.assertEqual(out["residual_binding_symbol"], "300216.SZ")

        with self.assertRaises(ValueError):
            mod.parse_baostock_row("300216.SZ", row)

        too_large = dict(row, volume="1000", amount="3430")
        with self.assertRaisesRegex(ValueError, "precision zero"):
            mod.parse_baostock_row("300216.SZ", too_large, residual_denominator=entry)

    def test_residual_recovery_refuses_wrong_symbol_or_out_of_window(self):
        entry = {
            "symbol": "300216.SZ",
            "coverage_start": "2020-08-05",
            "coverage_end": "2020-09-15",
            "floating_shares": 291_684_518,
            "source_publication_date": "2020-06-30",
        }
        wrong_symbol = {
            "date": "2020-08-05", "code": "sz.000001", "volume": "100", "amount": "343",
            "turn": "0", "tradestatus": "1",
        }
        with self.assertRaises(ValueError):
            mod.parse_baostock_row("000001.SZ", wrong_symbol, residual_denominator=entry)

        out_of_window = {
            "date": "2020-08-04", "code": "sz.300216", "volume": "100", "amount": "343",
            "turn": "0", "tradestatus": "1",
        }
        with self.assertRaises(ValueError):
            mod.parse_baostock_row("300216.SZ", out_of_window, residual_denominator=entry)

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

    def test_audit_traces_provider_status_overrides(self):
        expected = ["2024-06-12", "2024-06-13"]
        rows = [
            {"date": "2024-06-12", "turnover_ratio": 0.01},
            {
                "date": "2024-06-13",
                "turnover_ratio": 0.024596,
                "provider_status_override": True,
            },
        ]
        out = mod.audit_symbol_rows("002087.SZ", expected, rows)
        self.assertTrue(out["symbol_pass"])
        self.assertEqual(out["provider_status_override_n"], 1)
        self.assertEqual(out["provider_status_override_dates"], ["2024-06-13"])

    def test_audit_and_materialization_trace_precision_reconstruction(self):
        expected = ["2020-08-05", "2020-08-06"]
        rows = [
            {
                "date": "2020-08-05",
                "turnover_ratio": 100 / 291_684_518,
                "turnover_precision_reconstruction": True,
                "residual_denominator_shares": 291_684_518,
                "residual_binding_symbol": "300216.SZ",
            },
            {"date": "2020-08-06", "turnover_ratio": 0.000138},
        ]
        audit = mod.audit_symbol_rows("300216.SZ", expected, rows)
        self.assertTrue(audit["symbol_pass"])
        self.assertEqual(audit["turnover_precision_reconstruction_n"], 1)
        self.assertEqual(audit["turnover_precision_reconstruction_dates"], ["2020-08-05"])

        panel = mod.materialize_rows("300216.SZ", rows)
        self.assertEqual(panel[0]["source"], "BAOSTOCK_TURN_RESIDUAL_DENOMINATOR_RECONSTRUCTION")
        self.assertEqual(panel[1]["source"], "BAOSTOCK_TURN_DAILY_UNADJUSTED")

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
