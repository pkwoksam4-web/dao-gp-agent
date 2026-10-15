# MARKET REGIME V0 — SHOCK TRANSMISSION / EVENT-CONTAMINATION PREREG V1

Status: RESEARCH_ONLY
Thresholds: NOT_FROZEN
Production use: PROHIBITED

## Purpose

Prevent two historical-evaluation errors:

1. treating a shock that has already been fully repriced locally as if it were still pending;
2. crediting/blaming an original signal for new information that arrives later inside the forward horizon.

## Shock transmission state

Record independently of shock severity:

- `PENDING_TRANSMISSION`: verified external shock exists but local market has not yet had a normal session to price it.
- `IN_TRANSMISSION`: the local session is actively repricing the external shock.
- `REALIZED_SHOCK`: severe local repricing has already occurred by the evaluation timestamp.
- `REPAIRING`: after prior shock transmission, price acceptance / breadth / leadership are improving.
- `UNRESOLVED`: mixed or insufficient evidence.

No price or percentage threshold is frozen.

## Why severity and transmission are separate

A large shock can be:

- highly severe but already realized, creating high mean-reversion potential;
- moderate in observed local prices but still pending, creating substantial next-session tail risk.

Therefore `SEVERITY_HIGH` does not mechanically imply `PERSISTENT_DOWNSIDE`.

## Pre-signal trajectory

Record a qualitative field before each new window:

- `HEALTHY_PRIOR_STATE`
- `DETERIORATING_PRIOR_STATE`
- `CAPITULATION_AFTER_WEAKNESS`
- `FRESH_BREAK`
- `UNVERIFIED`

Use only information available before/at the signal timestamp. Do not infer this field from forward outcomes.

## Forward-event contamination

For every +1D / +3D / +5D horizon, separately flag material new information that arrived after the signal timestamp:

- `NONE_KNOWN`
- `NEW_EXTERNAL_EVENT`
- `NEW_POLICY_EVENT`
- `NEW_SECTOR_OR_COMPANY_EVENT`
- `MULTIPLE_NEW_EVENTS`
- `UNVERIFIED`

The outcome is never deleted. The contamination flag changes attribution, not the observed return.

## Evaluation rule

For each historical case:

1. freeze state, severity, transmission state and pre-signal trajectory before retrieving outcomes;
2. retrieve forward outcomes;
3. inspect intervening chronology without changing the original labels;
4. mark contamination by horizon;
5. score signal quality separately from new-event impact.

## Decision consequence candidate

- `PENDING_TRANSMISSION`: freeze/restrict new high-beta risk before local repricing; execution remains subject to price/market mechanics.
- `IN_TRANSMISSION`: emphasize preservation and survivors; do not assume the close is the final low.
- `REALIZED_SHOCK`: do not mechanically extrapolate; require absorption/repair evidence.
- `REPAIRING`: selectively re-open risk where RS/catalyst/theme dispersion support it.

No position percentages, execution times, or hard thresholds are frozen.
