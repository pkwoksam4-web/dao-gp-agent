import unittest

from formal_eval_preflight_v1 import check_manifest


VALID_MANIFEST = {
    "baseline_version": "MOMENTUM_VOL_REGIME_V1",
    "score_mapping_version": "RISK_EVIDENCE_SCORE_MAPPING_V1",
    "inference_version": "PRIMARY_3D_DOWNSIDE_CONCORDANCE_V1",
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
    "complex_classifier_version": "UNSET_FOR_TEST",
    "complex_classifier_hash": "def456",
    "data_cutoff_policy": "COMPLETED_SESSION_ONLY",
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

    def test_missing_power_assumptions_fail_closed(self):
        manifest = dict(VALID_MANIFEST)
        manifest["minimum_effect_delta_tau"] = None
        manifest["minimum_sample_required"] = None
        result = check_manifest(manifest)
        self.assertFalse(result["eligible"])
        self.assertIn("MINIMUM_EFFECT_NOT_FROZEN", result["reasons"])
        self.assertIn("MINIMUM_SAMPLE_NOT_FROZEN", result["reasons"])

    def test_preflight_does_not_authorize_production(self):
        result = check_manifest(dict(VALID_MANIFEST))
        self.assertFalse(result["production_authorized"])


if __name__ == "__main__":
    unittest.main()
