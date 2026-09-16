from __future__ import annotations

import copy
import unittest

import gp12_status_binding_v1 as sut


class StatusBindingValidatorTests(unittest.TestCase):
    def _binding(self):
        return {
            "artifact": "GP12_CANDIDATE_STATUS_BINDING_V1",
            "version": "1.0",
            "origin": "NEW_RECONSTRUCTION_CANDIDATE",
            "formal_window": ["2020-06-01", "2026-04-17"],
            "family": "status",
            "required_fields": ["is_st", "tradable", "upper_limit"],
            "semantic_state": {
                "is_st": "BOUND_PIT_VERIFIED",
                "tradable": "BOUND_PIT_VERIFIED",
                "upper_limit": "BOUND_PIT_VERIFIED",
            },
            "family_ready": True,
            "blockers": [],
            "panel_rows": 1021953,
            "panel_symbols": 847,
            "tradable_rows": 1011607,
            "nontradable_rows": 10346,
            "special_no_limit_rows": 9,
            "panel_sha256": "a" * 64,
            "panel_audit_payload_sha256": "b" * 64,
            "panel_audit_file_sha256": "c" * 64,
            "sohu_reference_run_id": 35064830592,
            "sohu_reference_panel_sha256": "d" * 64,
            "sohu_raw_run_id": 34192233633,
            "sohu_raw_parquet_sha256": "bc72238d046378cf3b6fa61723e86fb43f1c491ac3da86d76932e3185f60e1eb",
            "pit_st_final_run_id": 33977325822,
            "pit_st_merged_run_id": 33971534669,
            "partial_truth_rows": 896827,
            "partial_truth_symbols": 698,
            "partial_truth_sha256": "d11b415b74d44d63d1aa927e8652f395dd039c28f6e1b4c24964e53759405308",
            "partial_truth_mismatches": {"no_limit": 0, "price": 0, "boolean": 0},
            "special_evidence_artifact": "GP12_STATUS_SPECIAL_NO_LIMIT_EVIDENCE_V1",
            "special_evidence_entries": 9,
            "pit_policy": "SESSION_CLOSE_NO_LOOKAHEAD_POLICY",
            "historical_provider_publication_timestamp_proven": False,
            "historical_gp_v11_source_recovered": False,
            "model_freeze_allowed": False,
            "oos_metrics_allowed": False,
        }

    def test_accepts_exact_full_status_binding(self):
        result = sut.validate_status_binding(self._binding())
        self.assertEqual(result["family"], "status")
        self.assertTrue(result["family_ready"])
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["panel_rows"], 1021953)
        self.assertEqual(result["tradable_rows"], 1011607)

    def test_rejects_any_semantic_or_blocker_regression(self):
        for field in ("is_st", "tradable", "upper_limit"):
            bad = copy.deepcopy(self._binding())
            bad["semantic_state"][field] = "UNBOUND"
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    sut.validate_status_binding(bad)
        bad = self._binding()
        bad["blockers"] = ["STATUS_UPPER_LIMIT_UNBOUND"]
        with self.assertRaises(ValueError):
            sut.validate_status_binding(bad)

    def test_rejects_wrong_exact_counts(self):
        for key in ("panel_rows", "panel_symbols", "tradable_rows", "nontradable_rows", "special_no_limit_rows"):
            bad = self._binding()
            bad[key] += 1
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    sut.validate_status_binding(bad)

    def test_rejects_truth_mismatch_or_wrong_truth_identity(self):
        bad = copy.deepcopy(self._binding())
        bad["partial_truth_mismatches"]["price"] = 1
        with self.assertRaises(ValueError):
            sut.validate_status_binding(bad)
        bad = self._binding()
        bad["partial_truth_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            sut.validate_status_binding(bad)

    def test_rejects_provenance_or_gate_overclaim(self):
        for key in (
            "historical_provider_publication_timestamp_proven",
            "historical_gp_v11_source_recovered",
            "model_freeze_allowed",
            "oos_metrics_allowed",
        ):
            bad = self._binding()
            bad[key] = True
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    sut.validate_status_binding(bad)

    def test_rejects_missing_or_malformed_hashes(self):
        for key in (
            "panel_sha256", "panel_audit_payload_sha256", "panel_audit_file_sha256",
            "sohu_reference_panel_sha256", "sohu_raw_parquet_sha256", "partial_truth_sha256",
        ):
            bad = self._binding()
            bad[key] = "bad"
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    sut.validate_status_binding(bad)


if __name__ == "__main__":
    unittest.main()
