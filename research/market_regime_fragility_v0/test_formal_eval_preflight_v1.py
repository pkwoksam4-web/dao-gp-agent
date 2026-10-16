import unittest

from formal_eval_preflight_v1 import check_manifest


VALID_MANIFEST = {
    "baseline_version": "MOMENTUM_VOL_REGIME_V1",
    "zero_parameter_comparator_version": "BASELINE_0_NO_REGIME_OVERLAY",
    "score_mapping_version": "RISK_EVIDENCE_SCORE_MAPPING_V1",
    "inference_version": "PRIMARY_3D_DOWNSIDE_CONCORDANCE_V1",
    "permutation_null_version": "BLOCK_PERMUTATION_NULL_V1",
    "permutation_null_hash": "permutation-null-hash-abc123",
    "permutation_block_length": 3,
    "permutation_replications": 5000,
    "permutation_seed": 20261016,
    "power_plan_version": "POWER_SAMPLE_PLAN_V1",
    "primary_horizon_sessions": 3,
    "primary_alpha": 0.05,
    "target_power": 0.80,
    "minimum_effect_delta_tau": 0.05,
    "minimum_sample_required": 120,
    "unused_set": True,
    "evaluation_set_id": "prospective-shadow-001",
    "evaluation_set_hash": "abc123",
    "definitions_locked_before_set_open": True,
    "complex_classifier_version": "CANONICAL_STATE_CLASSIFIER_V1",
    "complex_classifier_hash": "def456",
    "atomic_ledger_version": "ATOMIC_EVIDENCE_LEDGER_V1",
    "classifier_ledger_pit_valid": True,
    "classifier_evidence_hash": "ledger-evidence-abc123",
    "data_cutoff_policy": "COMPLETED_SESSION_ONLY",
    "universe_snapshot_hash": "universe-hash-abc123",
    "universe_pit_valid": True,
    "tradability_policy_version": "A_SHARE_TRADABILITY_GATE_V1",
    "tradability_filter_applied_before_ranking": True,
    "market_structure_regime_schedule_version": "A_SHARE_MARKET_STRUCTURE_REGIME_SCHEDULE_V1",
    "market_structure_regime_schedule_hash": "schedule-hash-abc123",
    "market_structure_schedule_pit_valid": True,
    "market_structure_schedule_scope_complete": True,
    "change_control_version": "MODULE_DOWNGRADE_CHANGE_CONTROL_V1",
    "manual_override_policy_version": "MANUAL_OVERRIDE_LEDGER_V1",
    "primary_model_metric_uses_unoverridden_outputs": True,
    "manual_override_count": 0,
    "manual_override_ledger_hash": "empty-ledger-hash-abc123",
    "consumed_set_ids": ["historical-consumed-a", "historical-consumed-b"],
}


