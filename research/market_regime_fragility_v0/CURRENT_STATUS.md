# MARKET REGIME / FRAGILITY V0 — CURRENT STATUS

As of: 2026-10-16

Status: RESEARCH_ONLY
Production use: PROHIBITED
Formal OOS: NO
Thresholds: NOT_FROZEN

## Scope

This branch researches the risk-control layer above the frozen stock-selection core. It does not change Core10/Core13 production weights, `XH_REGIME_GATE_V0`, or the rejected standalone MA5 exit rule.

## Governance / preregistration

Mandatory files:

1. `MODULE_PROMOTION_GOVERNANCE_V1.md`
2. `STATE_ENUM_ABLATION_GOVERNANCE_V1.md`
3. `PORTFOLIO_HARD_RISK_GUARD_V1.md`
4. `SIMPLE_BASELINE_PREREG_V1.md`
5. `SIMPLE_BASELINE_EXECUTION_CONTRACT_V1.md`
6. `RISK_EVIDENCE_SCORE_MAPPING_V1.md`
7. `PRIMARY_INFERENCE_PREREG_V1.md`
8. `POWER_SAMPLE_PLAN_V1.md`
9. `MINIMUM_EFFECT_JUSTIFICATION_STATUS_V1.md`
10. `LAYER_CONFLICT_VETO_CONTRACT_V0.md`
11. `A_SHARE_EXECUTION_CONTRACT_V0.md`
12. `docs/superpowers/specs/2026-10-16-atomic-evidence-ledger-canonical-classifier-design.md`
13. `docs/superpowers/plans/2026-10-16-atomic-evidence-ledger-canonical-classifier.md`

No module may advance to `CANDIDATE` without a genuinely unused preregistered set, locked primary endpoint and baseline, frozen power/sample requirement, implementation parity, state-registry / ablation compliance, and required execution/risk governance.

## Evidence grades

- `E0_CONCEPTUAL`: mechanism only.
- `E1_SINGLE_EPISODE`: one day / episode; hypothesis-generating only.
- `E2_REPLICATED_RESEARCH`: replicated in consumed historical windows; not formal OOS.
- `E3_PREREG_UNUSED`: genuinely unused preregistered holdout / prospective shadow evidence.
- `E4_PROSPECTIVE_REPLICATION`: repeated prospective evidence across materially different regimes.

Post-hoc rule repair resets the revised hypothesis to at most `E1` until independently retested.

A state-space change is a rule change. Adding, splitting, merging, reinterpreting or reprioritizing a state / veto after seeing outcomes triggers a version reset under `STATE_ENUM_ABLATION_GOVERNANCE_V1.md`, even when no numeric threshold changes.

## Current architecture candidate

`MODEL-INDEPENDENT HARD RISK GUARD V1 [P0 GOVERNANCE FROZEN; NUMERIC MANDATE REQUIRED]`
→ `DATA VALIDITY / PIT`
→ `A-SHARE EXECUTION ELIGIBILITY / FEASIBILITY`
→ `ATOMIC EVIDENCE LEDGER V1 [IMPLEMENTED RESEARCH CONTRACT]`
→ `CANONICAL MARKET-STATE CLASSIFIER V1 [IMPLEMENTED CATEGORICAL CONTRACT]`
→ `EVENT / SHOCK SOURCE + PERSISTENCE / LOCAL TRANSMISSION EVIDENCE`
→ `MARKET REGIME / INTERNAL FRAGILITY`
→ `HEDGE / CAPITAL ROTATION [UNIMPLEMENTED_DATA_LAYER]`
→ `REGIME ROUTER / VETO`
→ `THEME + DISPERSION`
→ `RELATIVE STRENGTH / CATALYST`
→ `TACTICAL TIMING`
→ `SOFT EVIDENCE SCORE / PAYOFF`
→ `POSITION TARGET SUBJECT TO HARD RISK CEILINGS`
→ `EXECUTION`

