from __future__ import annotations

import math
import random
from typing import Iterable

PRIMARY_INFERENCE_VERSION = "PRIMARY_3D_DOWNSIDE_CONCORDANCE_V1"
PRIMARY_HORIZON_SESSIONS = 3
DEFAULT_BOOTSTRAP_REPLICATIONS = 5000
DEFAULT_BOOTSTRAP_SEED = 20261016
PRIMARY_ALPHA = 0.05


def _as_finite(values: Iterable[float], name: str) -> list[float]:
    xs = [float(x) for x in values]
    if not xs:
        raise ValueError(f"{name}_EMPTY")
    if not all(math.isfinite(x) for x in xs):
        raise ValueError(f"{name}_NONFINITE")
    return xs


def _validate_scores(values: Iterable[int | float], name: str) -> list[float]:
    xs = _as_finite(values, name)
    if not all(x in (0.0, 1.0, 2.0, 3.0) for x in xs):
        raise ValueError(f"{name}_OUT_OF_RANGE")
    return xs


def kendall_tau_b(x: Iterable[float], y: Iterable[float]) -> float:
    """Tie-aware ordinal concordance.

    When one variable has no comparable ordering information, return 0.0 rather
    than manufacturing signal or failing open. This convention is frozen for
    the evaluation harness and is not a probability estimate.
    """
    xs = _as_finite(x, "X")
    ys = _as_finite(y, "Y")
    if len(xs) != len(ys):
        raise ValueError("LENGTH_MISMATCH")
    if len(xs) < 2:
        raise ValueError("INSUFFICIENT_OBSERVATIONS")

    concordant = 0
    discordant = 0
    ties_x_only = 0
    ties_y_only = 0

    for i in range(len(xs) - 1):
        for j in range(i + 1, len(xs)):
            dx = xs[j] - xs[i]
            dy = ys[j] - ys[i]
            if dx == 0.0 and dy == 0.0:
                continue
            if dx == 0.0:
                ties_x_only += 1
                continue
            if dy == 0.0:
                ties_y_only += 1
                continue
            if dx * dy > 0:
                concordant += 1
            else:
                discordant += 1

    numerator = concordant - discordant
    denominator = math.sqrt(
        (concordant + discordant + ties_x_only)
        * (concordant + discordant + ties_y_only)
    )
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def compare_models(
    complex_scores: Iterable[int | float],
    baseline_scores: Iterable[int | float],
    future_3d_returns: Iterable[float],
) -> dict:
    complex_x = _validate_scores(complex_scores, "COMPLEX_SCORES")
    baseline_x = _validate_scores(baseline_scores, "BASELINE_SCORES")
    returns = _as_finite(future_3d_returns, "FUTURE_3D_RETURNS")
    if not (len(complex_x) == len(baseline_x) == len(returns)):
        raise ValueError("LENGTH_MISMATCH")
    if len(returns) < 2:
        raise ValueError("INSUFFICIENT_OBSERVATIONS")

    downside_severity = [-r for r in returns]
    tau_complex = kendall_tau_b(complex_x, downside_severity)
    tau_baseline = kendall_tau_b(baseline_x, downside_severity)
    return {
        "inference_version": PRIMARY_INFERENCE_VERSION,
        "primary_horizon_sessions": PRIMARY_HORIZON_SESSIONS,
        "n": len(returns),
        "tau_complex": tau_complex,
        "tau_baseline": tau_baseline,
        "delta_tau": tau_complex - tau_baseline,
    }


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        raise ValueError("EMPTY_BOOTSTRAP")
    if p <= 0:
        return sorted_values[0]
    if p >= 1:
        return sorted_values[-1]
    pos = p * (len(sorted_values) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_values[lo]
    w = pos - lo
    return sorted_values[lo] * (1.0 - w) + sorted_values[hi] * w


def _circular_block_indices(n: int, block_length: int, rng: random.Random) -> list[int]:
    if n < 2:
        raise ValueError("INSUFFICIENT_OBSERVATIONS")
    if block_length < 1:
        raise ValueError("INVALID_BLOCK_LENGTH")
    indices: list[int] = []
    while len(indices) < n:
        start = rng.randrange(n)
        indices.extend((start + k) % n for k in range(block_length))
    return indices[:n]


def bootstrap_delta_tau(
    complex_scores: Iterable[int | float],
    baseline_scores: Iterable[int | float],
    future_3d_returns: Iterable[float],
    *,
    replications: int = DEFAULT_BOOTSTRAP_REPLICATIONS,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> dict:
    complex_x = _validate_scores(complex_scores, "COMPLEX_SCORES")
    baseline_x = _validate_scores(baseline_scores, "BASELINE_SCORES")
    returns = _as_finite(future_3d_returns, "FUTURE_3D_RETURNS")
    if not (len(complex_x) == len(baseline_x) == len(returns)):
        raise ValueError("LENGTH_MISMATCH")
    if len(returns) < 2:
        raise ValueError("INSUFFICIENT_OBSERVATIONS")
    if replications < 100:
        raise ValueError("BOOTSTRAP_REPLICATIONS_TOO_SMALL")

    observed = compare_models(complex_x, baseline_x, returns)
    rng = random.Random(seed)
    deltas: list[float] = []
    for _ in range(replications):
        idx = _circular_block_indices(len(returns), PRIMARY_HORIZON_SESSIONS, rng)
        result = compare_models(
            [complex_x[i] for i in idx],
            [baseline_x[i] for i in idx],
            [returns[i] for i in idx],
        )
        deltas.append(result["delta_tau"])

    ordered = sorted(deltas)
    ci_low = _percentile(ordered, PRIMARY_ALPHA / 2.0)
    ci_high = _percentile(ordered, 1.0 - PRIMARY_ALPHA / 2.0)
    one_sided_p = (1 + sum(1 for d in deltas if d <= 0.0)) / (replications + 1)

    return {
        **observed,
        "block_length": PRIMARY_HORIZON_SESSIONS,
        "bootstrap_replications": replications,
        "bootstrap_seed": seed,
        "ci_level": 1.0 - PRIMARY_ALPHA,
        "delta_tau_ci_low": ci_low,
        "delta_tau_ci_high": ci_high,
        "one_sided_p_delta_gt_zero": one_sided_p,
    }
