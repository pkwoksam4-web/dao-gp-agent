from __future__ import annotations

import copy
import json
import pathlib
import tempfile
import unittest

import gp12_candidate_package_review_v1 as candidate


ROOT = pathlib.Path(__file__).resolve().parents[1]
PARAMETERS = ROOT / "data/GP12_CANDIDATE_PARAMETERS_V1.json"
FACTORS = ROOT / "data/GP12_CANDIDATE_FACTORS_V1.json"


def valid_evidence() -> dict:
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
        "factors_sha256": "b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e",
        "parameters_sha256": "22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204",
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
            "note": "candidate-only PIT policy evidence",
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


def review_with(evidence: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        p = pathlib.Path(tmp) / "benchmark.json"
        p.write_text(json.dumps(evidence), encoding="utf-8")
        return candidate.review_package(PARAMETERS, FACTORS, p)


class CandidateBenchmarkIntegrationTests(unittest.TestCase):
    def test_valid_candidate_benchmark_closes_only_benchmark_subblocker(self):
        report = review_with(valid_evidence())
        self.assertTrue(report["candidate_review_passed"])
        self.assertTrue(report["candidate_benchmark_validated"])
        self.assertTrue(report["candidate_benchmark_blocker_closed"])
        self.assertFalse(report["benchmark_feature_binding_allowed"])
        self.assertFalse(report["market_adjusted_close_substitution_allowed"])
        self.assertFalse(report["historical_benchmark_recovered"])
        self.assertFalse(report["historical_strategy_recovered"])
        self.assertFalse(report["real_feature_inputs_validated"])
        self.assertFalse(report["model_freeze_allowed"])
        self.assertFalse(report["oos_metrics_allowed"])
        self.assertEqual(report["adoption_status"], "UNAPPROVED")
        self.assertIn("NEW_STRATEGY_ADOPTION_REQUIRED", report["blockers"])
        self.assertEqual(report["candidate_benchmark"]["code"], "000985")
        self.assertEqual(
            report["asset_hashes"]["factor_definition_sha256"],
            valid_evidence()["factors_sha256"],
        )
        self.assertEqual(
            report["asset_hashes"]["parameter_sha256"],
            valid_evidence()["parameters_sha256"],
        )

    def test_missing_benchmark_evidence_fails_closed(self):
        missing = ROOT / "data/DOES_NOT_EXIST_BENCHMARK_VALIDATION.json"
        report = candidate.review_package(PARAMETERS, FACTORS, missing)
        self.assertFalse(report["candidate_review_passed"])
        self.assertFalse(report["candidate_benchmark_validated"])
        self.assertFalse(report["candidate_benchmark_blocker_closed"])
        self.assertIn("CANDIDATE_BENCHMARK_EVIDENCE_INVALID", report["blockers"])
        self.assertIn("NEW_STRATEGY_ADOPTION_REQUIRED", report["blockers"])

    def test_benchmark_drift_blockage_or_historical_claim_fails_closed(self):
        cases = {
            "factor_hash": lambda x: x.__setitem__("factors_sha256", "0" * 64),
            "benchmark_code": lambda x: x["benchmark"].__setitem__("code", "000300"),
            "calendar": lambda x: x["calendar"].__setitem__("full_coverage", False),
            "pit": lambda x: x["pit"].__setitem__("policy_valid", False),
            "source": lambda x: x["source"].__setitem__("identity_valid", False),
            "upstream_blocker": lambda x: x["blockers"].append("BENCHMARK_CALENDAR_GAP"),
            "closure_false": lambda x: x.__setitem__("candidate_benchmark_blocker_closed", False),
            "historical_claim": lambda x: x.__setitem__("gp_v11_benchmark_recovered", True),
            "claim_allowed": lambda x: x.__setitem__("historical_recovery_claim_allowed", True),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                evidence = copy.deepcopy(valid_evidence())
                mutate(evidence)
                report = review_with(evidence)
                self.assertFalse(report["candidate_review_passed"])
                self.assertFalse(report["candidate_benchmark_validated"])
                self.assertFalse(report["candidate_benchmark_blocker_closed"])
                self.assertIn("CANDIDATE_BENCHMARK_EVIDENCE_INVALID", report["blockers"])
                self.assertFalse(report["historical_benchmark_recovered"])
                self.assertFalse(report["market_adjusted_close_substitution_allowed"])


if __name__ == "__main__":
    unittest.main()