Hard gates / vetoes and soft evidence / ranking are now explicitly separate. A hard gate can block or cap an action but does not add positive score. A new multiplicative interaction among noisy soft layers is treated as a new hypothesis and requires versioning plus ablation.

The implemented ledger/classifier begins from **already-categorical atomic evidence**. Raw numeric market observations are not yet converted into those categories by a frozen extractor. Therefore the branch does not claim an end-to-end live raw-data classifier.

`HEDGE / CAPITAL ROTATION` cannot be cited as a live evidence layer until its required data are actually wired and timestamp-audited. Use `EVIDENCE SCORE`, not probability language, unless a future module is explicitly calibrated.

## Frozen stock-core boundary

The currently frozen / candidate Core10 ranking implementation uses only these ranking factors:

- `return_5d`
- `return_20d`
- `return_30d`
- `realized_vol_20d`

with the stable equal-weight negative rank formula under `RWV-STABLE4-CORE10-CAND-V1`.

Profit quality, revenue growth, earnings growth, valuation, catalyst, sector / theme, RS and funding / chip concepts are not silently treated as validated Core10 inputs unless a separately versioned module explicitly binds them. They remain auxiliary / research candidates unless otherwise governed.

## BASELINE_0 / BASELINE_1

### BASELINE_0

`NO_REGIME_OVERLAY`, represented for evaluation bookkeeping only as constant neutral `RISK_EVIDENCE_SCORE = 1`.

### BASELINE_1

`MOMENTUM_VOL_REGIME_V1` executable:

`research/market_regime_fragility_v0/simple_baseline_v1.py`

Locked semantics:

- CSI1000 completed daily closes only;
- `MOM20 = close_t / close_{t-20} - 1`;
- `RV20 = sample_stdev(latest 20 simple daily returns) * sqrt(252)`;
- `RV20_MED252 = median(latest 252 completed RV20 observations, inclusive t)`;
- minimum 272 completed closes;
- invalid / insufficient input => `SIMPLE_UNAVAILABLE`, never imputed.

PIT-safe batch runner:

`research/market_regime_fragility_v0/baseline_series_v1.py`

It emits per-session baseline states, deterministic input SHA256 provenance, strict session ordering, and is tested so appending future observations cannot change prior outputs.

### Baseline-independence limitation

`BASELINE_1` is intentionally simple, but it is not an independent information source relative to the frozen stock core: both use price / return / volatility information. Therefore beating `BASELINE_1` would demonstrate incremental decision value over a simple price-based regime rule, not proof of independent non-price information.

Source-group overlap must be declared and tested through module / source-family ablation.

## RISK_EVIDENCE_SCORE normalization

Evaluation-only ordinal scale:

- `0 = risk acceptance / risk-on evidence`
- `1 = normal / caution evidence`
- `2 = restricted-risk evidence`
- `3 = severe-risk / active-de-risking evidence`

Canonical mapping is frozen in `RISK_EVIDENCE_SCORE_MAPPING_V1.md`. Unresolved state => `UNAVAILABLE / null`, never NORMAL.

This score is not a calibrated probability.

## Primary inference locked

Version:

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
- block length = 3 sessions;
- default replications = 5000;
- deterministic seed = 20261016;
- two-sided 95% CI for `delta_tau`;
- one-sided primary alpha = 0.05.

The 3-session overlapping-return dependence is therefore not treated as IID in inference. Power / effective sample planning must likewise use block / event-effective units rather than raw daily row count.

This is an inference contract, not evidence that the complex model works.

## 3D risk horizon versus 5D trade horizon

The 3D risk endpoint and the 5D tactical / trade evaluation horizon are separate objectives and must not be silently conflated.

Before economic promotion, the project must preregister an action map specifying what a 3D risk score changes in a 5D holding process, for example exposure scaling, entry veto, or re-entry eligibility. The resulting decision must then be evaluated on drawdown, false-alarm opportunity cost, turnover and executable 5D trade outcomes.

A higher `tau-b` by itself is not sufficient evidence of a better portfolio decision.

## Power / sample-size status

