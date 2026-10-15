# MARKET REGIME / FRAGILITY V0 — CURRENT STATUS

As of: 2026-10-15

Status: RESEARCH_ONLY
Production use: PROHIBITED
Formal OOS: NO
Thresholds: NOT_FROZEN

## Scope

This branch researches the risk-control layer above the frozen stock-selection core. It does not change Core10/Core13 production weights, XH_REGIME_GATE_V0, or the MA5 exit status.

## Governance now locked

Two governance prerequisites are now mandatory before any promotion:

1. `MODULE_PROMOTION_GOVERNANCE_V1.md`
2. `SIMPLE_BASELINE_PREREG_V1.md`

No research module may move beyond `RESEARCH_ONLY` until it has a locked baseline, primary endpoint, falsification criteria, sample-size / power plan and unused evaluation set.

## Evidence grades

- `E0_CONCEPTUAL`: mechanism only.
- `E1_SINGLE_EPISODE`: one day / one episode; hypothesis-generating only.
- `E2_REPLICATED_RESEARCH`: repeated historical research evidence, but consumed / not formal OOS.
- `E3_PREREG_UNUSED`: preregistered genuinely unused holdout or prospective shadow evidence.
- `E4_PROSPECTIVE_REPLICATION`: independently repeated prospective evidence across materially different regimes.

A post-hoc rule repair resets the revised hypothesis to at most `E1` until independently retested.

The 2026-10-15 same-day stock examples are `E1` unless separately replicated. Existing consumed historical shock / fragility cases can support at most `E2`.

## Current architecture candidate

`EVENT / SHOCK SOURCE`
→ `SHOCK SOURCE PERSISTENCE`
→ `LOCAL TRANSMISSION STATE`
→ `MARKET REGIME`
→ `INTERNAL FRAGILITY / SEVERITY`
→ `HEDGE / CAPITAL ROTATION [UNIMPLEMENTED_DATA_LAYER]`
→ `REGIME ROUTER`
→ `THEME + DISPERSION`
→ `RELATIVE STRENGTH / CATALYST`
→ `TACTICAL TIMING`
→ `EVIDENCE SCORE / PAYOFF`
→ `POSITION BUDGET`

`HEDGE / CAPITAL ROTATION` must not be cited as an observed live evidence layer until its required derivatives / ETF / rotation inputs are actually wired and timestamp-audited.

Use `EVIDENCE SCORE`, not `win probability`, unless a future module is explicitly probability-calibrated.

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

1. Breadth weakness alone is insufficient.
2. Even multi-evidence internal-fragility confirmation can false-alarm.
3. Leadership deterioration + small-cap stress appears more informative than breadth alone.
4. Strong cap-weighted indices can hide broad fragility.
5. Shock detection is not an execution rule.
6. Shock severity is not the same as post-close persistence.
7. A realized shock can still persist.
8. Shock-source persistence must be separated from local transmission.
9. Same-day severity needs pre-signal trajectory.
10. Repair is an eligibility state, not full normalization.
11. Forward-event contamination must be explicit.

These are research findings, not production rules. Their evidence grades differ and must be tracked per hypothesis.

## Rejected shortcuts

- `many decliners -> fragility confirmed`
- `fragility confirmed -> sell`
- `shock -> sell at open`
- `severe realized shock -> more downside must follow`
- `one strong repair day -> full risk budget restored`
- `strong theme breadth -> next-day shock cannot occur`
- `domestic futures alone -> market is safe`
- `single-day stock example -> permanent model rule`

## Baseline requirement

Every future formal comparison must include:

- `BASELINE_0 = NO_REGIME_OVERLAY`
- `BASELINE_1 = MOMENTUM_VOL_REGIME_V1`

`BASELINE_1` uses CSI1000 20-session momentum plus 20-session realized volatility relative to its trailing 252-session median, with no post-hoc tuning.

Primary first formal comparison horizon: 3D.

The complex architecture must demonstrate incremental decision value over the simple baseline on a preregistered unused set before promotion.

## Current decision semantics candidate

- WATCH: reduce chase tolerance only.
- LOW-SEVERITY CONFIRMED: modestly restrict new high-beta risk; require stronger RS/catalyst evidence.
- HIGH-SEVERITY / ACTIVE_DE_RISKING: prioritize capital preservation and exceptional RS survivors.
- PENDING_TRANSMISSION + ongoing/escalating source: strongest reason to freeze/restrict new high-beta exposure before local repricing.
- REALIZED_SHOCK: do not extrapolate automatically; inspect source persistence and absorption/repair.
- REPAIR: selectively reopen risk; full normalization requires continuing breadth/leadership acceptance.

These semantics remain candidate logic. No position percentages, lookback lengths, execution times or numeric thresholds are frozen.

## Validation accounting

Future evaluation must separately record:

- TAIL_RISK_SAVE
- FALSE_ALARM_COST
- MILD_WARNING
- REPAIR_CAPTURE
- state flip / churn count
- data-unavailable rate

Hit rate alone is not an acceptable objective.

## Known governance gaps still open

1. Layer conflict / veto hierarchy and state hysteresis are not yet frozen.
2. A-share execution constraints are not yet implemented in the research comparison layer: T+1, price limits, one-word limit boards, suspension, liquidity/capacity, financing availability, fees and slippage.
3. Portfolio-level hard limits are not yet specified: theme concentration, total beta, correlation/factor concentration, gross exposure, drawdown budget and model-independent kill switches.
4. `HEDGE / CAPITAL ROTATION` is currently unimplemented, not an evidence-producing layer.

These gaps prohibit production promotion even if predictive validation later succeeds.

## Data / access note

Longbridge historical-candlestick quota for this account is currently zero, so historical validation must use auditable public historical carriers / already-authorized project data. Empty Longbridge history responses must never be interpreted as zero values.

## Next admissible work

1. Use the locked promotion template for every module.
2. Implement / reproduce `BASELINE_0` and `BASELINE_1` before adding further model complexity.
3. Freeze the state-to-`RISK_EVIDENCE_SCORE` mapping before the first unused comparison set is opened.
4. Define the minimum-effect / power assumptions; until then `minimum_sample_required = NOT_FROZEN` and promotion is prohibited.
5. Only after steps 1-4, specify conflict/veto/hysteresis, A-share execution constraints and portfolio hard limits.
6. Do not promote any rule to production until a genuinely unused preregistered validation set exists.