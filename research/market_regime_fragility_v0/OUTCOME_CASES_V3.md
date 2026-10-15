# MARKET REGIME V0 — OUTCOME REVIEW V3

Status: RESEARCH_ONLY
Thresholds: NOT_FROZEN
Production use: PROHIBITED

The original label for Case E was locked in `PREOUTCOME_CASES_V3.md` before outcome retrieval.

## Case E — 2026-03-19

Locked fields:
- state: `EXTERNAL_SHOCK` + `ACTIVE_DE_RISKING`
- severity: `SEVERITY_HIGH`
- transmission: `REALIZED_SHOCK`
- pre-signal trajectory: `HEALTHY_PRIOR_STATE`

Historical CSI1000 closes:
- signal close 2026-03-19: 7909.23
- +1D 2026-03-20: 7783.43
- +3D 2026-03-24: 7600.86
- +5D 2026-03-26: 7639.38

Forward returns from the signal close:
- +1D: approximately -1.59%
- +3D: approximately -3.90%
- +5D: approximately -3.41%

Diagnostic:

`REALIZED_SHOCK DID NOT MEAN IMMEDIATE MEAN REVERSION`

This is an important counterexample to the 2026-02-02 case. Both cases were severe local shock days by the close, but their post-close paths diverged:

- 2026-02-02 repaired strongly after the realized shock;
- 2026-03-19 continued to weaken materially over the next several sessions.

Therefore `SHOCK_TRANSMISSION_STATE = REALIZED_SHOCK` is necessary but not sufficient for deciding whether risk should be reopened.

## Attribution / contamination

The 2026-03-19 shock source was an ongoing macro/geopolitical complex (Fed repricing, oil/inflation pressure, Middle-East escalation), not a single closed event. Public reporting around the next session continued to describe the same conflict/oil shock rather than an obviously independent new catalyst.

Because a complete event-by-event audit for every intervening session has not yet been bound, forward-event contamination for this window remains:

`UNVERIFIED`

Do not attribute the full +3D/+5D decline solely to information available at the 03-19 close until that chronology is completed.

## Structural lesson

Add a separate **shock-source persistence** field. Transmission stage answers "how much has the local market already priced?"; source persistence answers "is the underlying shock driver resolving, ongoing, or escalating?"

A realized shock can still have persistent downside when the underlying source remains unresolved.

## Current implication

The research hierarchy should now distinguish at least:

`Shock severity`
+ `Local transmission stage`
+ `Shock-source persistence`
+ `Pre-signal local trajectory`
+ `Absorption / repair evidence`

No deterministic mapping, threshold, or position percentage is frozen from this case.
