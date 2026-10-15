from __future__ import annotations

import math
import statistics
from typing import Iterable

SIMPLE_RISK_ON = "SIMPLE_RISK_ON"
SIMPLE_RISK_OFF = "SIMPLE_RISK_OFF"
SIMPLE_NEUTRAL = "SIMPLE_NEUTRAL"
SIMPLE_UNAVAILABLE = "SIMPLE_UNAVAILABLE"

BASELINE0_SCORE = 1
SCORE_BY_STATE = {
    SIMPLE_RISK_ON: 0,
    SIMPLE_NEUTRAL: 1,
    SIMPLE_RISK_OFF: 2,
}

MIN_CLOSES = 272
TRADING_DAYS_PER_YEAR = 252


def classify_simple_state(mom20: float, rv20: float, rv20_med252: float) -> str:
    if mom20 > 0 and rv20 <= rv20_med252:
        return SIMPLE_RISK_ON
    if mom20 < 0 and rv20 > rv20_med252:
        return SIMPLE_RISK_OFF
    return SIMPLE_NEUTRAL


def _unavailable(reason: str) -> dict:
    return {
        "state": SIMPLE_UNAVAILABLE,
        "risk_evidence_score": None,
        "reason": reason,
        "mom20": None,
        "rv20": None,
        "rv20_med252": None,
    }


def _validate_closes(closes: list[float]) -> bool:
    return all(math.isfinite(x) and x > 0 for x in closes)


def _daily_returns(closes: list[float]) -> list[float]:
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]


def _annualized_sample_stdev(values: list[float]) -> float:
    return statistics.stdev(values) * math.sqrt(TRADING_DAYS_PER_YEAR)


def compute_latest_baseline(closes: Iterable[float]) -> dict:
    xs = [float(x) for x in closes]
    if len(xs) < MIN_CLOSES:
        return _unavailable("INSUFFICIENT_HISTORY")
    if not _validate_closes(xs):
        return _unavailable("INVALID_CLOSE")

    xs = xs[-MIN_CLOSES:]
    returns = _daily_returns(xs)

    rv20_series = []
    for end_idx in range(19, len(returns)):
        window = returns[end_idx - 19 : end_idx + 1]
        rv20_series.append(_annualized_sample_stdev(window))

    trailing_rv20 = rv20_series[-252:]
    if len(trailing_rv20) != 252:
        return _unavailable("INSUFFICIENT_RV_HISTORY")

    mom20 = xs[-1] / xs[-21] - 1.0
    rv20 = trailing_rv20[-1]
    rv20_med252 = statistics.median(trailing_rv20)
    state = classify_simple_state(mom20, rv20, rv20_med252)

    return {
        "state": state,
        "risk_evidence_score": SCORE_BY_STATE[state],
        "reason": None,
        "mom20": mom20,
        "rv20": rv20,
        "rv20_med252": rv20_med252,
    }
