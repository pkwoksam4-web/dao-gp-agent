# MARKET REGIME V0 — OUTCOME REVIEW V4

Status: RESEARCH_ONLY
Thresholds: NOT_FROZEN
Production use: PROHIBITED

The original labels for Case F were locked in `PREOUTCOME_CASES_V4.md` before outcome retrieval.

## Case F — 2026-04-08

Locked fields:
- market state: `REPAIR`
- severity: `SEVERITY_MEDIUM`
- shock transmission: `REPAIRING`
- shock-source persistence: `SOURCE_RESOLVING`
- pre-signal trajectory: `DETERIORATING_PRIOR_STATE`

Historical CSI1000 closes:
- signal close 2026-04-08: 7955.77
- +1D 2026-04-09: 7921.45
- +3D 2026-04-13: 8025.57
- +5D 2026-04-15: 8106.16

Forward returns from signal close:
- +1D: approximately -0.43%
- +3D: approximately +0.88%
- +5D: approximately +1.89%

Diagnostic:

`SOURCE_RESOLVING + REPAIRING` was consistent with a recoverable market state, but not with a guaranteed next-session continuation.

The +1D result shows why the model should not equate a very strong repair day with immediate momentum continuation. The +3D/+5D path remained positive from the signal close, supporting selective reopening of risk rather than a full defensive stance.

## Forward-event contamination

A new geopolitical development appeared inside the multi-day horizon: by 2026-04-13 contemporaneous reporting described a new US blockade action against Iranian port traffic. This is material new information relative to the 04-08 close.

Contamination flags:
- +1D: `NONE_KNOWN` based on the evidence reviewed so far;
- +3D: `NEW_EXTERNAL_EVENT`;
- +5D: `NEW_EXTERNAL_EVENT`.

Therefore the +3D/+5D outcomes are recorded but should not be treated as a clean isolated test of the 04-08 repair state.

## Structural lesson

The repair layer should distinguish:

1. `repair eligibility` — enough evidence exists to allow selected risk back into the portfolio;
2. `repair continuation` — not guaranteed and must still be validated by subsequent breadth/leadership/price acceptance;
3. `full regime normalization` — requires more than one strong rebound day.

This supports the existing principle:

`REPAIR -> selective reopening`, not `REPAIR -> full risk budget`.

No position fraction, confirmation period, or numeric threshold is frozen.
