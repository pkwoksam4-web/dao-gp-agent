from __future__ import annotations

import copy
import inspect
import unittest

import gp12_candidate_input_readiness_v1 as mod
import test_gp12_candidate_input_readiness_v1 as base


STATUS_BINDING_SHA256 = "aaf1c352d74ce2a0408ea454f8d9deaaea7d9428629ed33ecccdd09f1a2ce96a"


def valid_status_binding() -> dict:
    return {
        "artifact": "GP12_CANDIDATE_STATUS_BINDING_V1",
        "version": "1.0",
        "strategy_id": "GP12_REBUILD_CANDIDATE_V1",
        "status": "CANDIDATE_ONLY_UNAPPROVED",
        "origin": "NEW_RECONSTRUCTION_CANDIDATE",
        "formal_window": ["2020-06-01", "2026-04-17"],
        "universe_n": 847,
        "formal_symbol_n": 844,
        "na_symbols": ["600074.SH", "600485.SH", "600677.SH"],
        "lifecycle_rows": 1021953,
        "expected_trade_rows": 1011607,
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
            "workflow_run": 35052354861,
            "workflow_head": "627e5504afa71774437b9ba1c3cc5d95f188d74d",
            "artifact_name": "gp12-status-tradable-probe-v1",
            "artifact_id": 10428808437,
            "artifact_zip_sha256": "f9808c65cc953953a9920d730640aa2c1c22225a9de75ceddc1ac55433916ec7",
            "probe_json_sha256": "09559b86e0bf7424789c2c6f196b5ca1d2c941fdedb4d8c757ca335084617574",
            "definition": "True iff pinned Sohu raw has same symbol-date with volume>0 and amount>0; otherwise False for lifecycle-required date",
            "positive_trade_rows": 1011607,
            "nontrade_lifecycle_rows": 10346,
            "provider_status_misflag_n": 5,
            "status1_but_no_positive_trade_n": 0,
        },
        "upper_limit_source": {
            "field": "upper_limit",
            "definition": "True iff a tradable lifecycle symbol-date closes at the verified exchange-rule upper price limit; False on no-limit sessions and on non-tradable lifecycle dates",
            "workflow_run": 35069676486,
            "workflow_head": "1e07ada2b3480221c0dbc3417bf911965a1dc8ed",
            "artifact_name": "gp12-upper-limit-full-source-v1",
            "artifact_id": 10435886487,
            "artifact_zip_sha256": "ef9692c9feef8bda9d55b7d96f124925d6beb02b33123424725c8caf7f9ef8bf",
            "panel_sha256": "a08a0705621c41bfdc704ff281f6f3a6c01ba17485e3981d55707f18303ad08e",
            "audit_json_sha256": "44ada4ca0429963ae19f9c4ed4a5ba60e915e31b3677172cfefe63384ba1d6b8",
            "positive_trade_rows": 1011607,
            "formal_symbol_n": 844,
            "no_limit_rows": 199,
            "special_no_limit_rows": 9,
            "upper_limit_true_rows": 25742,
            "reference_panel_run": 35064830592,
            "reference_panel_artifact_id": 10435322179,
            "reference_panel_artifact_zip_sha256": "d15fb949b2318ec4713cd83223535c54ea2b36ce4e50f3981b069fe8b0e80728",
            "reference_panel_sha256": "39f4df606abd4629ab28fac1d7444e73dfdeb3bb36c6764673f378463bd08c7e",
            "special_evidence_artifact": "GP12_STATUS_SPECIAL_NO_LIMIT_EVIDENCE_V1",
            "special_evidence_sha256": "ab97091336089aedb984eca782468e0cfd331e1db96f397fb1a172fbea6db039",
            "canonical_truth_sha256": "d11b415b74d44d63d1aa927e8652f395dd039c28f6e1b4c24964e53759405308",
            "canonical_truth_overlap_rows": 896827,
            "canonical_truth_overlap_symbols": 698,
            "truth_close_mismatch_n": 0,
            "truth_no_limit_mismatch_n": 0,
            "truth_price_mismatch_n": 0,
            "truth_boolean_mismatch_n": 0,
        },
        "composition_source": {
            "workflow_run": 35070179201,
            "workflow_head": "e4ae255deddfbe7f98e56a1eb5e3ae2c77b6330d",
            "artifact_name": "gp12-status-full-composition-v1",
            "artifact_id": 10435349883,
            "artifact_zip_sha256": "fd3d3ca4fe573e9ad0a212e96e4acda8eeb740276f77148a262211834e8cd94c",
            "panel_sha256": "dadf57d1d845491caf7f6fdf785f32c7e9f56e23f2476f5f66d7d26d1c65d0a9",
            "audit_json_sha256": "8dd50470a6d7b4d149a9a9af30665f220351de00d13149c9aa42b9fccff3a83b",
            "pit_st_final_run": 33977325822,
            "pit_st_final_artifact_id": 9972698555,
            "pit_st_lifecycle_csv_sha256": "6ed8ffd09215bccb90f716af26d44f7f590ffd5d455c20841307484a63aaa490",
            "lifecycle_rows": 1021953,
            "tradable_true_rows": 1011607,
            "tradable_false_rows": 10346,
            "upper_limit_true_rows": 25742,
            "nontradable_upper_limit_true_rows": 0,
            "duplicate_symbol_dates": 0,
            "missing_status_values": 0,
        },
        "semantic_state": {
            "is_st": "BOUND_PIT_VERIFIED",
            "tradable": "BOUND_PIT_VERIFIED",
            "upper_limit": "BOUND_PIT_VERIFIED",
        },
        "pit": {
            "scope": "SESSION_CLOSE_NO_LOOKAHEAD_POLICY",
            "same_session_status_usable_before_close": False,
            "historical_provider_publication_timestamp_proven": False,
        },
        "family_ready": True,
        "historical_gp_v11_source_recovered": False,
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
        "blockers": [],
    }


def build_with_full_status(binding: dict | None = None) -> dict:
    signature = inspect.signature(mod.build_checkpoint)
    if "status_binding" not in signature.parameters:
        raise AssertionError("build_checkpoint must accept status_binding")
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
        status_binding=valid_status_binding() if binding is None else binding,
    )


class StatusFullBindingTests(unittest.TestCase):
    def test_full_status_validator_is_exact_and_fail_closed(self):
        self.assertTrue(hasattr(mod, "validate_status_binding"), "full status validator is missing")
        self.assertEqual(mod.validate_status_binding(valid_status_binding()), STATUS_BINDING_SHA256)
        bad = copy.deepcopy(valid_status_binding())
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