class FormalEvalPreflightV1Tests(unittest.TestCase):
    def test_valid_manifest_is_eligible_for_evaluation_only(self):
        result = check_manifest(dict(VALID_MANIFEST))
        self.assertTrue(result["eligible"])
        self.assertEqual(result["reasons"], [])

    def test_missing_lock_fails_closed(self):
        manifest = dict(VALID_MANIFEST)
        manifest["definitions_locked_before_set_open"] = False
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("DEFINITIONS_NOT_LOCKED_BEFORE_SET_OPEN", result["reasons"])

    def test_consumed_set_cannot_be_relabelled_unused(self):
        manifest = dict(VALID_MANIFEST)
        manifest["evaluation_set_id"] = "historical-consumed-a"
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("EVALUATION_SET_ALREADY_CONSUMED", result["reasons"])

    def test_unset_hash_or_wrong_version_fails_closed(self):
        manifest = dict(VALID_MANIFEST)
        manifest["complex_classifier_hash"] = ""
        manifest["baseline_version"] = "OTHER"
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("COMPLEX_CLASSIFIER_HASH_MISSING", result["reasons"])
        self.assertIn("BASELINE_VERSION_MISMATCH", result["reasons"])

    def test_zero_parameter_comparator_version_must_match(self):
        manifest = dict(VALID_MANIFEST)
        manifest["zero_parameter_comparator_version"] = "OTHER"
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("ZERO_PARAMETER_COMPARATOR_VERSION_MISMATCH", result["reasons"])

    def test_permutation_null_version_must_match(self):
        manifest = dict(VALID_MANIFEST)
        manifest["permutation_null_version"] = "OTHER"
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("PERMUTATION_NULL_VERSION_MISMATCH", result["reasons"])

    def test_permutation_null_hash_is_required(self):
        manifest = dict(VALID_MANIFEST)
        manifest["permutation_null_hash"] = ""
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("PERMUTATION_NULL_HASH_MISSING", result["reasons"])

    def test_permutation_block_length_is_locked_to_primary_horizon(self):
        manifest = dict(VALID_MANIFEST)
        manifest["permutation_block_length"] = 2
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("PERMUTATION_BLOCK_LENGTH_MISMATCH", result["reasons"])

    def test_permutation_replications_and_seed_are_frozen(self):
        manifest = dict(VALID_MANIFEST)
        manifest["permutation_replications"] = 4999
        manifest["permutation_seed"] = 7
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("PERMUTATION_REPLICATIONS_MISMATCH", result["reasons"])
        self.assertIn("PERMUTATION_SEED_MISMATCH", result["reasons"])

    def test_missing_power_assumptions_fail_closed(self):
        manifest = dict(VALID_MANIFEST)
        manifest["minimum_effect_delta_tau"] = None
        manifest["minimum_sample_required"] = None
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("MINIMUM_EFFECT_NOT_FROZEN", result["reasons"])
        self.assertIn("MINIMUM_SAMPLE_NOT_FROZEN", result["reasons"])

    def test_wrong_atomic_ledger_version_fails_closed(self):
        manifest = dict(VALID_MANIFEST)
        manifest["atomic_ledger_version"] = "OTHER_LEDGER"
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("ATOMIC_LEDGER_VERSION_MISMATCH", result["reasons"])

    def test_classifier_ledger_must_be_pit_valid(self):
        manifest = dict(VALID_MANIFEST)
        manifest["classifier_ledger_pit_valid"] = False
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("CLASSIFIER_LEDGER_NOT_PIT_VALID", result["reasons"])

    def test_classifier_evidence_hash_is_required(self):
        manifest = dict(VALID_MANIFEST)
        manifest["classifier_evidence_hash"] = ""
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("CLASSIFIER_EVIDENCE_HASH_MISSING", result["reasons"])

    def test_universe_snapshot_hash_is_required(self):
        manifest = dict(VALID_MANIFEST)
        manifest["universe_snapshot_hash"] = ""
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("UNIVERSE_SNAPSHOT_HASH_MISSING", result["reasons"])

    def test_universe_must_be_pit_valid(self):
        manifest = dict(VALID_MANIFEST)
        manifest["universe_pit_valid"] = False
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("UNIVERSE_NOT_PIT_VALID", result["reasons"])

    def test_tradability_policy_version_must_match(self):
        manifest = dict(VALID_MANIFEST)
        manifest["tradability_policy_version"] = "OTHER"
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("TRADABILITY_POLICY_VERSION_MISMATCH", result["reasons"])

    def test_tradability_filter_must_run_before_ranking(self):
        manifest = dict(VALID_MANIFEST)
        manifest["tradability_filter_applied_before_ranking"] = False
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("TRADABILITY_FILTER_NOT_APPLIED_BEFORE_RANKING", result["reasons"])

    def test_market_structure_regime_schedule_version_must_match(self):
        manifest = dict(VALID_MANIFEST)
        manifest["market_structure_regime_schedule_version"] = "OTHER"
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("MARKET_STRUCTURE_REGIME_SCHEDULE_VERSION_MISMATCH", result["reasons"])

    def test_market_structure_schedule_hash_is_required(self):
        manifest = dict(VALID_MANIFEST)
        manifest["market_structure_regime_schedule_hash"] = ""
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("MARKET_STRUCTURE_REGIME_SCHEDULE_HASH_MISSING", result["reasons"])

    def test_market_structure_schedule_must_be_pit_valid(self):
        manifest = dict(VALID_MANIFEST)
        manifest["market_structure_schedule_pit_valid"] = False
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("MARKET_STRUCTURE_SCHEDULE_NOT_PIT_VALID", result["reasons"])

    def test_market_structure_schedule_must_be_scope_complete(self):
        manifest = dict(VALID_MANIFEST)
        manifest["market_structure_schedule_scope_complete"] = False
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("MARKET_STRUCTURE_SCHEDULE_SCOPE_INCOMPLETE", result["reasons"])

    def test_change_control_version_must_match(self):
        manifest = dict(VALID_MANIFEST)
        manifest["change_control_version"] = "OTHER"
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("CHANGE_CONTROL_VERSION_MISMATCH", result["reasons"])

    def test_manual_override_policy_version_must_match(self):
        manifest = dict(VALID_MANIFEST)
        manifest["manual_override_policy_version"] = "OTHER"
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("MANUAL_OVERRIDE_POLICY_VERSION_MISMATCH", result["reasons"])

    def test_primary_model_metric_must_use_unoverridden_outputs(self):
        manifest = dict(VALID_MANIFEST)
        manifest["primary_model_metric_uses_unoverridden_outputs"] = False
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("PRIMARY_MODEL_METRIC_CONTAMINATED_BY_OVERRIDE", result["reasons"])

    def test_manual_override_count_must_be_nonnegative_integer(self):
        for bad_value in (-1, 1.5, True, None):
            manifest = dict(VALID_MANIFEST)
            manifest["manual_override_count"] = bad_value
            result = check_manifest(manifest)
            self.assertFalse(result["eligible"])
            self.assertIn("MANUAL_OVERRIDE_COUNT_INVALID", result["reasons"])

    def test_manual_override_ledger_hash_is_required_even_when_count_zero(self):
        manifest = dict(VALID_MANIFEST)
        manifest["manual_override_ledger_hash"] = ""
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("MANUAL_OVERRIDE_LEDGER_HASH_MISSING", result["reasons"])

    def test_nonzero_manual_override_count_is_allowed_when_provenance_is_present(self):
        manifest = dict(VALID_MANIFEST)
        manifest["manual_override_count"] = 2
        manifest["manual_override_ledger_hash"] = "ledger-hash-with-two-overrides"
        result = check_manifest(manifest)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["reasons"], [])

    def test_preflight_does_not_authorize_production(self):
        result = check_manifest(dict(VALID_MANIFEST))
        self.assertFalse(result["production_authorized"])


if __name__ == "__main__":
    unittest.main()
