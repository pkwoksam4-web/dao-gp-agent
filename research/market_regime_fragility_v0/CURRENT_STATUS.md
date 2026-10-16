# MARKET REGIME / FRAGILITY V0 — CURRENT STATUS

As of: 2026-10-16

Status: RESEARCH_ONLY
Production use: PROHIBITED
Formal OOS: NO
Thresholds: NOT_FROZEN

## Scope

This branch researches the risk-control layer above the frozen stock-selection core. It does not change Core10/Core13 production weights, `XH_REGIME_GATE_V0`, or the rejected standalone MA5 exit rule.

## Governance documents

Mandatory governance / preregistration files now include:

1. `MODULE_PROMOTION_GOVERNANCE_V1.md`
2. `SIMPLE_BASELINE_PREREG_V1.md`
3. `SIMPLE_BASELINE_EXECUTION_CONTRACT_V1.md`
4. `RISK_EVIDENCE_SCORE_MAPPING_V1.md`
5. `PRIMARY_INFERENCE_PREREG_V1.md`
6. `POWER_SAMPLE_PLAN_V1.md`
7. `LAYER_CONFLICT_VETO_CONTRACT_V0.md`
8. `A_SHARE_EXECUTION_CONTRACT_V0.md`
9. `PORTFOLIO_HARD_RISK_GUARD_V0.md`

No research module may advance to `CANDIDATE` without a genuinely unused preregistered set, a locked primary endpoint, a locked baseline, a frozen power/sample requirement and implementation parity.

## Evidence grades

- `E0_CONCEPTUAL`: mechanism only.
- `E1_SINGLE_EPISODE`: one day / one episode; hypothesis-generating only.
- `E2_REPLICATED_RESEARCH`: replicated in consumed historical research windows; not formal OOS.
- `E3_PREREG_UNUSED`: genuinely unused preregistered holdout / prospective shadow evidence.
- `E4_PROSPECTIVE_REPLICATION`: repeated prospective evidence across materially different regimes.

Post-hoc rule repair resets the revised hypothesis to at most `E1` until independently retested.

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

`HEDGE / CAPITAL ROTATION` cannot be cited as a live evidence layer until the required derivatives / ETF / rotation inputs are wired and timestamp-audited.

Use `EVIDENCE SCORE`, not probability language, unless a future module is explicitly calibrated.

## BASELINE_0 / BASELINE_1

### BASELINE_0

`NO_REGIME_OVERLAY`, represented for evaluation bookkeeping only as constant neutral `RISK_EVIDENCE_SCORE = 1`.

### BASELINE_1

`MOMENTUM_VOL_REGIME_V1` is executable in:

`research/market_regime_fragility_v0/simple_baseline_v1.py`

Locked semantics:

- CSI1000 completed daily closes only;
- `MOM20 = close_t / close_{t-20} - 1`;
- `RV20 = sample_stdev(latest 20 simple daily returns) * sqrt(252)`;
- `RV20_MED252 = median(latest 252 completed RV20 observations, inclusive of t)`;
- minimum 272 completed closes;
- invalid / insufficient input => `SIMPLE_UNAVAILABLE`, never imputed.

Batch PIT-safe series runner:

`research/market_regime_fragility_v0/baseline_series_v1.py`

It produces per-session baseline states plus deterministic input SHA256 metadata and has an explicit no-future-leakage test.

## RISK_EVIDENCE_SCORE mapping

Evaluation-only ordinal mapping remains:

- `0 = risk acceptance / risk-on evidence`
- `1 = normal / caution evidence`
- `2 = restricted-risk evidence`
- `3 = severe-risk / active-de-risking evidence`

Canonical market-state mapping is frozen in `RISK_EVIDENCE_SCORE_MAPPING_V1.md`.

No canonical state => `UNAVAILABLE / null`, not NORMAL.

## Primary inference now locked

Inference version:

`PRIMARY_3D_DOWNSIDE_CONCORDANCE_V1`

Executable:

`research/market_regime_fragility_v0/primary_inference_v1.py`

Primary outcome:

`downside_severity_3d = -(close_{t+3}/close_t - 1)`

Primary statistic:

- tie-aware Kendall `tau-b` between ordinal risk score and 3-session downside severity;
- `delta_tau = tau_complex - tau_BASELINE_1`;
- directional primary hypothesis: `delta_tau > 0`.

Locked uncertainty procedure:

