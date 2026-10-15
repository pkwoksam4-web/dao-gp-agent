# MARKET REGIME V0 — SHOCK SOURCE PERSISTENCE PREREG V1

Status: RESEARCH_ONLY
Thresholds: NOT_FROZEN
Production use: PROHIBITED

## Purpose

`SHOCK_TRANSMISSION_STATE` describes how far an external shock has already propagated into local prices. It does not describe whether the underlying shock driver is ending or continuing.

This file preregisters a separate source-state field for future unused windows.

## Source persistence states

Use only evidence available at the evaluation timestamp:

- `SOURCE_RESOLVING` — verified evidence indicates the underlying driver is being removed, reversed, settled, or credibly de-escalated.
- `SOURCE_ONGOING` — the driver remains active with no verified resolution.
- `SOURCE_ESCALATING` — verified new developments indicate increasing magnitude/scope/probability of the original shock.
- `SOURCE_TRANSIENT_REPRICING` — the observed shock is primarily a rapid market repricing without a verified continuing fundamental/event mechanism at the evaluation timestamp.
- `SOURCE_UNVERIFIED` — available evidence is insufficient or conflicting.

No state implies a deterministic next-session return.

## Required separation

For every new external-shock case, record independently:

1. `SEVERITY`
2. `SHOCK_TRANSMISSION_STATE`
3. `SHOCK_SOURCE_PERSISTENCE`
4. `PRE_SIGNAL_TRAJECTORY`
5. local absorption / relative-strength evidence

Do not collapse these into one risk score during this phase.

## Candidate interpretation

- `PENDING_TRANSMISSION + SOURCE_ONGOING/ESCALATING`: strongest reason to restrict new high-beta exposure before local repricing.
- `REALIZED_SHOCK + SOURCE_RESOLVING`: higher repair/mean-reversion plausibility; still requires price acceptance.
- `REALIZED_SHOCK + SOURCE_ONGOING/ESCALATING`: continued downside remains plausible; do not reopen risk solely because a large selloff already occurred.
- `SOURCE_TRANSIENT_REPRICING`: assess whether local price damage has overshot and whether breadth/leadership begin repairing.

These are research hypotheses, not production rules.

## Anti-leakage rule

The source state must be committed before forward-return retrieval. Later event evolution can be logged as new information but cannot be used to rewrite the original state.
