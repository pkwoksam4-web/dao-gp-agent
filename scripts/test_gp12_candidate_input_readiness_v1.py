from __future__ import annotations

import copy
import inspect
import json
import pathlib
import unittest

import gp12_candidate_input_readiness_v1 as mod


ROOT = pathlib.Path(__file__).resolve().parents[1]
FACTOR_SHA256 = "b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e"
PARAMETER_SHA256 = "22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204"


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def valid_benchmark_evidence() -> dict:
    return {
        "artifact": "GP12_CANDIDATE_BENCHMARK_VALIDATION_V1",
        "status": "PASS_CANDIDATE_BENCHMARK_V1",
        "strategy_id": "GP12_REBUILD_CANDIDATE_V1",
        "binding_status": "CANDIDATE_ONLY_UNAPPROVED",
        "definition_origin": "NEW_RECONSTRUCTION_CANDIDATE",
        "benchmark": {
            "name": "CSI All Share",
            "local_name": "中证全指",
            "code": "000985",
            "eastmoney_secid": "1.000985",
            "series": "daily_close",
            "series_construction": "INDEX_OWN_DAILY_CLOSE_NO_CONSTITUENT_RECONSTRUCTION",
            "source": "Eastmoney historical daily kline endpoint, fqt=0, klt=101",
        },
        "formal_window": ["2020-06-01", "2026-04-17"],
        "binding_sha256": "73e9f84bd5a7a01ae43a6d780c66279a48c63743636e4fb3611996bead544c1a",
        "factors_sha256": FACTOR_SHA256,
        "parameters_sha256": PARAMETER_SHA256,
        "factors_parameters_hashes_unchanged": True,
        "calendar": {
            "expected_n": 1426,
            "observed_n": 1426,
            "first": "2020-06-01",
            "last": "2026-04-17",
            "legacy_sha256": "0bfa32175dfccbd24d30eb7ceb0605f6cde2ed0bcc31ac2cac61479ba812add0",
            "semantic_sha256": "5a872a47cf7a338cc48aa628b8de46053fddc3ed161a2617550199d0607efae7",
            "full_coverage": True,
        },
        "pit": {
            "policy_valid": True,
            "scope": "SESSION_CLOSE_NO_LOOKAHEAD_POLICY",
            "known_at_first": "2020-06-01T15:00:00+08:00",
            "known_at_last": "2026-04-17T15:00:00+08:00",
            "same_session_close_usable_before_close": False,
            "historical_provider_publication_timestamp_proven": False,
        },
        "source": {
            "provider": "Eastmoney",
            "endpoint": "https://push2his.eastmoney.com/api/qt/stock/kline/get",
            "secid": "1.000985",
            "payload_code": "000985",
            "payload_name": "中证全指",
            "klt": 101,
            "fqt": 0,
            "series_construction": "INDEX_OWN_DAILY_CLOSE_NO_CONSTITUENT_RECONSTRUCTION",
            "identity_valid": True,
        },
        "close_series_sha256": "e9541cf917893b214ebe31a8602914c793e162bc5280137bfac88d243b75a73e",
        "close_csv": "CSI_ALL_SHARE_000985_DAILY_CLOSE_20200601_20260417.csv",
        "candidate_benchmark_blocker_closed": True,
        "gp_v11_benchmark_recovered": False,
        "historical_recovery_claim_allowed": False,
        "blockers": [],
    }