`POWER_SAMPLE_PLAN_V1.md` locks the planning method:

- primary estimand = `delta_tau`;
- alpha = 0.05;
- target planning power = 0.80;
- sample size must use the exact paired comparison procedure and effective dependence-aware sampling units;
- rare-event modules use independent event episodes rather than days;
- unused outcomes cannot be used to choose the minimum effect or required sample.

`MINIMUM_EFFECT_JUSTIFICATION_STATUS_V1.md` records the current objective blocker:

- `minimum_effect_delta_tau = NOT_FROZEN`
- `minimum_sample_required = NOT_FROZEN`

The intended next derivation is ex ante and cost-side first: the minimum meaningful effect must be at least large enough to support an economically useful action after turnover / execution / false-alarm cost, and it must also exceed a defensible noise floor derived without using the complex model's observed performance. Baseline-only uncertainty may inform the noise floor; the exact rule remains to be separately frozen before use.

Because no frozen numeric downstream action / exposure mapping exists yet, the project cannot objectively translate `delta_tau` into tail-risk benefit net of false-alarm cost. Deriving an effect threshold from consumed complex-model windows or synthetic unit-test fixtures is prohibited.

Therefore formal promotion testing remains blocked.

## Atomic Evidence Ledger V1

Executable:

`research/market_regime_fragility_v0/atomic_evidence_ledger_v1.py`

Version:

`ATOMIC_EVIDENCE_LEDGER_V1`

The ledger validates already-categorical evidence for:

- external shock;
- source persistence;
- local transmission;
- breadth;
- leadership;
- small/mid-cap condition;
- turnover state;
- repair state.

Each item must carry a valid enum, timezone-aware `observed_at`, non-empty provenance and `pit_valid=True`. Any post-cutoff observation, invalid enum, missing provenance, false PIT flag, malformed/naive timestamp, or missing required field fails closed. A deterministic SHA256 evidence hash includes the ledger version, classifier version, UTC-normalized cutoff and normalized evidence/provenance.

This layer does not derive categorical evidence from raw numeric market values.

## Canonical Market-State Classifier V1

Executable:

`research/market_regime_fragility_v0/canonical_state_classifier_v1.py`

Version:

`CANONICAL_STATE_CLASSIFIER_V1`

It consumes only a validated Atomic Evidence Ledger and applies the preregistered finite categorical precedence:

1. `ACTIVE_DE_RISKING`
2. `EXTERNAL_SHOCK`
3. `INTERNAL_FRAGILITY_CONFIRMED_HIGH_SEVERITY`
4. `INTERNAL_FRAGILITY_CONFIRMED_LOW_SEVERITY`
5. `REPAIR`
6. `INTERNAL_FRAGILITY_WATCH`
7. `NORMAL_RISK_ON`
8. `NORMAL`
9. `UNAVAILABLE`

Key contract behavior:

- explicit unavailable required evidence cannot become NORMAL;
- breadth divergence alone is at most WATCH;
- multi-channel categorical deterioration is required for confirmed fragility;
- distribution plus broad deterioration has precedence as `ACTIVE_DE_RISKING`;
- verified ongoing/escalating external shock with unresolved transmission resolves to `EXTERNAL_SHOCK` unless a higher-priority active-de-risking state applies;
- broad repair may resolve to `REPAIR` without mutating source-persistence evidence;
- contradictory required combinations fail closed;
- score mapping is imported from existing `state_resolution_v1.py`, not duplicated;
- `production_authorized` is always false.

These are implementation semantics, not evidence that the classifier predicts future returns.

All future state additions / splits / merges / precedence changes are subject to `STATE_ENUM_ABLATION_GOVERNANCE_V1.md` and cannot silently expand the model during E3 evaluation.

## Rare-event module policy

Shock, source-persistence, local-transmission and active-de-risking states are treated as rare-event risk controls by default, not high-frequency predictors.

Binding interpretation:

