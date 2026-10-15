# MARKET REGIME / FRAGILITY V0 — CURRENT STATUS

As of: 2026-10-15

Status: RESEARCH_ONLY
Production use: PROHIBITED
Formal OOS: NO
Thresholds: NOT_FROZEN

## Scope

This branch researches the risk-control layer above the frozen stock-selection core. It does not change Core10/Core13 production weights, XH_REGIME_GATE_V0, or the MA5 exit status.

## Current architecture candidate

`EVENT / SHOCK SOURCE`
→ `SHOCK SOURCE PERSISTENCE`
→ `LOCAL TRANSMISSION STATE`
→ `MARKET REGIME`
→ `INTERNAL FRAGILITY / SEVERITY`
→ `HEDGE / CAPITAL ROTATION`
→ `REGIME ROUTER`
→ `THEME + DISPERSION`
→ `RELATIVE STRENGTH / CATALYST`
→ `TACTICAL TIMING`
→ `RISK / REWARD`
→ `POSITION BUDGET`

## Research states retained

### Market / fragility
- NORMAL_RISK_ON
- NORMAL
- INTERNAL_FRAGILITY_WATCH
- INTERNAL_FRAGILITY_CONFIRMED_LOW_SEVERITY
- INTERNAL_FRAGILITY_CONFIRMED_HIGH_SEVERITY
- EXTERNAL_SHOCK
- ACTIVE_DE_RISKING
- REPAIR

### Shock transmission
- PENDING_TRANSMISSION
- IN_TRANSMISSION
- REALIZED_SHOCK
- REPAIRING
- UNRESOLVED

### Shock source persistence
- SOURCE_RESOLVING
- SOURCE_ONGOING
- SOURCE_ESCALATING
- SOURCE_TRANSIENT_REPRICING
- SOURCE_UNVERIFIED

### Pre-signal trajectory
- HEALTHY_PRIOR_STATE
- DETERIORATING_PRIOR_STATE
- CAPITULATION_AFTER_WEAKNESS
- FRESH_BREAK
- UNVERIFIED

### Forward-event contamination
- NONE_KNOWN
- NEW_EXTERNAL_EVENT
- NEW_POLICY_EVENT
- NEW_SECTOR_OR_COMPANY_EVENT
- MULTIPLE_NEW_EVENTS
- UNVERIFIED

## Strongest findings so far

1. **Breadth weakness alone is insufficient.** 2026-04-13 was a clear false-positive control.
2. **Even multi-evidence internal-fragility confirmation can false-alarm.** 2026-04-15 subsequently repaired strongly; temporary profit-taking must be distinguished from persistent risk-budget withdrawal.
3. **Leadership deterioration + small-cap stress adds information.** 2026-05-26 was materially more dangerous than breadth-only controls.
4. **Strong cap-weighted indices can hide broad fragility.** 2026-06-25 showed concentrated technology leadership alongside weak breadth.
5. **Shock detection is not an execution rule.** 2026-06-08 rejected `SHOCK -> SELL AT OPEN` because large gap losses can repair intraday.
6. **Shock severity is not the same as post-close persistence.** 2026-02-02 was a severe realized shock followed by fast repair.
7. **A realized shock can still persist.** 2026-03-19 remained weak through +1D/+3D/+5D; therefore transmission stage alone is insufficient.
8. **Shock-source persistence must be separated from local transmission.** Ongoing geopolitical/macro drivers can keep pressure alive after local repricing begins.
9. **Same-day severity needs pre-signal trajectory.** 2026-07-06 was labeled low severity but weakened further at +1D/+3D; the snapshot understated prior deterioration.
10. **Repair is an eligibility state, not full normalization.** 2026-04-08 supported selective risk reopening, but +1D did not continue immediately and later horizons were event-contaminated.
11. **Forward-event contamination must be explicit.** New events inside +3D/+5D cannot be credited to the original signal.

## Rejected shortcuts

- `many decliners -> fragility confirmed`
- `fragility confirmed -> sell`
- `shock -> sell at open`
- `severe realized shock -> more downside must follow`
- `one strong repair day -> full risk budget restored`
- `strong theme breadth -> next-day shock cannot occur`
- `domestic futures alone -> market is safe`

## Current decision semantics candidate

- WATCH: reduce chase tolerance only.
- LOW-SEVERITY CONFIRMED: modestly restrict new high-beta risk; require stronger RS/catalyst evidence.
- HIGH-SEVERITY / ACTIVE_DE_RISKING: prioritize capital preservation and exceptional RS survivors.
- PENDING_TRANSMISSION + ongoing/escalating source: strongest reason to freeze/restrict new high-beta exposure before local repricing.
- REALIZED_SHOCK: do not extrapolate automatically; inspect source persistence and absorption/repair.
- REPAIR: selectively reopen risk; full normalization requires continuing breadth/leadership acceptance.

No position percentages, lookback lengths, execution times or numeric thresholds are frozen.

## Validation accounting

Future evaluation must separately record:
- TAIL_RISK_SAVE
- FALSE_ALARM_COST
- MILD_WARNING
- REPAIR_CAPTURE

Hit rate alone is not an acceptable objective.

## Data / access note

Longbridge historical-candlestick quota for this account is currently zero, so historical validation must use auditable public historical carriers / already-authorized project data. Empty Longbridge history responses must never be interpreted as zero values.

## Next admissible work

1. Keep the preregistered field schemas fixed.
2. Test fresh unused windows only after committing state/severity/transmission/source/trajectory labels.
3. Prioritize one `PENDING_TRANSMISSION + SOURCE_ONGOING` case and one healthy control with strong breadth/leadership.
4. Complete event-contamination chronology for +1D/+3D/+5D horizons.
5. Quantify tail-risk save separately from false-alarm opportunity cost.
6. Do not promote any rule to production until a genuinely unused preregistered validation set exists.
