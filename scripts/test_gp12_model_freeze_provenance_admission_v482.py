import copy
import unittest

from gp12_model_freeze_provenance_admission_v482 import build_model_freeze_provenance_admission


EXPECTED_BLOCKERS = [
    "COMPLETE_12_FACTOR_STRATEGY_CODE_BYTES_MISSING",
    "EXACT_NON_DAILY_FACTOR_FORMULAS_NORMALIZATION_AGGREGATION_MISSING",
    "PIT_SECTOR_AND_FUND_FLOW_INPUT_PROVENANCE_INCOMPLETE",
    "FULL_GP12_THREE_WAY_PROBABILITY_MAPPING_MISSING",
    "RANKING_TOPN_SEMANTICS_MISSING",
    "ENTRY_EXIT_THRESHOLDS_MISSING",
    "HOLDING_REBALANCE_POLICY_MISSING",
    "POSITION_SIZING_AND_RISK_RULES_MISSING",
    "ACTUAL_FILL_PRICE_AND_INTRADAY_EXECUTION_RULES_MISSING",
    "FORMAL847_INTRADAY_BYTE_COVERAGE_AND_HISTORICAL_RESAMPLING_MISSING",
]


class ModelFreezeProvenanceAdmissionV482Test(unittest.TestCase):
    def label(self):
        return {
            "status": "PASS_LABEL_PROVENANCE_ADMISSION",
            "promotion": {
                "adjusted_close_blocker_closed": True,
                "turnover_ratio_blocker_closed": True,
                "label_provenance_blocker_closed": True,
                "formal_feature_ready": True,
                "model_freeze_allowed": False,
                "oos_metrics_allowed": False,
            },
        }

    def calendar(self):
        return {
            "status": "OOS_CALENDAR_READY_V482",
            "formal_date_n": 1426,
            "oos_date_n": 98,
            "total_date_n": 1524,
            "first_oos_trade_date": "2026-04-20",
            "last_oos_trade_date": "2026-09-08",
            "official_evidence_sha256": "082ce4579a5d526faaa01249babef41dccd79caee6f35a2fa383ea62a6ef2f87",
            "formal_calendar_sha256": "5a872a47cf7a338cc48aa628b8de46053fddc3ed161a2617550199d0607efae7",
            "oos_calendar_sha256": "897a76ff4a857c9712f98877491f03e975f0ee591025cfa543e1a618b240b992",
            "calendar_sha256": "e60deef5c885b36b99fe8dd1cbd6d5763a2f945f123e9fd5f60ce07c907c5019",
        }

    def strategy(self):
        return {
            "artifact": "GP_V11_STRATEGY_RECOVERY_EVIDENCE_V482",
            "version": "V4.82",
            "strategy_id": "GP_V11",
            "recovered_assets": [{"key": "daily_base_strategy_code", "complete_12_factor_strategy": False}],
            "missing_required_fields": [
                "complete_12_factor_strategy_code_bytes",
                "non_daily_layer_factor_formulas",
                "exact_normalization_and_clipping",
                "score_layer_aggregation",
                "probability_mapping",
                "ranking_topn_semantics",
                "entry_exit_thresholds",
                "holding_and_rebalance_policy",
                "position_sizing_and_risk_rules",
                "non_daily_layer_source_bytes",
            ],
        }

    def factor(self):
        return {
            "artifact": "GP_V11_FACTOR_RECOVERY_MATRIX_V482",
            "authoritative_weight_vector_recovered": True,
            "complete_factor_definitions_recovered": False,
            "full_strategy_source_recovered": False,
            "sector_membership_partial_source": {"pit_membership_verified": False, "factor_formula_recovered": False},
            "fund_flow_partial_source": {"factor_formula_recovered": False},
            "intraday_source_partial": {
                "formal_847_inventory_membership_verified": True,
                "formal_847_minute_byte_coverage_verified": False,
                "formal_15m_coverage_verified": False,
                "formal_60m_coverage_verified": False,
                "resampling_contract_recovered": False,
                "factor_formula_recovered": False,
            },
        }

    def decision(self):
        return {
            "artifact": "GP_V11_DECISION_POLICY_RECOVERY_MATRIX_V482",
            "full_parameter_set_recovered": False,
            "full_strategy_probability_mapping_recovered": False,
            "remaining_policy_gaps": [
                "full_gp12_three_way_probability_mapping",
                "ranking_topn_semantics",
                "entry_exit_thresholds",
                "holding_and_rebalance_policy",
                "position_sizing_and_risk_rules",
                "actual_fill_price_and_intraday_execution_rules",
            ],
            "model_freeze_allowed": False,
            "oos_metrics_allowed": False,
        }

    def intraday(self):
        return {
            "artifact": "GP_V11_INTRADAY_SOURCE_RECOVERY_V482",
            "status": "PARTIAL_FILE_BACKED_FORMAL847_INVENTORY_PLUS_SINGLE_SYMBOL_RESAMPLING_PILOT",
            "formal_847_minute_inventory_membership_verified": True,
            "formal_847_minute_byte_coverage_verified": False,
            "formal_847_15m_coverage_verified": False,
            "formal_847_60m_coverage_verified": False,
            "resampling_contract_recovered": False,
            "factor_formula_recovered": False,
            "model_freeze_allowed": False,
            "oos_metrics_allowed": False,
        }

    def test_current_evidence_emits_exact_fail_closed_checkpoint(self):
        x = build_model_freeze_provenance_admission(
            self.label(), self.calendar(), self.strategy(), self.factor(), self.decision(), self.intraday()
        )
        self.assertEqual(x["status"], "BLOCKED_MODEL_FREEZE_PROVENANCE")
        self.assertTrue(x["formal_feature_ready"])
        self.assertTrue(x["oos_calendar_ready"])
        self.assertTrue(x["old_oos_calendar_blocker_closed"])
        self.assertFalse(x["strategy_provenance_complete"])
        self.assertEqual(x["remaining_blockers"], EXPECTED_BLOCKERS)
        self.assertFalse(x["model_freeze_allowed"])
        self.assertFalse(x["oos_metrics_allowed"])
        self.assertFalse(x["candidate_substitution_allowed"])

    def test_feature_gate_must_be_closed_first(self):
        label = self.label(); label["promotion"]["formal_feature_ready"] = False
        with self.assertRaisesRegex(ValueError, "feature"):
            build_model_freeze_provenance_admission(
                label, self.calendar(), self.strategy(), self.factor(), self.decision(), self.intraday()
            )

    def test_oos_calendar_must_be_officially_bound(self):
        cal = self.calendar(); cal["oos_date_n"] = 97
        with self.assertRaisesRegex(ValueError, "calendar"):
            build_model_freeze_provenance_admission(
                self.label(), cal, self.strategy(), self.factor(), self.decision(), self.intraday()
            )

    def test_candidate_cannot_erase_historical_strategy_gaps(self):
        strategy = self.strategy(); strategy["candidate_package_available"] = True
        x = build_model_freeze_provenance_admission(
            self.label(), self.calendar(), strategy, self.factor(), self.decision(), self.intraday()
        )
        self.assertEqual(x["remaining_blockers"], EXPECTED_BLOCKERS)
        self.assertFalse(x["candidate_substitution_allowed"])
        self.assertFalse(x["model_freeze_allowed"])

    def test_intraday_inventory_membership_is_not_byte_coverage(self):
        intraday = self.intraday(); intraday["formal_847_minute_inventory_membership_verified"] = True
        x = build_model_freeze_provenance_admission(
            self.label(), self.calendar(), self.strategy(), self.factor(), self.decision(), intraday
        )
        self.assertIn("FORMAL847_INTRADAY_BYTE_COVERAGE_AND_HISTORICAL_RESAMPLING_MISSING", x["remaining_blockers"])

    def test_inconsistent_recovery_claim_fails_closed(self):
        factor = self.factor(); factor["complete_factor_definitions_recovered"] = True
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            build_model_freeze_provenance_admission(
                self.label(), self.calendar(), self.strategy(), factor, self.decision(), self.intraday()
            )


if __name__ == "__main__":
    unittest.main()
