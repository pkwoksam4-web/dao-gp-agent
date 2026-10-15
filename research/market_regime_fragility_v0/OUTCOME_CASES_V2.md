# INTERNAL FRAGILITY V0 — OUTCOME REVIEW V2

Status: RESEARCH_ONLY
Thresholds: NOT_FROZEN
Production use: PROHIBITED

The pre-outcome labels for these cases are locked in `PREOUTCOME_CASES_V2.md` and are not changed below.

## Case C — 2026-02-02

Locked state:
- `EXTERNAL_SHOCK`
- `ACTIVE_DE_RISKING`
- `SEVERITY_HIGH`

Observed contemporaneous signal close:
- CSI1000 close: 7975.43
- same-day CSI1000 decline: about -3.39%
- >4,600 A-share decliners; major indices all fell more than 2%
- resource / commodity stress and external macro repricing were already transmitted into the local close

Forward CSI1000 outcomes from the signal close:
- +1D: +2.93% (published next-session index return)
- +3D close (2026-02-05): 8068.08, approximately +1.16% from signal close
- +5D close (2026-02-09): 8233.78, approximately +3.24% from signal close

Diagnostic:

`HIGH-SEVERITY PERSISTENCE FORECAST = FALSE ALARM`

The shock classification itself was not necessarily wrong: the local market did experience a severe cross-asset liquidation. The error is treating **shock severity at the close** as equivalent to **expected persistence after the close**.

The evidence supports a new distinction:

- shock magnitude / severity;
- shock transmission stage;
- post-shock persistence / repair.

By the 02-02 close, a large part of the external shock had already been transmitted into A-share prices. The next session repaired sharply. Therefore a close-time rule that extrapolates a realized shock forward would over-de-risk.

## Case D — 2026-07-06

Locked state:
- `INTERNAL_FRAGILITY_WATCH`
- `SEVERITY_LOW`

Observed signal close:
- CSI1000 close: 8472.60
- more than 3,500 stocks declined
- headline indices ranged from flat Shanghai to weaker Shenzhen/ChiNext
- turnover remained high but contracted; several independent receiving themes remained active

Forward CSI1000 outcomes:
- +1D (2026-07-07): 8301.80, approximately -2.02%
- +3D (2026-07-09): 8300.08, approximately -2.04%
- +5D (2026-07-13): 7787.85, approximately -8.08%

Diagnostic:

`LOW-SEVERITY CLASSIFICATION = TOO OPTIMISTIC FOR NEAR-TERM RISK`

However, the +5D horizon contains a material new event cluster on 07-13 (including renewed external/geopolitical stress and another severe broad-market selloff). Therefore the full -8.08% must not be attributed mechanically to information available on 07-06.

The +1D / +3D weakness still indicates that the original low-severity classification missed an important feature: **pre-existing deterioration / multi-session damage before the signal close**.

## Structural lessons

### 1. Add `SHOCK_TRANSMISSION_STATE`

External shock evidence should carry a separate stage field:

- `PENDING_TRANSMISSION` — external shock visible before local repricing;
- `IN_TRANSMISSION` — local market is actively repricing the shock;
- `REALIZED_SHOCK` — severe local damage has already occurred by the signal close;
- `REPAIRING` — local acceptance/breadth is recovering after transmission;
- `UNRESOLVED` — evidence mixed.

The 2026-08-18/19 research window is closer to `PENDING_TRANSMISSION` before the A-share open, while 2026-02-02 at the close is closer to `REALIZED_SHOCK`.

These two states must not share the same execution consequence.

### 2. Add `PRE_SIGNAL_TRAJECTORY`

The model should record whether fragility is:

- a one-day divergence after otherwise healthy conditions;
- an extension of a multi-session deterioration;
- a late-stage capitulation after sustained weakness;
- a fresh break from a stable regime.

This field is descriptive; no lookback threshold is frozen.

The 2026-07-06 case suggests that a same-day snapshot can understate risk when growth/small-cap damage was already accumulating before the signal close.

### 3. Add `FORWARD_EVENT_CONTAMINATION`

For historical evaluation, a later unrelated/new shock inside the +3D/+5D horizon must be flagged rather than silently credited to the original signal.

Candidate flags:
- `NONE_KNOWN`
- `NEW_EXTERNAL_EVENT`
- `NEW_POLICY_EVENT`
- `NEW_COMPANY/SECTOR_EVENT`
- `UNVERIFIED`

Outcomes remain recorded, but interpretation must separate original-signal information from new information arriving later.

## Current research consequence

- `EXTERNAL_SHOCK` is a detection layer, not a persistence forecast.
- `PENDING_TRANSMISSION` can justify aggressive restriction of new high-beta risk before local repricing.
- `REALIZED_SHOCK` requires absorption/repair assessment before extrapolating further downside.
- Internal fragility severity must incorporate the pre-signal trajectory, not only the current-session snapshot.
- Forward validation must flag event contamination to avoid falsely crediting or blaming the model for information that did not exist at signal time.