- paired circular block bootstrap;
- block length = 3 sessions, matching the primary horizon;
- default bootstrap replications = 5000;
- deterministic seed = 20261016;
- two-sided 95% CI for `delta_tau`;
- one-sided primary alpha = 0.05.

This is an inference contract, not evidence that the complex model works.

## Power / sample-size status

`POWER_SAMPLE_PLAN_V1.md` now fixes the planning method but intentionally does not invent an effect threshold.

Locked design conventions:

- primary estimand = `delta_tau`;
- alpha = 0.05;
- target planning power = 0.80;
- sample-size calculation must use the exact paired comparison procedure and development-only / synthetic assumptions;
- the unused evaluation set may not be used to choose the minimum effect or required sample.

Still unfrozen:

- `minimum_effect_delta_tau = NOT_FROZEN`
- `minimum_sample_required = NOT_FROZEN`

Therefore formal promotion testing remains blocked.

## Formal evaluation preflight

Executable fail-closed preflight:

`research/market_regime_fragility_v0/formal_eval_preflight_v1.py`

It rejects a formal evaluation unless the manifest has, at minimum:

- exact baseline version;
- exact score-mapping version;
- exact inference version;
- exact power-plan version;
- 3-session primary horizon and alpha;
- frozen target power, positive minimum effect and numeric minimum sample;
- classifier version / hash;
- completed-session-only cutoff policy;
- genuinely unused evaluation-set ID / hash;
- definitions locked before set opening;
- no collision with consumed-set IDs.

The preflight can authorize evaluation only. It always returns `production_authorized = false`.

Because the project's actual minimum effect and minimum sample remain unfrozen, the real project cannot yet pass this preflight for formal promotion testing.

## Conflict / execution / portfolio governance

`LAYER_CONFLICT_VETO_CONTRACT_V0.md` retains the rule that upper layers restrict eligibility / risk budget / execution permission; they do not rewrite lower-layer evidence.

Examples:

- Theme CONFIRMED and EXTERNAL_SHOCK may coexist.
- ACTIVE_DE_RISKING may block new high-beta attack exposure but does not imply impossible forced liquidation.
- Strong RS does not silently convert an overheated lifecycle into `CHASE_OK`.
- Strong company catalyst may preserve idiosyncratic eligibility but cannot override market / portfolio hard caps.

No arbitrary numeric hysteresis has been added. State flip / churn remains an explicit complexity cost.

`A_SHARE_EXECUTION_CONTRACT_V0.md` remains preregistered but not a full execution engine. T+1, suspension, price-limit accessibility, liquidity/capacity, fees, slippage and financing assumptions must be frozen identically across models before any production PnL claim.

`PORTFOLIO_HARD_RISK_GUARD_V0.md` remains an `UNIMPLEMENTED_POLICY_LAYER`; no numeric single-name, theme, beta, gross/net, correlation, liquidity or drawdown limits have been invented.

## Verification

Workflow:

`.github/workflows/market-regime-baseline-v1.yml`

TDD evidence for the current extension:

- RED run `38832719000`: failed because the new inference / batch-series / preflight modules did not yet exist.
- Later RED run `38832878860`: failed after adding the requirement that power assumptions must be present in the formal-evaluation manifest.
- GREEN run `38832999991`: SUCCESS; full discovered suite ran `23 tests`, `23/23 PASS`.

This verifies the implementation contracts only. It is not predictive validation or OOS evidence.

## Current blockers

1. `minimum_effect_delta_tau` is not objectively justified or frozen.
2. `minimum_sample_required` is therefore not frozen.
3. Complex native classifier state resolution is still not an executable PIT-auditable classifier suitable for formal comparison.
4. A-share execution numeric assumptions remain unfrozen.
5. Portfolio hard-risk numeric limits remain unfrozen.
6. `HEDGE / CAPITAL ROTATION` remains `UNIMPLEMENTED_DATA_LAYER`.

## Next admissible work

1. Do not open a new unused formal evaluation set.
2. Attempt to justify a minimum economically meaningful `delta_tau` from decision utility, not from unused outcomes.
3. If a defensible effect size can be frozen, implement the versioned Monte Carlo power simulator and derive `minimum_sample_required`.
4. In parallel, make the complex native classifier state-resolution path executable and PIT-auditable without changing its research semantics.
5. Only after both the power gate and classifier gate are closed may a new unused / prospective formal comparison window be opened.
6. Keep Core10/Core13, XH V0 and MA5 production status unchanged.
