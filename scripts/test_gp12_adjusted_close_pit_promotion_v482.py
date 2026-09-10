import copy
import unittest

from gp12_adjusted_close_pit_promotion_v482 import build_promotion


class GP12AdjustedClosePitPromotionV482Test(unittest.TestCase):
    def setUp(self):
        self.event = {
            "status": "PASS_EVENT_TIMING_ADMISSION",
            "expected_n": 2732,
            "covered_n": 2732,
            "missing_n": 0,
            "extra_n": 0,
            "late_n": 0,
            "source_partition_exact": True,
            "promotion": {"event_availability_time_verified": True},
        }
        self.override = {
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
        self.row = {
            "status": "PASS_ROW_LEVEL_MATERIALIZATION",
            "formal_symbol_n": 844,
            "not_applicable_symbol_n": 3,
            "row_n": 1011607,
            "unique_symbol_date_n": 1011607,
            "factor_positive_rows": 1011607,
            "row_provenance_nonempty_n": 1011607,
            "row_provenance_unique_n": 1011607,
            "event_ledger_n": 2732,
            "override_event_n": 281,
            "sample50_v479": {"sample_n": 50, "pass_n": 50, "fail_n": 0, "max_diff_bp": 3.6},
            "global_row_crosscheck": {"threshold_bp": 5.0, "mismatch_rows": 0, "max_diff_bp": 4.9},
        }
        self.formal = {
            "formal_ready": True,
            "validated_global_provenance_emitted": True,
            "full_path_pass_n": 844,
            "full_path_fail_n": 0,
            "checkpoint": {"PASS": 844, "EXACT_TERM_REVIEW": 0, "MISSING_EVENT_REVIEW": 0, "NOT_APPLICABLE": 3},
            "oos_metrics_allowed": False,
        }

    def test_valid_inputs_promote_adjusted_close_only(self):
        result = build_promotion(self.event, self.override, self.row, self.formal)
        self.assertEqual(result["status"], "VALIDATED_GLOBAL_PROVENANCE")
        self.assertTrue(result["promotion"]["adjusted_close_blocker_closed"])
        self.assertTrue(result["promotion"]["adjustment_provenance_blocker_closed"])
        self.assertFalse(result["promotion"]["turnover_ratio_blocker_closed"])
        self.assertFalse(result["promotion"]["label_provenance_blocker_closed"])
        self.assertFalse(result["promotion"]["model_freeze_allowed"])
        self.assertFalse(result["promotion"]["oos_metrics_allowed"])
        self.assertEqual(
            result["remaining_gp12_blockers"],
            ["TURNOVER_RATIO_UNBOUND", "LABEL_PROVENANCE_UNBOUND"],
        )

    def test_event_timing_failure_fails_closed(self):
        bad = copy.deepcopy(self.event)
        bad["late_n"] = 1
        with self.assertRaisesRegex(ValueError, "event timing admission"):
            build_promotion(bad, self.override, self.row, self.formal)

    def test_override_binding_failure_fails_closed(self):
        bad = copy.deepcopy(self.override)
        bad["binding_mismatch_n"] = 1
        with self.assertRaisesRegex(ValueError, "override timing admission"):
            build_promotion(self.event, bad, self.row, self.formal)

    def test_row_level_crosscheck_failure_fails_closed(self):
        bad = copy.deepcopy(self.row)
        bad["global_row_crosscheck"]["mismatch_rows"] = 1
        with self.assertRaisesRegex(ValueError, "row-level provenance"):
            build_promotion(self.event, self.override, bad, self.formal)

    def test_formal_final_failure_fails_closed(self):
        bad = copy.deepcopy(self.formal)
        bad["full_path_fail_n"] = 1
        with self.assertRaisesRegex(ValueError, "formal final"):
            build_promotion(self.event, self.override, self.row, bad)


if __name__ == "__main__":
    unittest.main()
