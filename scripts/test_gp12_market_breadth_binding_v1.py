from __future__ import annotations

import copy
import inspect
import json
import pathlib
import unittest

import gp12_candidate_input_readiness_v1 as readiness
import test_gp12_candidate_input_readiness_v1 as base_tests


ROOT = pathlib.Path(__file__).resolve().parents[1]
EXPECTED_SHA = "337f6dafa3894c55fb8f24b87779d600c9258b1c09f10b8b140d65a120eed1c1"


def valid_market_breadth_binding() -> dict:
    return json.loads(
        (ROOT / "data/GP12_CANDIDATE_MARKET_BREADTH_BINDING_V1.json").read_text(
            encoding="utf-8"
        )
    )


class MarketBreadthBindingTests(unittest.TestCase):
    def test_market_breadth_validator_is_exact_and_fail_closed(self):
        self.assertTrue(
            hasattr(readiness, "validate_market_breadth_binding"),
            "validate_market_breadth_binding is not implemented",
        )
        binding = valid_market_breadth_binding()
        self.assertEqual(readiness.validate_market_breadth_binding(binding), EXPECTED_SHA)

        bad = copy.deepcopy(binding)
        bad["bridge_source"]["candidate_series_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            readiness.validate_market_breadth_binding(bad)

    def test_checkpoint_accepts_and_promotes_only_market_breadth(self):
        signature = inspect.signature(readiness.build_checkpoint)
        self.assertIn("market_breadth_binding", signature.parameters)
        out = readiness.build_checkpoint(
            base_tests.load("data/GP12_CANDIDATE_PARAMETERS_V1.json"),
            base_tests.load("data/GP12_CANDIDATE_FACTORS_V1.json"),
            base_tests.load("data/GP12_FORMAL_INPUT_EVIDENCE_V1.json"),
            base_tests.load("data/GP12_INTRADAY_FORMAL847_BINDING_V1.json"),
            base_tests.load("data/GP12_PIT_ADJUSTED_CLOSE_BINDING_V1.json"),
            base_tests.valid_benchmark_evidence(),
            base_tests.valid_amount_turnover_binding(),
            market_breadth_binding=valid_market_breadth_binding(),
        )
        family = out["feature_families"]["market_breadth"]
        self.assertTrue(family["formal_feature_ready"])
        self.assertEqual(family["binding_state"], "BOUND_VERIFIED_ARTIFACT")
        self.assertEqual(family["pit_state"], "PIT_VERIFIED")
        self.assertEqual(family["source_artifact"], "GP12_CANDIDATE_MARKET_BREADTH_BINDING_V1")
        self.assertEqual(family["source_sha256"], EXPECTED_SHA)
        self.assertEqual(family["blockers"], [])
        self.assertIn("market_breadth", out["validated_families"])
        self.assertIn("F2", out["ready_factor_ids"])
        self.assertNotIn("F2", out["blocked_factor_ids"])
        self.assertNotIn("MARKET_BREADTH_UNBOUND", out["blockers"])
        self.assertFalse(out["feature_families"]["market_adjusted_close"]["formal_feature_ready"])
        self.assertFalse(out["feature_families"]["main_net_flow"]["formal_feature_ready"])
        self.assertFalse(out["candidate_scoring_ready"])
        self.assertFalse(out["model_freeze_allowed"])
        self.assertFalse(out["oos_metrics_allowed"])

    def test_market_breadth_identity_constant_is_pinned(self):
        self.assertEqual(
            getattr(readiness, "MARKET_BREADTH_BINDING_SHA256", None),
            EXPECTED_SHA,
        )


if __name__ == "__main__":
    unittest.main()
