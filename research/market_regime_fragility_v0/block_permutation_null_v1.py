from __future__ import annotations

import math
import random
from typing import Iterable

from primary_inference_v1 import PRIMARY_HORIZON_SESSIONS, compare_models


NULL_VERSION = "BLOCK_PERMUTATION_NULL_V1"
BLOCK_LENGTH = PRIMARY_HORIZON_SESSIONS
DEFAULT_PERMUTATION_REPLICATIONS = 5000
DEFAULT_PERMUTATION_SEED = 20261016
MIN_PERMUTATION_REPLICATIONS = 100


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        raise ValueError("EMPTY_NULL_DISTRIBUTION")
    if p <= 0:
        return sorted_values[0]
    if p >= 1:
        return sorted_values[-1]
    pos = p * (len(sorted_values) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_values[lo]
    weight = pos - lo
    return sorted_values[lo] * (1.0 - weight) + sorted_values[hi] * weight


def _contiguous_blocks(n: int, block_length: int) -> list[list[int]]:
    if n < 2:
        raise ValueError("INSUFFICIENT_OBSERVATIONS")
    if block_length != BLOCK_LENGTH:
        raise ValueError("BLOCK_LENGTH_MISMATCH")
    return [list(range(start, min(start + block_length, n))) for start in range(0, n, block_length)]


def _permuted_block_indices(n: int, block_length: int, rng: random.Random) -> list[int]:
    blocks = _contiguous_blocks(n, block_length)
    shuffled = [block[:] for block in blocks]
    rng.shuffle(shuffled)
    return [index for block in shuffled for index in block]


def block_permutation_delta_tau(
    complex_scores: Iterable[int | float],
    baseline_scores: Iterable[int | float],
    future_3d_returns: Iterable[float],
    *,
    replications: int = DEFAULT_PERMUTATION_REPLICATIONS,
    seed: int = DEFAULT_PERMUTATION_SEED,
    block_length: int = BLOCK_LENGTH,
) -> dict:
    complex_values = list(complex_scores)
    baseline_values = list(baseline_scores)
    return_values = list(future_3d_returns)

    if block_length != BLOCK_LENGTH:
        raise ValueError("BLOCK_LENGTH_MISMATCH")
    if not isinstance(replications, int) or isinstance(replications, bool) or replications < MIN_PERMUTATION_REPLICATIONS:
        raise ValueError("PERMUTATION_REPLICATIONS_TOO_SMALL")
    if not (len(complex_values) == len(baseline_values) == len(return_values)):
        raise ValueError("LENGTH_MISMATCH")

    observed = compare_models(complex_values, baseline_values, return_values)
    rng = random.Random(seed)
    null_deltas: list[float] = []

    for _ in range(replications):
        indices = _permuted_block_indices(len(return_values), block_length, rng)
        permuted_returns = [return_values[i] for i in indices]
        null_result = compare_models(complex_values, baseline_values, permuted_returns)
        null_deltas.append(null_result["delta_tau"])

    observed_delta = observed["delta_tau"]
    ordered = sorted(null_deltas)
    p_one_sided = (1 + sum(1 for value in null_deltas if value >= observed_delta)) / (replications + 1)

    return {
        **observed,
        "null_version": NULL_VERSION,
        "block_length": block_length,
        "permutation_replications": replications,
        "permutation_seed": seed,
        "permutation_p_one_sided": p_one_sided,
        "null_delta_tau_mean": sum(null_deltas) / len(null_deltas),
        "null_delta_tau_q05": _percentile(ordered, 0.05),
        "null_delta_tau_median": _percentile(ordered, 0.50),
        "null_delta_tau_q95": _percentile(ordered, 0.95),
        "production_authorized": False,
        "formal_oos_authorized": False,
    }
