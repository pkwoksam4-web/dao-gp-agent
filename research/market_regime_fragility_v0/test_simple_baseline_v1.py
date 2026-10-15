import math
import unittest

from simple_baseline_v1 import (
    BASELINE0_SCORE,
    SIMPLE_NEUTRAL,
    SIMPLE_RISK_OFF,
    SIMPLE_RISK_ON,
    SIMPLE_UNAVAILABLE,
    classify_simple_state,
    compute_latest_baseline,
)


def closes_from_returns(returns, start=100.0):
    closes = [float(start)]
    for r in returns:
        closes.append(closes[-1] * (1.0 + r))
    return closes


class SimpleBaselineV1Tests(unittest.TestCase):
    def test_baseline0_is_constant_neutral_reference(self):
        self.assertEqual(BASELINE0_SCORE, 1)

    def test_classify_state_exact_contract(self):
        self.assertEqual(classify_simple_state(0.01, 0.10, 0.10), SIMPLE_RISK_ON)
        self.assertEqual(classify_simple_state(-0.01, 0.11, 0.10), SIMPLE_RISK_OFF)
        self.assertEqual(classify_simple_state(-0.01, 0.10, 0.10), SIMPLE_NEUTRAL)
        self.assertEqual(classify_simple_state(0.01, 0.11, 0.10), SIMPLE_NEUTRAL)

    def test_insufficient_history_is_unavailable(self):
        result = compute_latest_baseline([100.0] * 271)
        self.assertEqual(result["state"], SIMPLE_UNAVAILABLE)
        self.assertIsNone(result["risk_evidence_score"])
        self.assertEqual(result["reason"], "INSUFFICIENT_HISTORY")

    def test_invalid_close_is_unavailable_not_imputed(self):
        closes = [100.0] * 272
        closes[-5] = 0.0
        result = compute_latest_baseline(closes)
        self.assertEqual(result["state"], SIMPLE_UNAVAILABLE)
        self.assertEqual(result["reason"], "INVALID_CLOSE")

    def test_low_vol_positive_momentum_is_risk_on(self):
        returns = [0.001] * 271
        result = compute_latest_baseline(closes_from_returns(returns))
        self.assertEqual(result["state"], SIMPLE_RISK_ON)
        self.assertEqual(result["risk_evidence_score"], 0)
        self.assertGreater(result["mom20"], 0)
        self.assertLessEqual(result["rv20"], result["rv20_med252"] + 1e-15)

    def test_negative_momentum_with_volatility_spike_is_risk_off(self):
        calm = [0.0002 if i % 2 == 0 else -0.0002 for i in range(251)]
        stressed = [-0.04 if i % 2 == 0 else 0.02 for i in range(20)]
        result = compute_latest_baseline(closes_from_returns(calm + stressed))
        self.assertEqual(result["state"], SIMPLE_RISK_OFF)
        self.assertEqual(result["risk_evidence_score"], 2)
        self.assertLess(result["mom20"], 0)
        self.assertGreater(result["rv20"], result["rv20_med252"])
        self.assertTrue(math.isfinite(result["rv20"]))


if __name__ == "__main__":
    unittest.main()
