from __future__ import annotations

import datetime as dt
import json
import pathlib
import unittest

import gp12_candidate_benchmark_v1 as mod


ROOT = pathlib.Path(__file__).resolve().parents[1]


def fake_binding() -> dict:
    return {
        "artifact": "GP12_CANDIDATE_BENCHMARK_BINDING_V1",
        "strategy_id": "GP12_REBUILD_CANDIDATE_V1",
        "status": "CANDIDATE_ONLY_UNAPPROVED",
        "definition_origin": "NEW_RECONSTRUCTION_CANDIDATE",
        "benchmark": {
            "name": "CSI All Share",
            "code": "000985",
            "eastmoney_secid": "1.000985",
            "series": "daily_close",
        },
        "formal_window": {"start": "2020-06-01", "end": "2026-04-17"},
        "pit_policy": {
            "timezone": "Asia/Shanghai",
            "session_close": "15:00:00",
            "same_session_close_usable_before_close": False,
        },
        "pins": {
            "parameters_sha256": mod.SUPPORTED_PARAMETERS_SHA256,
            "factors_sha256": mod.SUPPORTED_FACTORS_SHA256,
            "frozen_calendar_legacy_sha256": mod.FROZEN_CALENDAR_LEGACY_SHA256,
            "frozen_calendar_n": 1426,
        },
        "claims": {
            "gp_v11_benchmark_recovered": False,
            "historical_recovery_claim_allowed": False,
        },
    }


class CandidateBenchmarkBindingV1Tests(unittest.TestCase):
    def test_binding_is_candidate_only_and_preserves_existing_hashes(self):
        binding = json.loads((ROOT / "data/GP12_CANDIDATE_BENCHMARK_V1.json").read_text(encoding="utf-8"))
        factors = json.loads((ROOT / "data/GP12_CANDIDATE_FACTORS_V1.json").read_text(encoding="utf-8"))
        parameters = json.loads((ROOT / "data/GP12_CANDIDATE_PARAMETERS_V1.json").read_text(encoding="utf-8"))

        out = mod.validate_binding(binding, factors, parameters)
        self.assertEqual(out["blockers"], [])
        self.assertTrue(out["candidate_binding_valid"])
        self.assertFalse(out["gp_v11_benchmark_recovered"])
        self.assertEqual(out["factors_sha256"], mod.SUPPORTED_FACTORS_SHA256)
        self.assertEqual(out["parameters_sha256"], mod.SUPPORTED_PARAMETERS_SHA256)

    def test_factor_or_parameter_drift_fails_closed(self):
        binding = fake_binding()
        factors = {"x": 1}
        parameters = {"y": 2}
        out = mod.validate_binding(binding, factors, parameters)
        self.assertIn("FACTORS_HASH_DRIFT", out["blockers"])
        self.assertIn("PARAMETERS_HASH_DRIFT", out["blockers"])
        self.assertFalse(out["candidate_binding_valid"])

    def test_exact_calendar_coverage_and_close_pit_policy_pass(self):
        expected = ["2020-06-01", "2020-06-02", "2020-06-03"]
        rows = [
            {"date": "2020-06-01", "close": 4010.1},
            {"date": "2020-06-02", "close": 4022.2},
            {"date": "2020-06-03", "close": 4033.3},
        ]
        out = mod.validate_close_series(rows, expected, fake_binding())
        self.assertEqual(out["blockers"], [])
        self.assertTrue(out["calendar_full_coverage"])
        self.assertTrue(out["pit_policy_valid"])
        self.assertEqual(out["row_n"], 3)
        self.assertEqual(out["first"], expected[0])
        self.assertEqual(out["last"], expected[-1])
        self.assertEqual(out["known_at_first"], "2020-06-01T15:00:00+08:00")

    def test_missing_extra_duplicate_or_bad_close_keeps_blocker_open(self):
        expected = ["2020-06-01", "2020-06-02"]
        cases = [
            ([{"date": "2020-06-01", "close": 1.0}], "BENCHMARK_CALENDAR_GAP"),
            ([{"date": "2020-06-01", "close": 1.0}, {"date": "2020-06-02", "close": 2.0}, {"date": "2020-06-03", "close": 3.0}], "BENCHMARK_OUT_OF_CALENDAR_DATE"),
            ([{"date": "2020-06-01", "close": 1.0}, {"date": "2020-06-01", "close": 2.0}], "BENCHMARK_DUPLICATE_DATE"),
            ([{"date": "2020-06-01", "close": 1.0}, {"date": "2020-06-02", "close": 0.0}], "BENCHMARK_INVALID_CLOSE"),
        ]
        for rows, blocker in cases:
            with self.subTest(blocker=blocker):
                out = mod.validate_close_series(rows, expected, fake_binding())
                self.assertIn(blocker, out["blockers"])
                self.assertFalse(out["candidate_benchmark_blocker_closed"])

    def test_pit_timestamp_cannot_be_before_session_close(self):
        self.assertEqual(
            mod.close_known_at("2020-06-01", fake_binding()),
            dt.datetime(2020, 6, 1, 15, 0, tzinfo=mod.SHANGHAI),
        )
        self.assertFalse(
            mod.close_available_at(
                "2020-06-01",
                dt.datetime(2020, 6, 1, 14, 59, 59, tzinfo=mod.SHANGHAI),
                fake_binding(),
            )
        )
        self.assertTrue(
            mod.close_available_at(
                "2020-06-01",
                dt.datetime(2020, 6, 1, 15, 0, tzinfo=mod.SHANGHAI),
                fake_binding(),
            )
        )


if __name__ == "__main__":
    unittest.main()
