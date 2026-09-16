from __future__ import annotations

import inspect
import unittest

import gp12_candidate_input_readiness_v1 as readiness


class MarketBreadthBindingRedTests(unittest.TestCase):
    def test_market_breadth_validator_is_exposed(self):
        self.assertTrue(
            hasattr(readiness, "validate_market_breadth_binding"),
            "validate_market_breadth_binding is not implemented",
        )

    def test_checkpoint_accepts_market_breadth_binding(self):
        signature = inspect.signature(readiness.build_checkpoint)
        self.assertIn(
            "market_breadth_binding",
            signature.parameters,
            "build_checkpoint does not accept market_breadth_binding",
        )

    def test_market_breadth_identity_constant_is_pinned(self):
        self.assertEqual(
            getattr(readiness, "MARKET_BREADTH_BINDING_SHA256", None),
            "337f6dafa3894c55fb8f24b87779d600c9258b1c09f10b8b140d65a120eed1c1",
        )


if __name__ == "__main__":
    unittest.main()