def valid_amount_turnover_binding() -> dict:
    return {
        "artifact": "GP12_CANDIDATE_AMOUNT_TURNOVER_BINDING_V1",
        "version": "1.0",
        "strategy_id": "GP12_REBUILD_CANDIDATE_V1",
        "status": "CANDIDATE_ONLY_UNAPPROVED",
        "origin": "NEW_RECONSTRUCTION_CANDIDATE",
        "formal_window": ["2020-06-01", "2026-04-17"],
        "universe_n": 847,
        "formal_symbol_n": 844,
        "na_symbols": ["600074.SH", "600485.SH", "600677.SH"],
        "expected_trade_rows": 1011607,
        "amount_source": {
            "field": "amount",
            "unit": "CNY",
            "artifact_name": "gp-sohu-full-raw-v482-reaudit",
            "workflow_run": 34192233633,
            "artifact_id": 10042614517,
            "artifact_zip_sha256": "cee7e91f1fda605f7c3bdf41c3f4a7796feeae83f8c3702e50900e6af3fa9550",
            "positive_amount_rows": 1011607,
        },
        "turnover_source": {
            "provider": "BaoStock",
            "field": "turn",
            "source_unit": "percent",
            "candidate_unit": "decimal_ratio",
            "workflow_run": 34981310300,
            "workflow_head": "66571bc360f77ba989c47dbe6e8dc0708aac46f9",
            "artifact_name": "gp12-baostock-turnover-full-v1",
            "artifact_id": 10403125922,
            "artifact_zip_sha256": "9fcda20e7d7ab01ce22ea377c15726126dfd62d28b5ad7df6d694fda545be6ad",
            "audit_json_sha256": "7c3c85315f53956df96a59f2703210077bdc67d758d454c77de7edce03e24e0c",
            "panel_csv_sha256": "90b483f5f55668c0243523c5cf997c5251611e59dc5007fa6429ddf441b515a4",
            "observed_turnover_rows": 1011607,
            "materialized_rows": 1011607,
            "provider_status_override_n": 5,
            "turnover_precision_reconstruction_n": 9,
            "residual_denominator_binding_artifact": "GP12_CANDIDATE_TURNOVER_RESIDUAL_DENOMINATORS_V1",
            "residual_denominator_binding_sha256": "74e00c11098c4fe46b1b60048306b5b64c6836ca929c54fdb58064e4a14fce4f",
        },
        "coverage": {
            "amount_turnover_full_window_aligned": True,
            "turnover_ratio_candidate_pit_verified": True,
            "pit_scope": "SESSION_CLOSE_NO_LOOKAHEAD_POLICY",
            "same_session_turnover_usable_before_close": False,
            "historical_provider_publication_timestamp_proven": False,
        },
        "historical_gp_v11_source_recovered": False,
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
        "blockers": [],
    }


def build(
    benchmark: dict | None = None,
    turnover: dict | None = None,
) -> dict:
    signature = inspect.signature(mod.build_checkpoint)
    if "amount_turnover_binding" not in signature.parameters:
        raise AssertionError("build_checkpoint must accept amount_turnover_binding")
    return mod.build_checkpoint(
        load("data/GP12_CANDIDATE_PARAMETERS_V1.json"),
        load("data/GP12_CANDIDATE_FACTORS_V1.json"),
        load("data/GP12_FORMAL_INPUT_EVIDENCE_V1.json"),
        load("data/GP12_INTRADAY_FORMAL847_BINDING_V1.json"),
        load("data/GP12_PIT_ADJUSTED_CLOSE_BINDING_V1.json"),
        valid_benchmark_evidence() if benchmark is None else benchmark,
        valid_amount_turnover_binding() if turnover is None else turnover,
    )


