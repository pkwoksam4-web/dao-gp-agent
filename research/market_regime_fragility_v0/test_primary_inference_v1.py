import math
import unittest

from primary_inference_v1 import (
    PRIMARY_HORIZON_SESSIONS,
    bootstrap_delta_tau,
    compare_models,
    kendall_tau_b,
)


class PrimaryInferenceV1Tests(unittest.TestCase):
    def test_primary_horizon_is_locked_to_three_sessions(self):
        self.assertEqual(PRIMARY_HORIZON_SESSIONS, 3)

    def test_kendall_tau_b_perfect_concordance(self):
        self.assertAlmostEqual(kendall_tau_b([0, 1, 2, 3], [0.0, 1.0, 2.0, 3.0]), 1.0)

    def test_kendall_tau_b_perfect_discordance(self):
        self.assertAlmostEqual(kendall_tau_b([0, 1, 2, 3], [3.0, 2.0, 1.0, 0.0]), -1.0)

    def test_kendall_tau_b_handles_ties(self):
        value = kendall_tau_b([0, 0, 1, 1, 2, 2], [0.0, 0.2, 0.1, 0.5, 0.4, 0.8])
        self.assertTrue(math.isfinite(value))
        self.assertGreater(value, 0.0)

    def test_compare_models_uses_downside_severity_not_raw_return(self):
        future_3d_returns = [0.04, 0.02, -0.01, -0.05, -0.08, -0.12]
        complex_scores = [0, 0, 1, 2, 3, 3]
        baseline_scores = [1, 1, 1, 1, 2, 2]
        result = compare_models(complex_scores, baseline_scores, future_3d_returns)
        self.assertGreater(result["tau_complex"], result["tau_baseline"])
        self.assertGreater(result["delta_tau"], 0.0)

    def test_bootstrap_is_deterministic_for_same_seed(self):
        future_3d_returns = [0.05, 0.02, 0.01, -0.01, -0.03, -0.06, -0.04, 0.00, 0.03, -0.02, -0.07, -0.09]
        complex_scores = [0, 0, 1, 1, 2, 3, 2, 1, 0, 2, 3, 3]
        baseline_scores = [1, 1, 1, 1, 1, 2, 2, 1, 1, 2, 2, 2]
        first = bootstrap_delta_tau(complex_scores, baseline_scores, future_3d_returns, replications=200, seed=17)
        second = bootstrap_delta_tau(complex_scores, baseline_scores, future_3d_returns, replications=200, seed=17)
        self.assertEqual(first, second)
        self.assertEqual(first["block_length"], PRIMARY_HORIZON_SESSIONS)

    def test_mismatched_lengths_fail_closed(self):
        with self.assertRaises(ValueError):
            compare_models([0, 1], [0], [0.01, -0.01])


if __name__ == "__main__":
    unittest.main()
