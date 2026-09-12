import unittest

from gp12_model_freeze_recovery_triage_v482 import build_model_freeze_recovery_triage


CANONICAL = [
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

HISTORICAL = [
    "COMPLETE_12_FACTOR_STRATEGY_CODE_BYTES_MISSING",
    "EXACT_NON_DAILY_FACTOR_FORMULAS_NORMALIZATION_AGGREGATION_MISSING",
    "FULL_GP12_THREE_WAY_PROBABILITY_MAPPING_MISSING",
    "RANKING_TOPN_SEMANTICS_MISSING",
    "ENTRY_EXIT_THRESHOLDS_MISSING",
    "HOLDING_REBALANCE_POLICY_MISSING",
    "POSITION_SIZING_AND_RISK_RULES_MISSING",
    "ACTUAL_FILL_PRICE_AND_INTRADAY_EXECUTION_RULES_MISSING",
]

MIXED = [
    "PIT_SECTOR_AND_FUND_FLOW_INPUT_PROVENANCE_INCOMPLETE",
    "FORMAL847_INTRADAY_BYTE_COVERAGE_AND_HISTORICAL_RESAMPLING_MISSING",
]


def checkpoint():
    return {
        "artifact": "GP12_MODEL_FREEZE_PROVENANCE_CHECKPOINT_V482",
        "version": "V4.82",
        "strategy_id": "GP_V11",
        "status": "BLOCKED_MODEL_FREEZE_PROVENANCE",
        "formal_feature_ready": True,
        "oos_calendar_ready": True,
        "remaining_blockers": CANONICAL,
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
    }


def archive_audit():
    keys = {
        "full_three_way_prob": False,
        "topn_policy": False,
        "entry_exit_policy": False,
        "holding_rebalance": False,
        "position_sizing": False,
        "intraday_formula": False,
    }
    archives = []
    for i in range(13):
        archives.append({
            "name": f"archive-{i}.zip",
            "sha256": (f"{i:02x}" * 32)[:64],
            "keyword_presence": dict(keys),
            "explicit_daily_base_scope": i < 10,
        })
    return {
        "artifact": "GP12_HISTORICAL_ARCHIVE_EXHAUSTION_V482",
        "strategy_id": "GP_V11",
        "accessible_archive_lineage_complete": True,
        "archive_count": 13,
        "archives": archives,
        "explicit_daily_base_scope_archive_n": 10,
        "historical_conversation_contract_search_complete": True,
        "historical_conversation_found_missing_policy_contract": False,
    }


class ModelFreezeRecoveryTriageV482Test(unittest.TestCase):
    def test_current_evidence_separates_historical_and_mixed_blockers(self):
        x = build_model_freeze_recovery_triage(checkpoint(), archive_audit())
        self.assertEqual(x["status"], "RECOVERY_TRIAGED_MODEL_FREEZE_BLOCKED")
        self.assertEqual(x["historical_contract_blockers"], HISTORICAL)
        self.assertEqual(x["mixed_data_and_contract_blockers"], MIXED)
        self.assertEqual(x["pure_engineering_blockers"], [])
        self.assertTrue(x["accessible_historical_archive_lineage_exhausted"])
        self.assertFalse(x["historical_gp_v11_freeze_possible_from_accessible_archives"])
        self.assertFalse(x["candidate_substitution_allowed"])
        self.assertFalse(x["model_freeze_allowed"])
        self.assertFalse(x["oos_metrics_allowed"])

    def test_archive_lineage_must_be_complete(self):
        a = archive_audit(); a["accessible_archive_lineage_complete"] = False
        with self.assertRaisesRegex(ValueError, "archive lineage"):
            build_model_freeze_recovery_triage(checkpoint(), a)

    def test_all_archive_hashes_are_bound(self):
        a = archive_audit(); a["archives"][0]["sha256"] = "bad"
        with self.assertRaisesRegex(ValueError, "sha256"):
            build_model_freeze_recovery_triage(checkpoint(), a)

    def test_policy_hit_in_archive_prevents_exhaustion_claim(self):
        a = archive_audit(); a["archives"][0]["keyword_presence"]["topn_policy"] = True
        x = build_model_freeze_recovery_triage(checkpoint(), a)
        self.assertFalse(x["accessible_historical_archive_lineage_exhausted"])
        self.assertNotIn("RANKING_TOPN_SEMANTICS_MISSING", x["historical_contract_blockers"])
        self.assertIn("RANKING_TOPN_SEMANTICS_MISSING", x["requires_targeted_reinspection"])

    def test_cannot_triage_from_promoted_or_open_oos_checkpoint(self):
        c = checkpoint(); c["oos_metrics_allowed"] = True
        with self.assertRaisesRegex(ValueError, "fail-closed"):
            build_model_freeze_recovery_triage(c, archive_audit())

    def test_rebuild_must_use_new_strategy_identity(self):
        x = build_model_freeze_recovery_triage(checkpoint(), archive_audit())
        self.assertEqual(x["if_rebuild_is_approved"]["strategy_identity_rule"], "MUST_NOT_CLAIM_GP_V11_HISTORICAL_IDENTITY")
        self.assertEqual(x["next_gate"], "ENGINEER_RECOVERABLE_PROVENANCE_AND_SEARCH_EXTERNAL_ORIGINAL_CONTRACT")


if __name__ == "__main__":
    unittest.main()