class CandidateInputReadinessTests(unittest.TestCase):
    def test_amount_turnover_binding_validator_is_exact_and_fail_closed(self):
        self.assertTrue(
            hasattr(mod, "validate_amount_turnover_binding"),
            "amount-turnover binding validator is missing",
        )
        valid = valid_amount_turnover_binding()
        binding_sha = mod.validate_amount_turnover_binding(valid)
        self.assertRegex(binding_sha, r"^[0-9a-f]{64}$")

        bad = copy.deepcopy(valid)
        bad["turnover_source"]["panel_csv_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            mod.validate_amount_turnover_binding(bad)

    def test_current_verified_overlay_promotes_amount_turnover_only(self):
        out = build()
        self.assertEqual(out["artifact"], "GP12_CANDIDATE_INPUT_READINESS_V1")
        self.assertEqual(
            out["validated_families"],
            [
                "amount_turnover",
                "intraday_15m",
                "intraday_60m",
                "market_calendar",
                "stock_adjusted_close",
            ],
        )
        self.assertEqual(out["ready_factor_ids"], ["F6", "F7", "F8", "F9", "F10", "F12"])
        self.assertEqual(out["blocked_factor_ids"], ["F1", "F2", "F3", "F4", "F5", "F11"])
        self.assertEqual(out["asset_hashes"]["factor_definition_sha256"], FACTOR_SHA256)
        self.assertEqual(out["asset_hashes"]["parameter_sha256"], PARAMETER_SHA256)
        self.assertTrue(out["candidate_benchmark_reference_validated"])
        self.assertEqual(out["candidate_benchmark_reference"]["code"], "000985")
        self.assertEqual(out["candidate_benchmark_reference"]["scope"], "BENCHMARK_REFERENCE_ONLY")
        self.assertFalse(out["benchmark_feature_binding_allowed"])
        self.assertFalse(out["market_adjusted_close_substitution_allowed"])
        self.assertFalse(out["feature_families"]["market_adjusted_close"]["formal_feature_ready"])
        self.assertEqual(
            out["feature_families"]["market_adjusted_close"]["blockers"],
            ["MARKET_ADJUSTED_CLOSE_FEATURE_BINDING_UNBOUND"],
        )
        amount_turnover = out["feature_families"]["amount_turnover"]
        self.assertTrue(amount_turnover["formal_feature_ready"])
        self.assertEqual(amount_turnover["binding_state"], "BOUND_VERIFIED_ARTIFACT")
        self.assertEqual(amount_turnover["pit_state"], "PIT_VERIFIED")
        self.assertEqual(amount_turnover["blockers"], [])
        self.assertEqual(
            amount_turnover["source_artifact"],
            "GP12_CANDIDATE_AMOUNT_TURNOVER_BINDING_V1",
        )
        self.assertRegex(amount_turnover["source_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotIn("MARKET_BENCHMARK_UNBOUND", out["blockers"])
        self.assertNotIn("ADJUSTED_CLOSE_PIT_UNVERIFIED", out["blockers"])
        self.assertNotIn("INTRADAY_15M_UNBOUND", out["blockers"])
        self.assertNotIn("INTRADAY_60M_UNBOUND", out["blockers"])
        self.assertNotIn("TURNOVER_RATIO_UNBOUND", out["blockers"])
        self.assertIn("MAIN_NET_FLOW_UNBOUND", out["blockers"])
        self.assertIn("MARKET_ADJUSTED_CLOSE_FEATURE_BINDING_UNBOUND", out["blockers"])
        self.assertEqual(out["next_priority_family"], "main_net_flow")
        self.assertEqual(out["next_priority_blocker"], "MAIN_NET_FLOW_UNBOUND")
        self.assertFalse(out["candidate_scoring_ready"])
        self.assertFalse(out["real_feature_inputs_validated"])
        self.assertFalse(out["model_freeze_allowed"])
        self.assertFalse(out["oos_metrics_allowed"])
        self.assertFalse(out["historical_benchmark_recovered"])
        self.assertFalse(out["historical_strategy_recovered"])

    def test_invalid_turnover_binding_fails_closed_without_promoting_family(self):
        evidence = copy.deepcopy(valid_amount_turnover_binding())
        evidence["turnover_source"]["workflow_run"] = 1
        with self.assertRaises(ValueError):
            build(turnover=evidence)

    def test_invalid_benchmark_reference_fails_closed_without_promoting_market_feature(self):
        evidence = copy.deepcopy(valid_benchmark_evidence())
        evidence["benchmark"]["code"] = "000300"
        out = build(benchmark=evidence)
        self.assertEqual(out["asset_hashes"]["factor_definition_sha256"], FACTOR_SHA256)
        self.assertEqual(out["asset_hashes"]["parameter_sha256"], PARAMETER_SHA256)
        self.assertFalse(out["candidate_benchmark_reference_validated"])
        self.assertIn("CANDIDATE_BENCHMARK_EVIDENCE_INVALID", out["blockers"])
        self.assertFalse(out["feature_families"]["market_adjusted_close"]["formal_feature_ready"])
        self.assertTrue(out["feature_families"]["amount_turnover"]["formal_feature_ready"])
        self.assertFalse(out["market_adjusted_close_substitution_allowed"])
        self.assertFalse(out["candidate_scoring_ready"])


if __name__ == "__main__":
    unittest.main()
