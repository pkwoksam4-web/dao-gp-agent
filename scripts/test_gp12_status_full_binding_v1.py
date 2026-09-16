from __future__ import annotations

import copy
import unittest

import gp12_candidate_input_readiness_status_v1 as mod
import test_gp12_candidate_input_readiness_v1 as base


STATUS_BINDING_SHA256 = "aaf1c352d74ce2a0408ea454f8d9deaaea7d9428629ed33ecccdd09f1a2ce96a"


def canonical_status_binding() -> dict:
    return base.load("data/GP12_CANDIDATE_STATUS_BINDING_V1.json")


def build_with_full_status(binding: dict | None = None) -> dict:
    return mod.build_checkpoint(
        base.load("data/GP12_CANDIDATE_PARAMETERS_V1.json"),
        base.load("data/GP12_CANDIDATE_FACTORS_V1.json"),
        base.load("data/GP12_FORMAL_INPUT_EVIDENCE_V1.json"),
        base.load("data/GP12_INTRADAY_FORMAL847_BINDING_V1.json"),
        base.load("data/GP12_PIT_ADJUSTED_CLOSE_BINDING_V1.json"),
        base.valid_benchmark_evidence(),
        base.valid_amount_turnover_binding(),
        base.load("data/GP12_MAIN_NET_FLOW_SOURCE_REQUIREMENT_V1.json"),
        base.load("data/GP12_CANDIDATE_STATUS_PARTIAL_BINDING_V1.json"),
        base.load("data/GP12_CANDIDATE_MARKET_BREADTH_BINDING_V1.json"),
        status_binding=canonical_status_binding() if binding is None else binding,
    )


class StatusFullBindingTests(unittest.TestCase):
    def test_full_status_validator_is_exact_and_fail_closed(self):
        binding = canonical_status_binding()
        self.assertEqual(mod.validate_status_binding(binding), STATUS_BINDING_SHA256)
        bad = copy.deepcopy(binding)
        bad["upper_limit_source"]["truth_price_mismatch_n"] = 1
        with self.assertRaises(ValueError):
            mod.validate_status_binding(bad)

    def test_full_status_binding_promotes_family_without_opening_global_gates(self):
        out = build_with_full_status()
        self.assertEqual(out["status_binding_artifact"], "GP12_CANDIDATE_STATUS_BINDING_V1")
        self.assertEqual(out["status_binding_sha256"], STATUS_BINDING_SHA256)
        self.assertEqual(out["status_semantic_state"], {
            "is_st": "BOUND_PIT_VERIFIED",
            "tradable": "BOUND_PIT_VERIFIED",
            "upper_limit": "BOUND_PIT_VERIFIED",
        })
        status = out["feature_families"]["status"]
        self.assertTrue(status["formal_feature_ready"])
        self.assertEqual(status["binding_state"], "BOUND_VERIFIED_ARTIFACT")
        self.assertEqual(status["pit_state"], "PIT_VERIFIED")
        self.assertEqual(status["source_artifact"], "GP12_CANDIDATE_STATUS_BINDING_V1")
        self.assertEqual(status["source_sha256"], STATUS_BINDING_SHA256)
        self.assertEqual(status["blockers"], [])
        self.assertIn("status", out["validated_families"])
        self.assertNotIn("status", out["missing_or_unvalidated_families"])
        self.assertNotIn("STATUS_UPPER_LIMIT_UNBOUND", out["blockers"])
        self.assertEqual(out["ready_factor_ids"], ["F2", "F6", "F7", "F8", "F9", "F10", "F12"])
        self.assertEqual(out["blocked_factor_ids"], ["F1", "F3", "F4", "F5", "F11"])
        self.assertFalse(out["candidate_scoring_ready"])
        self.assertFalse(out["model_freeze_allowed"])
        self.assertFalse(out["oos_metrics_allowed"])
        self.assertFalse(out["historical_strategy_recovered"])


if __name__ == "__main__":
    unittest.main()