- sampling unit = independent `EVENT_EPISODE`, not trading days;
- adjacent sessions inside one shock do not count as independent events;
- quiet prospective shadow time with no event adds uptime evidence but not shock-outcome sample size;
- event labels must be created from contemporaneous timestamped evidence available at the decision cutoff;
- retrospective event relabeling cannot support E3;
- by default these modules may tighten or preserve risk but may not increase leverage / exposure above the non-event policy.

## Formal evaluation preflight

Executable fail-closed gate:

`research/market_regime_fragility_v0/formal_eval_preflight_v1.py`

It now requires:

- exact baseline / score-mapping / inference / power-plan versions;
- exact `ATOMIC_EVIDENCE_LEDGER_V1` version;
- horizon and alpha;
- frozen target power, positive numeric minimum effect and numeric minimum sample;
- classifier version / implementation hash;
- `classifier_ledger_pit_valid=True`;
- non-empty classifier evidence hash;
- completed-session cutoff policy;
- genuinely unused set ID/hash;
- definitions locked before set opening;
- no collision with consumed-set IDs.

It can authorize evaluation only and always returns `production_authorized = false`.

Because the actual project minimum effect and sample remain unfrozen, no real formal promotion manifest is currently eligible. Numeric values used in unit-test fixture manifests are test fixtures only and are not project thresholds.

## Categorical state-resolution / veto layer

Executable:

`research/market_regime_fragility_v0/state_resolution_v1.py`

This remains downstream of the canonical classifier and applies the preregistered conflict/veto semantics:

- `ACTIVE_DE_RISKING` blocks new high-beta attack exposure but never implies `force_liquidate_all`;
- `PENDING_TRANSMISSION + SOURCE_ONGOING/SOURCE_ESCALATING` blocks new high-beta attack before local repricing;
- `PENDING_TRANSMISSION + SOURCE_RESOLVING` does not activate that specific veto;
- `OVERHEATED` lifecycle activates a chase veto without rewriting a confirmed theme;
- Theme CONFIRMED and EXTERNAL_SHOCK may coexist;
- invalid data => score null / no full-architecture approval;
- unknown canonical state => fail closed, never coerced to NORMAL.

## A-share execution / hard-risk governance

`A_SHARE_EXECUTION_CONTRACT_V0.md` remains preregistered but not a complete execution engine. It already requires explicit treatment of T+1, suspension, price-limit accessibility, liquidity/capacity, fees, slippage and financing assumptions.

`PORTFOLIO_HARD_RISK_GUARD_V1.md` is now the P0 portfolio gate. Its governance order and mandatory limit families are frozen, but numeric limits remain blocked pending one explicit portfolio-risk mandate. No arbitrary single-name, theme, beta, gross/net, correlation, liquidity, gap-loss or drawdown number has been inserted.

A logical exit does not imply an executable fill. T+1, suspension, limit-down and liquidity failure must be handled through ex-ante sizing plus explicit unresolved-risk states rather than assuming post-signal liquidation is always possible.

## Funding / chip semantics

Vendor capital-flow fields are treated as vendor-defined capital net-flow / distribution data. They are not direct proof of institutional identity.

Price-volume interpretations such as `price down + volume up = distribution` or `price down + volume down = liquidity withdrawal` are research hypotheses / descriptive possibilities, not frozen one-to-one mappings. Panic liquidation, forced selling and other mechanisms remain plausible alternatives and require separate evidence.

## Design principles versus E2 observations

### Design principles / governance rules

The following are architecture rules, not formal empirical findings:

- theme conviction and entry timing are separate decisions;
- shock detection is not an automatic all-position sell command;
- hard gates and soft scores are separate;
- missing / unavailable evidence is not NORMAL;
- a favorable model state cannot override hard portfolio limits;
- model complexity must justify itself through ablation.

### E2 research observations from consumed windows

The following may support research design but are not formal OOS:

- breadth weakness alone produced at least one clear false-positive control, so breadth divergence alone is insufficient for confirmed fragility;
- some consumed windows with leadership deterioration plus small/mid-cap stress showed materially worse forward downside than breadth-only controls;
- at least one consumed shock window showed that selling mechanically at the shock open would have been inferior to observing subsequent absorption / repair;
- consumed severe-shock windows showed different post-close persistence paths, supporting separation of realized severity, local transmission and source persistence.

