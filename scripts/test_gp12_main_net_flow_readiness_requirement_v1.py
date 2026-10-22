from __future__ import annotations

import copy
import inspect
import pathlib
import unittest

import gp12_candidate_input_readiness_v1 as mod
from test_gp12_candidate_input_readiness_v1 import (
    load,
    valid_amount_turnover_binding,
    valid_benchmark_evidence,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
REQUIREMENT_SHA256 = "13577a123a506750d1070c91c96bb603aa727fb9f7826a5cb449efe39963fed3"


def valid_requirement() -> dict:
    return load("data/GP12_MAIN_NET_FLOW_SOURCE_REQUIREMENT_V1.json")


def build(requirement: dict | None = None) -> dict:
    signature = inspect.signature(mod.build_checkpoint)
    if "main_net_flow_requirement" not in signature.parameters:
        raise AssertionError("build_checkpoint must accept main_net_flow_requirement")
    return mod.build_checkpoint(
        load("data/GP12_CANDIDATE_PARAMETERS_V1.json"),
        load("data/GP12_CANDIDATE_FACTORS_V1.json"),
        load("data/GP12_FORMAL_INPUT_EVIDENCE_V1.json"),
        load("data/GP12_INTRADAY_FORMAL847_BINDING_V1.json"),
        load("data/GP12_PIT_ADJUSTED_CLOSE_BINDING_V1.json"),
        valid_benchmark_evidence(),
        valid_amount_turnover_binding(),
        valid_requirement() if requirement is None else requirement,
    )


class MainNetFlowReadinessRequirementTests(unittest.TestCase):
    def test_requirement_validator_is_exact_and_fail_closed(self):
        self.assertTrue(
            hasattr(mod, "validate_main_net_flow_requirement"),
            "main-net-flow requirement validator is missing",
        )
        value = valid_requirement()
        requirement_sha = mod.validate_main_net_flow_requirement(value)
        self.assertEqual(requirement_sha, REQUIREMENT_SHA256)

        bad = copy.deepcopy(value)
        bad["resolution_state"]["credential_available"] = True
        with self.assertRaises(ValueError):
            mod.validate_main_net_flow_requirement(bad)

    def test_requirement_is_exposed_without_promoting_main_net_flow(self):
        out = build()
        self.assertEqual(
            out["main_net_flow_requirement_artifact"],
            "GP12_MAIN_NET_FLOW_SOURCE_REQUIREMENT_V1",
        )
        self.assertEqual(out["main_net_flow_requirement_sha256"], REQUIREMENT_SHA256)
        state = out["feature_families"]["main_net_flow"]
        self.assertFalse(state["formal_feature_ready"])
        self.assertEqual(state["binding_state"], "UNBOUND")
        self.assertEqual(state["pit_state"], "PIT_UNVERIFIED")
        self.assertIsNone(state["source_artifact"])
        self.assertIsNone(state["source_sha256"])
        self.assertEqual(
            state["blockers"],
            [
                "MAIN_NET_FLOW_UNBOUND",
                "TUSHARE_CREDENTIAL_REQUIRED",
                "MAIN_NET_FLOW_PANEL_NOT_MATERIALIZED",
            ],
        )
        self.assertIn("MAIN_NET_FLOW_UNBOUND", out["blockers"])
        self.assertIn("TUSHARE_CREDENTIAL_REQUIRED", out["blockers"])
        self.assertIn("MAIN_NET_FLOW_PANEL_NOT_MATERIALIZED", out["blockers"])
        self.assertEqual(out["next_priority_family"], "main_net_flow")
        self.assertEqual(out["next_priority_blocker"], "MAIN_NET_FLOW_UNBOUND")
        self.assertFalse(out["candidate_scoring_ready"])
        self.assertFalse(out["model_freeze_allowed"])
        self.assertFalse(out["oos_metrics_allowed"])

    def test_requirement_cannot_claim_materialized_or_verified_panel(self):
        for key in ("panel_materialized", "main_net_flow_candidate_pit_verified"):
            bad = copy.deepcopy(valid_requirement())
            bad["resolution_state"][key] = True
            with self.assertRaises(ValueError):
                mod.validate_main_net_flow_requirement(bad)


if __name__ == "__main__":
    unittest.main()
