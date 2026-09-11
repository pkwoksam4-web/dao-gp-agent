import copy
import unittest

from gp12_label_provenance_admission_v482 import (
    audit_action_neutral_label_rows,
    build_label_provenance_admission,
)


class GP12LabelProvenanceAdmissionV482Test(unittest.TestCase):
    def _raw_probe(self):
        return {
            "status": "PASS_LITERAL_RAW_CLOSE_LABEL_PROVENANCE_PROBE",
            "formal_window": ["2020-06-01", "2026-04-17"],
            "horizons": [
                {"horizon_market_sessions": 1, "label_rows": 1010002},
                {"horizon_market_sessions": 2, "label_rows": 1008825},
                {"horizon_market_sessions": 3, "label_rows": 1007667},
            ],
            "invariants": {
                "oos_rows_consumed": 0,
                "max_target_date": "2026-04-17",
                "target_dates_never_shifted_for_missing_symbol_rows": True,
                "source_symbol_date_duplicates": 0,
                "zero_trade_symbols_emit_no_labels": True,
            },
            "promotion": {
                "historical_label_provenance_candidate_materialized": True,
                "label_provenance_blocker_closed": False,
                "candidate_adoption_status": "UNAPPROVED",
                "model_freeze_allowed": False,
                "oos_metrics_allowed": False,
            },
        }

    def _candidate(self):
        return {
            "status": "PASS_V482_PROVENANCE_LABEL_CANDIDATE_MATERIALIZED",
            "formal_window": ["2020-06-01", "2026-04-17"],
            "formal_qfq_checkpoint": {
                "PASS": 844,
                "EXACT_TERM_REVIEW": 0,
                "MISSING_EVENT_REVIEW": 0,
                "NOT_APPLICABLE": 3,
            },
            "formal_full_path_pass_n": 844,
            "standard_override_n": 270,
            "special_override_n": 11,
            "total_override_n": 281,
            "method": "Apply only V4.82-proven event ratios with T < ex_date <= target_date; exclude events after target_date.",
            "horizons": [
                {"horizon": 1, "rows": 1010002, "crossing_action_rows": 2708, "raw_vs_neutral_diff_rows": 792, "output_sha256": "a" * 64},
                {"horizon": 2, "rows": 1008825, "crossing_action_rows": 5414, "raw_vs_neutral_diff_rows": 1259, "output_sha256": "b" * 64},
                {"horizon": 3, "rows": 1007667, "crossing_action_rows": 8116, "raw_vs_neutral_diff_rows": 1735, "output_sha256": "c" * 64},
            ],
            "invariants": {
                "events_after_target_date_used": False,
                "oos_rows_consumed": 0,
                "max_target_date": "2026-04-17",
                "all_281_overrides_bound_to_ledger": True,
            },
            "promotion": {
                "label_contract_approved": False,
                "label_provenance_blocker_closed": False,
                "candidate_adoption_status": "UNAPPROVED",
                "model_freeze_allowed": False,
                "oos_metrics_allowed": False,
            },
        }

    def _row_audits(self):
        return [
            {
                "status": "PASS_ACTION_NEUTRAL_LABEL_ROWS",
                "horizon": 1,
                "rows": 1010002,
                "unique_symbol_date_n": 1010002,
                "formula_mismatch_n": 0,
                "label_mismatch_n": 0,
                "invalid_label_n": 0,
                "source_semantics_mismatch_n": 0,
                "target_oos_n": 0,
                "target_nonforward_n": 0,
                "invalid_numeric_n": 0,
                "file_sha256": "a" * 64,
            },
            {
                "status": "PASS_ACTION_NEUTRAL_LABEL_ROWS",
                "horizon": 2,
                "rows": 1008825,
                "unique_symbol_date_n": 1008825,
                "formula_mismatch_n": 0,
                "label_mismatch_n": 0,
                "invalid_label_n": 0,
                "source_semantics_mismatch_n": 0,
                "target_oos_n": 0,
                "target_nonforward_n": 0,
                "invalid_numeric_n": 0,
                "file_sha256": "b" * 64,
            },
            {
                "status": "PASS_ACTION_NEUTRAL_LABEL_ROWS",
                "horizon": 3,
                "rows": 1007667,
                "unique_symbol_date_n": 1007667,
                "formula_mismatch_n": 0,
                "label_mismatch_n": 0,
                "invalid_label_n": 0,
                "source_semantics_mismatch_n": 0,
                "target_oos_n": 0,
                "target_nonforward_n": 0,
                "invalid_numeric_n": 0,
                "file_sha256": "c" * 64,
            },
        ]

    def _event(self):
        return {
            "status": "PASS_EVENT_TIMING_ADMISSION",
            "expected_n": 2732,
            "covered_n": 2732,
            "missing_n": 0,
            "extra_n": 0,
            "late_n": 0,
            "source_partition_exact": True,
            "promotion": {"event_availability_time_verified": True},
        }

    def _override(self):
        return {
            "status": "PASS_OVERRIDE_TIMING_ADMISSION",
            "standard_expected_n": 270,
            "standard_pass_n": 270,
            "special_expected_n": 11,
            "special_pass_n": 11,
            "total_expected_n": 281,
            "total_pass_n": 281,
            "missing_n": 0,
            "binding_mismatch_n": 0,
            "late_n": 0,
            "missing_preopen_n": 0,
            "same_day_preopen_pass_n": 2,
            "promotion": {"corrected_term_availability_time_verified": True},
        }

    def _adjusted(self):
        return {
            "status": "VALIDATED_GLOBAL_PROVENANCE",
            "promotion": {
                "adjusted_close_blocker_closed": True,
                "adjustment_provenance_blocker_closed": True,
                "turnover_ratio_blocker_closed": False,
                "label_provenance_blocker_closed": False,
                "model_freeze_allowed": False,
                "oos_metrics_allowed": False,
            },
        }

    def _turnover(self):
        return {
            "status": "PASS_TURNOVER_RATIO_PIT_ADMISSION",
            "scope": {
                "universe_symbol_n": 847,
                "row_bearing_symbol_n": 844,
                "not_applicable_symbol_n": 3,
                "trade_row_n": 1011607,
            },
            "promotion": {
                "adjusted_close_blocker_closed": True,
                "adjustment_provenance_blocker_closed": True,
                "turnover_ratio_pit_verified": True,
                "turnover_ratio_blocker_closed": True,
                "label_provenance_blocker_closed": False,
                "model_freeze_allowed": False,
                "oos_metrics_allowed": False,
            },
        }

    def test_row_audit_accepts_contract_exact_rows(self):
        rows = [
            {
                "symbol": "000001.SZ",
                "date": "2024-01-02",
                "horizon_market_sessions": 1,
                "target_date": "2024-01-03",
                "close": 10.0,
                "target_close": 9.0,
                "event_ratio_product": 0.9,
                "crosses_corporate_action": True,
                "action_neutral_reference_close": 9.0,
                "label": "FLAT",
                "source_semantics": "V4.82_proven_horizon_local_action_neutral",
            },
            {
                "symbol": "000002.SZ",
                "date": "2024-01-02",
                "horizon_market_sessions": 1,
                "target_date": "2024-01-03",
                "close": 10.0,
                "target_close": 10.5,
                "event_ratio_product": 1.0,
                "crosses_corporate_action": False,
                "action_neutral_reference_close": 10.0,
                "label": "UP",
                "source_semantics": "V4.82_proven_horizon_local_action_neutral",
            },
        ]
        x = audit_action_neutral_label_rows(rows, 1, file_sha256="d" * 64)
        self.assertEqual(x["status"], "PASS_ACTION_NEUTRAL_LABEL_ROWS")
        self.assertEqual(x["formula_mismatch_n"], 0)
        self.assertEqual(x["label_mismatch_n"], 0)

    def test_row_audit_rejects_label_formula_mismatch(self):
        rows = [{
            "symbol": "000001.SZ",
            "date": "2024-01-02",
            "horizon_market_sessions": 1,
            "target_date": "2024-01-03",
            "close": 10.0,
            "target_close": 9.1,
            "event_ratio_product": 0.9,
            "crosses_corporate_action": True,
            "action_neutral_reference_close": 9.0,
            "label": "DOWN",
            "source_semantics": "V4.82_proven_horizon_local_action_neutral",
        }]
        x = audit_action_neutral_label_rows(rows, 1, file_sha256="d" * 64)
        self.assertEqual(x["status"], "REVIEW_ACTION_NEUTRAL_LABEL_ROWS")
        self.assertEqual(x["label_mismatch_n"], 1)

    def test_valid_evidence_closes_label_only_and_keeps_freeze_oos_closed(self):
        x = build_label_provenance_admission(
            self._raw_probe(), self._candidate(), self._row_audits(),
            self._event(), self._override(), self._adjusted(), self._turnover(),
        )
        self.assertEqual(x["status"], "PASS_LABEL_PROVENANCE_ADMISSION")
        self.assertTrue(x["promotion"]["label_contract_approved"])
        self.assertTrue(x["promotion"]["label_provenance_blocker_closed"])
        self.assertTrue(x["promotion"]["formal_feature_ready"])
        self.assertFalse(x["promotion"]["model_freeze_allowed"])
        self.assertFalse(x["promotion"]["oos_metrics_allowed"])
        self.assertEqual(x["remaining_gp12_feature_blockers"], [])
        self.assertEqual(x["next_gate"], "MODEL_FREEZE_PROVENANCE_ADMISSION")

    def test_future_event_use_fails_closed(self):
        bad = copy.deepcopy(self._candidate())
        bad["invariants"]["events_after_target_date_used"] = True
        with self.assertRaisesRegex(ValueError, "candidate"):
            build_label_provenance_admission(
                self._raw_probe(), bad, self._row_audits(),
                self._event(), self._override(), self._adjusted(), self._turnover(),
            )

    def test_shifted_target_policy_fails_closed(self):
        bad = copy.deepcopy(self._raw_probe())
        bad["invariants"]["target_dates_never_shifted_for_missing_symbol_rows"] = False
        with self.assertRaisesRegex(ValueError, "raw label"):
            build_label_provenance_admission(
                bad, self._candidate(), self._row_audits(),
                self._event(), self._override(), self._adjusted(), self._turnover(),
            )

    def test_row_mismatch_fails_closed(self):
        rows = self._row_audits()
        rows[1]["formula_mismatch_n"] = 1
        rows[1]["status"] = "REVIEW_ACTION_NEUTRAL_LABEL_ROWS"
        with self.assertRaisesRegex(ValueError, "row audit"):
            build_label_provenance_admission(
                self._raw_probe(), self._candidate(), rows,
                self._event(), self._override(), self._adjusted(), self._turnover(),
            )

    def test_event_or_override_timing_failure_fails_closed(self):
        event = self._event(); event["late_n"] = 1
        with self.assertRaisesRegex(ValueError, "event timing"):
            build_label_provenance_admission(
                self._raw_probe(), self._candidate(), self._row_audits(),
                event, self._override(), self._adjusted(), self._turnover(),
            )
        override = self._override(); override["binding_mismatch_n"] = 1
        with self.assertRaisesRegex(ValueError, "override timing"):
            build_label_provenance_admission(
                self._raw_probe(), self._candidate(), self._row_audits(),
                self._event(), override, self._adjusted(), self._turnover(),
            )

    def test_upstream_feature_gate_failure_fails_closed(self):
        turnover = self._turnover(); turnover["promotion"]["turnover_ratio_blocker_closed"] = False
        with self.assertRaisesRegex(ValueError, "turnover"):
            build_label_provenance_admission(
                self._raw_probe(), self._candidate(), self._row_audits(),
                self._event(), self._override(), self._adjusted(), turnover,
            )


if __name__ == "__main__":
    unittest.main()
