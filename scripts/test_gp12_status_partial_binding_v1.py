from __future__ import annotations

import copy
import inspect
import unittest

import gp12_candidate_input_readiness_v1 as mod
from test_gp12_candidate_input_readiness_v1 import (
    load,
    valid_amount_turnover_binding,
    valid_benchmark_evidence,
)
from test_gp12_main_net_flow_readiness_requirement_v1 import valid_requirement


STATUS_PARTIAL_SHA256 = "e565742e9baaa37de5563aa9c51ff2a4a6b9166c1f1579945b865f69d909cb10"


def valid_status_partial_binding() -> dict:
    return {
        "artifact": "GP12_CANDIDATE_STATUS_PARTIAL_BINDING_V1",
        "version": "1.0",
        "strategy_id": "GP12_REBUILD_CANDIDATE_V1",
        "status": "CANDIDATE_ONLY_UNAPPROVED",
        "origin": "NEW_RECONSTRUCTION_CANDIDATE",
        "formal_window": ["2020-06-01", "2026-04-17"],
        "universe_n": 847,
        "required_status_fields": ["is_st", "tradable", "upper_limit"],
        "is_st_source": {
            "provider": "BaoStock+CNINFO transition crosscheck",
            "field": "isST",
            "workflow_run": 33977325822,
            "workflow_head": "a552c5855a96c526178da15837f2d9d488e2d2e6",
            "artifact_name": "gp-pit-st-v480-final-audit",
            "artifact_id": 9972698555,
            "artifact_zip_sha256": "a86d807829deb393e012e93fea44637cefd1759c973fa109e2a728647fa83f58",
            "overlay_csv_sha256": "6ed8ffd09215bccb90f716af26d44f7f590ffd5d455c20841307484a63aaa490",
            "lifecycle_rows": 1021953,
            "lifecycle_pass_n": 847,
            "transition_crosscheck_pass_n": 6,
            "transition_crosscheck_evidence_n": 6,
        },
        "tradable_source": {
            "definition": "True iff pinned Sohu raw has same symbol-date with volume>0 and amount>0; otherwise False for lifecycle-required date",
            "workflow_run": 35052354861,
            "workflow_head": "627e5504afa71774437b9ba1c3cc5d95f188d74d",
            "artifact_name": "gp12-status-tradable-probe-v1",
            "artifact_id": 10428808437,
            "artifact_zip_sha256": "f9808c65cc953953a9920d730640aa2c1c22225a9de75ceddc1ac55433916ec7",
            "probe_json_sha256": "09559b86e0bf7424789c2c6f196b5ca1d2c941fdedb4d8c757ca335084617574",
            "positive_trade_rows": 1011607,
            "nontrade_lifecycle_rows": 10346,
            "provider_status_misflag_n": 5,
            "status1_but_no_positive_trade_n": 0,
        },
        "semantic_state": {
            "is_st": "BOUND_PIT_VERIFIED",
            "tradable": "BOUND_PIT_VERIFIED",
            "upper_limit": "UNBOUND",
        },
        "pit": {
            "scope": "SESSION_CLOSE_NO_LOOKAHEAD_POLICY",
            "same_session_status_usable_before_close": False,
            "historical_provider_publication_timestamp_proven": False,
        },
        "family_ready": False,
        "historical_gp_v11_source_recovered": False,
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
        "blockers": ["STATUS_UPPER_LIMIT_UNBOUND"],
    }


def build(status_binding: dict | None = None) -> dict:
    signature = inspect.signature(mod.build_checkpoint)
    if "status_partial_binding" not in signature.parameters:
        raise AssertionError("build_checkpoint must accept status_partial_binding")
    return mod.build_checkpoint(
        load("data/GP12_CANDIDATE_PARAMETERS_V1.json"),
        load("data/GP12_CANDIDATE_FACTORS_V1.json"),
        load("data/GP12_FORMAL_INPUT_EVIDENCE_V1.json"),
        load("data/GP12_INTRADAY_FORMAL847_BINDING_V1.json"),
        load("data/GP12_PIT_ADJUSTED_CLOSE_BINDING_V1.json"),
        valid_benchmark_evidence(),
        valid_amount_turnover_binding(),
        valid_requirement(),
        valid_status_partial_binding() if status_binding is None else status_binding,
    )


class StatusPartialBindingTests(unittest.TestCase):
    def test_partial_binding_validator_is_exact_and_fail_closed(self):
        self.assertTrue(
            hasattr(mod, "validate_status_partial_binding"),
            "status partial-binding validator is missing",
        )
        value = valid_status_partial_binding()
        self.assertEqual(mod.validate_status_partial_binding(value), STATUS_PARTIAL_SHA256)

        bad = copy.deepcopy(value)
        bad["tradable_source"]["artifact_id"] = 1
        with self.assertRaises(ValueError):
            mod.validate_status_partial_binding(bad)

    def test_partial_binding_replaces_vague_status_blocker_without_promoting_family(self):
        out = build()
        state = out["feature_families"]["status"]
        self.assertFalse(state["formal_feature_ready"])
        self.assertEqual(state["binding_state"], "BOUND_STRUCTURAL_ONLY")
        self.assertEqual(state["pit_state"], "PIT_PARTIAL")
        self.assertEqual(state["source_artifact"], "GP12_CANDIDATE_STATUS_PARTIAL_BINDING_V1")
        self.assertEqual(state["source_sha256"], STATUS_PARTIAL_SHA256)
        self.assertEqual(state["coverage_start"], "2020-06-01")
        self.assertEqual(state["coverage_end"], "2026-04-17")
        self.assertEqual(state["blockers"], ["STATUS_UPPER_LIMIT_UNBOUND"])
        self.assertNotIn("STATUS_SEMANTICS_INCOMPLETE", out["blockers"])
        self.assertIn("STATUS_UPPER_LIMIT_UNBOUND", out["blockers"])
        self.assertEqual(
            out["status_semantic_state"],
            {
                "is_st": "BOUND_PIT_VERIFIED",
                "tradable": "BOUND_PIT_VERIFIED",
                "upper_limit": "UNBOUND",
            },
        )
        self.assertEqual(out["status_partial_binding_sha256"], STATUS_PARTIAL_SHA256)
        self.assertEqual(out["ready_factor_ids"], ["F6", "F7", "F8", "F9", "F10", "F12"])
        self.assertEqual(out["blocked_factor_ids"], ["F1", "F2", "F3", "F4", "F5", "F11"])
        self.assertIn("MAIN_NET_FLOW_UNBOUND", out["blockers"])
        self.assertFalse(out["candidate_scoring_ready"])
        self.assertFalse(out["model_freeze_allowed"])
        self.assertFalse(out["oos_metrics_allowed"])

    def test_partial_binding_cannot_claim_upper_limit_or_family_ready(self):
        for path in ("upper_limit", "family_ready"):
            bad = copy.deepcopy(valid_status_partial_binding())
            if path == "upper_limit":
                bad["semantic_state"]["upper_limit"] = "BOUND_PIT_VERIFIED"
            else:
                bad["family_ready"] = True
            with self.assertRaises(ValueError):
                mod.validate_status_partial_binding(bad)


if __name__ == "__main__":
    unittest.main()
