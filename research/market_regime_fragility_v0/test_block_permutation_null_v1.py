import random
import unittest

from block_permutation_null_v1 import (
    BLOCK_LENGTH,
    NULL_VERSION,
    _permuted_block_indices,
    block_permutation_delta_tau,
)
from primary_inference_v1 import compare_models


COMPLEX = [0, 0, 1, 1, 2, 2, 3, 3, 3, 2, 1, 0]
BASELINE = [1] * len(COMPLEX)
RETURNS = [0.06, 0.04, 0.02, 0.01, -0.01, -0.02, -0.05, -0.07, -0.06, -0.03, 0.01, 0.04]


class BlockPermutationNullV1Tests(unittest.TestCase):
    def test_permuted_indices_use_each_row_once_and_preserve_within_block_order(self):
        rng = random.Random(7)
        idx = _permuted_block_indices(8, BLOCK_LENGTH, rng)
        self.assertEqual(sorted(idx), list(range(8)))

        original_blocks = [(0, 1, 2), (3, 4, 5), (6, 7)]
        pos = {value: i for i, value in enumerate(idx)}
        for block in original_blocks:
            positions = [pos[value] for value in block]
            self.assertEqual(positions, list(range(positions[0], positions[0] + len(block))))

    def test_observed_delta_matches_primary_inference(self):
        result = block_permutation_delta_tau(COMPLEX, BASELINE, RETURNS, replications=200, seed=11)
        observed = compare_models(COMPLEX, BASELINE, RETURNS)
        self.assertEqual(result["null_version"], NULL_VERSION)
        self.assertEqual(result["delta_tau"], observed["delta_tau"])
        self.assertEqual(result["block_length"], 3)

    def test_same_seed_is_deterministic(self):
        a = block_permutation_delta_tau(COMPLEX, BASELINE, RETURNS, replications=200, seed=99)
        b = block_permutation_delta_tau(COMPLEX, BASELINE, RETURNS, replications=200, seed=99)
        self.assertEqual(a["permutation_p_one_sided"], b["permutation_p_one_sided"])
        self.assertEqual(a["null_delta_tau_mean"], b["null_delta_tau_mean"])
        self.assertEqual(a["null_delta_tau_q05"], b["null_delta_tau_q05"])
        self.assertEqual(a["null_delta_tau_q95"], b["null_delta_tau_q95"])

    def test_p_value_is_bounded_and_uses_plus_one_correction(self):
        result = block_permutation_delta_tau(COMPLEX, BASELINE, RETURNS, replications=200, seed=5)
        self.assertGreater(result["permutation_p_one_sided"], 0.0)
        self.assertLessEqual(result["permutation_p_one_sided"], 1.0)
        self.assertGreaterEqual(result["permutation_p_one_sided"], 1 / 201)

    def test_block_length_is_frozen_to_primary_horizon(self):
        with self.assertRaisesRegex(ValueError, "BLOCK_LENGTH_MISMATCH"):
            block_permutation_delta_tau(
                COMPLEX,
                BASELINE,
                RETURNS,
                replications=200,
                seed=1,
                block_length=2,
            )

    def test_too_few_replications_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "PERMUTATION_REPLICATIONS_TOO_SMALL"):
            block_permutation_delta_tau(COMPLEX, BASELINE, RETURNS, replications=99, seed=1)

    def test_length_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "LENGTH_MISMATCH"):
            block_permutation_delta_tau(COMPLEX[:-1], BASELINE, RETURNS, replications=200, seed=1)

    def test_constant_complex_and_baseline_produce_zero_observed_delta(self):
        constant = [1] * len(RETURNS)
        result = block_permutation_delta_tau(constant, constant, RETURNS, replications=200, seed=3)
        self.assertEqual(result["delta_tau"], 0.0)
        self.assertEqual(result["permutation_p_one_sided"], 1.0)


if __name__ == "__main__":
    unittest.main()