Exact dates / outcomes remain consumed research evidence and cannot be reused as E3.

## State enumeration / ablation governance

`STATE_ENUM_ABLATION_GOVERNANCE_V1.md` is binding immediately.

Before any decision-active state family may reach `CANDIDATE`, it must have:

- a complete state registry;
- source-group declarations;
- a full-model versus module-removed ablation;
- where possible a state-collapse ablation;
- primary metric / uncertainty;
- false-alarm and tail-risk attribution;
- action / turnover burden;
- event-episode counting for rare-event families.

If removal or collapse does not materially worsen the preregistered decision objective, the extra state / module does not earn promotion.

## Verification

Workflow:

`.github/workflows/market-regime-baseline-v1.yml`

Earlier verified TDD evidence:

- RED `38832719000`: missing inference / batch-series / preflight implementations.
- GREEN `38832999991`: inference + batch baseline + preflight suite successful, 23/23 tests PASS.
- RED `38833183632`: state-resolution tests failed before `state_resolution_v1.py` existed.
- GREEN `38833220950`: full suite successful after implementation, 30/30 tests PASS.

Atomic ledger / classifier TDD evidence:

- RED `38848386749`: atomic-ledger tests were wired before `atomic_evidence_ledger_v1.py` existed; expected failure.
- GREEN `38848433691`: atomic ledger implementation passed the research suite.
- RED `38848486788`: canonical-classifier tests were committed before `canonical_state_classifier_v1.py` existed; expected failure.
- GREEN `38848598260`: canonical classifier implementation passed the research suite.
- RED `38848654992`: new formal-preflight provenance requirements failed against the previous preflight implementation as expected.
- GREEN `38848703828`: ledger + classifier + preflight provenance + existing research contracts all passed; workflow log reports `Ran 55 tests` and `OK`.

These runs verify executable contracts only. They are not predictive validation, formal OOS evidence, or production authorization.

The later hard-risk / state-ablation changes in this status are governance/document changes; they do not constitute predictive-validation evidence and do not modify the 55-test implementation claim.

## Current blockers — priority order

1. `PORTFOLIO_HARD_RISK_GUARD_V1` numeric mandate is not frozen. This is now the first production-risk blocker.
2. Risk-score -> action / exposure mapping is not frozen.
3. `minimum_effect_delta_tau` is therefore objectively unjustified and remains unfrozen.
4. `minimum_sample_required` therefore remains unfrozen.
5. Raw numeric PIT observations -> Atomic Evidence Ledger categorical extraction is not yet frozen or executable; V1 begins from already-categorical evidence.
6. Live source wiring / timestamp-audited ingestion for the new ledger is not implemented.
7. A-share execution numeric assumptions remain unfrozen.
8. State-family registry / ablation evidence does not yet exist for every lifecycle / timing / shock family.
9. `HEDGE / CAPITAL ROTATION` remains `UNIMPLEMENTED_DATA_LAYER`.

## Next admissible work

1. Do not open a new unused formal evaluation set.
2. Keep state-space frozen unless a new version is explicitly registered; no silent enum expansion.
3. Prepare one consolidated portfolio-risk mandate request for the numeric hard limits instead of asking piecemeal questions.
4. Freeze the risk-score -> action / exposure map before economically justifying `minimum_effect_delta_tau`.
5. Derive minimum effect from ex-ante action economics / costs plus a defensible baseline-only noise floor; do not use observed complex-model delta to set the requirement.
6. Derive minimum sample using dependence-aware effective units; for rare-event modules count independent event episodes.
7. Design raw numeric PIT -> atomic category extraction separately, with source contracts and no outcome-derived threshold fitting.
8. Confirm whether any genuinely unseen historical window still exists; if none exists, E3 is prospective-only.
9. Keep Core10/Core13, XH V0 and MA5 production status unchanged.
