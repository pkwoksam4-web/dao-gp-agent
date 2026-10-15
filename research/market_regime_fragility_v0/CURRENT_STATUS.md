# MARKET REGIME / FRAGILITY V0 — CURRENT STATUS

As of: 2026-10-15

Status: RESEARCH_ONLY
Production use: PROHIBITED
Formal OOS: NO
Thresholds: NOT_FROZEN

## Scope

This branch researches the risk-control layer above the frozen stock-selection core. It does not change Core10/Core13 production weights, XH_REGIME_GATE_V0, or the MA5 exit status.

## Governance now locked

Mandatory governance documents:

1. `MODULE_PROMOTION_GOVERNANCE_V1.md`
2. `SIMPLE_BASELINE_PREREG_V1.md`
3. `SIMPLE_BASELINE_EXECUTION_CONTRACT_V1.md`
4. `RISK_EVIDENCE_SCORE_MAPPING_V1.md`
5. `LAYER_CONFLICT_VETO_CONTRACT_V0.md`
6. `A_SHARE_EXECUTION_CONTRACT_V0.md`
7. `PORTFOLIO_HARD_RISK_GUARD_V0.md`

No research module may move beyond `RESEARCH_ONLY` until it has a locked baseline, primary endpoint, falsification criteria, sample-size / power plan and unused evaluation set. Production additionally requires executable A-share constraints and model-independent hard portfolio limits.

## Evidence grades

- `E0_CONCEPTUAL`: mechanism only.
- `E1_SINGLE_EPISODE`: one day / one episode; hypothesis-generating only.
- `E2_REPLICATED_RESEARCH`: repeated historical research evidence, but consumed / not formal OOS.
- `E3_PREREG_UNUSED`: preregistered genuinely unused holdout or prospective shadow evidence.
- `E4_PROSPECTIVE_REPLICATION`: independently repeated prospective evidence across materially different regimes.

A post-hoc rule repair resets the revised hypothesis to at most `E1` until independently retested.

The 2026-10-15 same-day stock examples are `E1` unless separately replicated. Existing consumed historical shock / fragility cases can support at most `E2`.

## Current architecture candidate

`MODEL-INDEPENDENT HARD RISK GUARD [UNIMPLEMENTED_POLICY_LAYER]`
→ `DATA VALIDITY / PIT`
→ `EVENT / SHOCK SOURCE`
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
→ `A-SHARE EXECUTION FEASIBILITY [PREREGISTERED, NOT FULLY IMPLEMENTED]`

`HEDGE / CAPITAL ROTATION` must not be cited as an observed live evidence layer until its required derivatives / ETF / rotation inputs are actually wired and timestamp-audited.

Use `EVIDENCE SCORE`, not `win probability`, unless a future module is explicitly probability-calibrated.

## Baseline implementation status

### BASELINE_0

`NO_REGIME_OVERLAY`

For scalar evaluation bookkeeping only, represented as constant neutral `RISK_EVIDENCE_SCORE = 1`. This is not a trading signal.

### BASELINE_1

`MOMENTUM_VOL_REGIME_V1`

Executable implementation:

`research/market_regime_fragility_v0/simple_baseline_v1.py`

Locked executable semantics:

- CSI1000 completed daily closes;
- `MOM20 = close_t / close_{t-20} - 1`;
- `RV20 = sample stdev(latest 20 simple daily returns) * sqrt(252)`;
- `RV20_MED252 = median(latest 252 completed RV20 observations, inclusive of t)`;
- minimum 272 completed closes;
- invalid / insufficient data => `SIMPLE_UNAVAILABLE`, never imputed;
- state boundaries exactly as frozen in `SIMPLE_BASELINE_EXECUTION_CONTRACT_V1.md`.

Verification workflow:

`.github/workflows/market-regime-baseline-v1.yml`

TDD evidence:

- RED: run `38759835264` failed as expected because `simple_baseline_v1` did not yet exist.
- GREEN: run `38759943020` succeeded after the deterministic implementation was added.
- Latest governance-triggered verification: run `38760082335` succeeded at score-mapping commit `b5d606e466f3b2ee043bb06fbc8ef97d1c560aae`.

This verifies the current unit contract only; it does not constitute predictive validation.

## RISK_EVIDENCE_SCORE normalization

Evaluation-only mapping is frozen in `RISK_EVIDENCE_SCORE_MAPPING_V1.md`:

- `0 = risk acceptance / risk-on evidence`
- `1 = normal / caution evidence`
- `2 = restricted-risk evidence`
- `3 = severe-risk / active-de-risking evidence`

Canonical complex-model mapping:

- `NORMAL_RISK_ON -> 0`
- `NORMAL -> 1`
- `INTERNAL_FRAGILITY_WATCH -> 1`
- `INTERNAL_FRAGILITY_CONFIRMED_LOW_SEVERITY -> 2`
- `INTERNAL_FRAGILITY_CONFIRMED_HIGH_SEVERITY -> 3`
- `EXTERNAL_SHOCK -> 2`
- `ACTIVE_DE_RISKING -> 3`
- `REPAIR -> 1`

No resolved canonical state => `UNAVAILABLE / null`, not NORMAL.

`SHOCK_SOURCE_PERSISTENCE` and `LOCAL_TRANSMISSION_STATE` are not independently added to the score in V1. Their interaction belongs to the native classifier / conflict contract; this avoids double counting and ad-hoc score inflation.

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
- `unavailable upstream data -> assume NORMAL`
- `strong lower-layer stock evidence -> override hard portfolio limit`

## Baseline requirement

Every future formal comparison must include:

- `BASELINE_0 = NO_REGIME_OVERLAY`
- `BASELINE_1 = MOMENTUM_VOL_REGIME_V1`

Primary first formal comparison horizon: 3D.

The complex architecture must demonstrate incremental decision value over the simple baseline on a preregistered unused set before promotion.

## Layer conflict / veto governance

`LAYER_CONFLICT_VETO_CONTRACT_V0.md` now defines narrow veto semantics.

Key rule:

- upper layers restrict eligibility / risk budget / execution permission;
- they do not rewrite lower-layer evidence to make a narrative internally consistent.

Examples:

- confirmed theme + external shock may coexist;
- `ACTIVE_DE_RISKING` can block new high-beta attack exposure but does not force impossible liquidation;
- strong RS does not silently override an overheated lifecycle into `CHASE_OK`;
- strong company catalyst may preserve idiosyncratic eligibility under weak theme breadth, but cannot override market / hard-risk caps.

For the first formal comparison, canonical market state is resolved once per completed A-share session. No arbitrary 2-day / 3-day hysteresis has been invented. Daily state flips are counted as a complexity penalty; any later numeric hysteresis requires a new version and unused test set.

## A-share execution governance

`A_SHARE_EXECUTION_CONTRACT_V0.md` is preregistered but not yet a complete execution engine.

It requires:

- explicit decision timestamp and data cutoff;
- T+1 sell-eligible quantity accounting;
- no fills during suspension;
- no assumed fills on one-word limit-up / limit-down without auditable executable liquidity;
- explicit blocked / partial / full fill states;
- identical execution assumptions across complex model and baselines;
- frozen liquidity, capacity, costs, slippage and financing availability before any production PnL claim.

Economic-PnL eligibility remains blocked until those numeric execution assumptions are frozen.

## Portfolio hard-risk governance

`PORTFOLIO_HARD_RISK_GUARD_V0.md` defines a required model-independent safeguard layer.

Before production it must freeze numeric limits for at least:

- single-name concentration;
- theme / industry concentration;
- gross and net exposure;
- portfolio beta;
- correlation / factor clusters;
- liquidity / capacity concentration;
- daily loss / drawdown escalation;
- maximum drawdown / kill switch;
- unavailable-data exposure.

No numeric limits are invented in V0. Therefore this remains `UNIMPLEMENTED_POLICY_LAYER` and is a production blocker.

## Current decision semantics candidate

- WATCH: reduce chase tolerance only.
- LOW-SEVERITY CONFIRMED: modestly restrict new high-beta risk; require stronger RS/catalyst evidence.
- HIGH-SEVERITY / ACTIVE_DE_RISKING: prioritize capital preservation and exceptional RS survivors.
- PENDING_TRANSMISSION + ongoing/escalating source: strongest reason to freeze/restrict new high-beta exposure before local repricing.
- REALIZED_SHOCK: do not extrapolate automatically; inspect source persistence and absorption/repair.
- REPAIR: selectively reopen risk; full normalization requires continuing breadth/leadership acceptance.

These semantics remain candidate logic. No position percentages, hard beta thresholds, execution times or numeric portfolio limits are frozen.

## Validation accounting

Future evaluation must separately record:

- TAIL_RISK_SAVE
- FALSE_ALARM_COST
- MILD_WARNING
- REPAIR_CAPTURE
- state flip / churn count
- data-unavailable rate

Hit rate alone is not an acceptable objective.

## Remaining blockers

1. Minimum-effect / power assumptions are not frozen; `minimum_sample_required = NOT_FROZEN`.
2. Exact primary inference implementation / uncertainty procedure for `3D downside concordance` is not yet frozen.
3. Complex native classifier state-resolution logic still needs an executable, PIT-auditable implementation before unused formal comparison.
4. A-share execution numeric assumptions remain unfrozen.
5. Portfolio hard-risk numeric mandate remains unfrozen.
6. `HEDGE / CAPITAL ROTATION` remains `UNIMPLEMENTED_DATA_LAYER`.

These gaps prohibit production promotion even if descriptive historical cases remain supportive.

## Data / access note

Longbridge historical-candlestick quota for this account is currently zero, so historical validation must use auditable public historical carriers / already-authorized project data. Empty Longbridge history responses must never be interpreted as zero values.

## Next admissible work

1. Freeze the exact primary statistic / uncertainty method for 3D downside concordance without opening a new unused set.
2. Define the minimum economically meaningful effect and derive a power / sample requirement; if a defensible effect size cannot yet be justified, keep promotion blocked rather than inventing one.
3. Add a batch baseline-series runner using only completed CSI1000 bars and provenance metadata.
4. Build an evaluation harness that refuses to run a formal comparison unless the baseline version, score mapping, inference contract and unused-set manifest are all locked.
5. Only then open any new unused historical / prospective evaluation window.
6. Do not promote any rule to production until a genuinely unused preregistered validation set exists.
