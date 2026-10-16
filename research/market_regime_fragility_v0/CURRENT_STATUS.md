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
2. `SIMPLE_BASELINE_PREREG_V1.md`
3. `SIMPLE_BASELINE_EXECUTION_CONTRACT_V1.md`
4. `RISK_EVIDENCE_SCORE_MAPPING_V1.md`
5. `PRIMARY_INFERENCE_PREREG_V1.md`
6. `POWER_SAMPLE_PLAN_V1.md`
7. `MINIMUM_EFFECT_JUSTIFICATION_STATUS_V1.md`
8. `LAYER_CONFLICT_VETO_CONTRACT_V0.md`
9. `A_SHARE_EXECUTION_CONTRACT_V0.md`
10. `PORTFOLIO_HARD_RISK_GUARD_V0.md`
11. `docs/superpowers/specs/2026-10-16-atomic-evidence-ledger-canonical-classifier-design.md`
12. `docs/superpowers/plans/2026-10-16-atomic-evidence-ledger-canonical-classifier.md`

No module may advance to `CANDIDATE` without a genuinely unused preregistered set, locked primary endpoint and baseline, frozen power/sample requirement, implementation parity, and required execution/risk governance.

## Evidence grades

- `E0_CONCEPTUAL`: mechanism only.
- `E1_SINGLE_EPISODE`: one day / episode; hypothesis-generating only.
- `E2_REPLICATED_RESEARCH`: replicated in consumed historical windows; not formal OOS.
- `E3_PREREG_UNUSED`: genuinely unused preregistered holdout / prospective shadow evidence.
- `E4_PROSPECTIVE_REPLICATION`: repeated prospective evidence across materially different regimes.

Post-hoc rule repair resets the revised hypothesis to at most `E1` until independently retested.

## Current architecture candidate

`MODEL-INDEPENDENT HARD RISK GUARD [UNIMPLEMENTED_POLICY_LAYER]`
→ `DATA VALIDITY / PIT`
→ `ATOMIC EVIDENCE LEDGER V1 [IMPLEMENTED RESEARCH CONTRACT]`
→ `CANONICAL MARKET-STATE CLASSIFIER V1 [IMPLEMENTED CATEGORICAL CONTRACT]`
→ `EVENT / SHOCK SOURCE + PERSISTENCE / LOCAL TRANSMISSION EVIDENCE`
→ `MARKET REGIME / INTERNAL FRAGILITY`
→ `HEDGE / CAPITAL ROTATION [UNIMPLEMENTED_DATA_LAYER]`
→ `REGIME ROUTER / VETO`
→ `THEME + DISPERSION`
→ `RELATIVE STRENGTH / CATALYST`
→ `TACTICAL TIMING`
→ `EVIDENCE SCORE / PAYOFF`
→ `POSITION BUDGET`
→ `A-SHARE EXECUTION FEASIBILITY [PREREGISTERED, NOT FULLY IMPLEMENTED]`

The implemented ledger/classifier begins from **already-categorical atomic evidence**. Raw numeric market observations are not yet converted into those categories by a frozen extractor. Therefore the branch does not claim an end-to-end live raw-data classifier.

`HEDGE / CAPITAL ROTATION` cannot be cited as a live evidence layer until its required data are actually wired and timestamp-audited. Use `EVIDENCE SCORE`, not probability language, unless a future module is explicitly calibrated.

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

## RISK_EVIDENCE_SCORE normalization

Evaluation-only ordinal scale:

- `0 = risk acceptance / risk-on evidence`
- `1 = normal / caution evidence`
- `2 = restricted-risk evidence`
- `3 = severe-risk / active-de-risking evidence`

Canonical mapping is frozen in `RISK_EVIDENCE_SCORE_MAPPING_V1.md`. Unresolved state => `UNAVAILABLE / null`, never NORMAL.

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

This is an inference contract, not evidence that the complex model works.

## Power / sample-size status

`POWER_SAMPLE_PLAN_V1.md` locks the planning method:

- primary estimand = `delta_tau`;
- alpha = 0.05;
- target planning power = 0.80;
- sample size must use the exact paired comparison procedure and development-only / synthetic assumptions;
- unused outcomes cannot be used to choose the minimum effect or required sample.

`MINIMUM_EFFECT_JUSTIFICATION_STATUS_V1.md` records the current objective blocker:

- `minimum_effect_delta_tau = NOT_FROZEN`
- `minimum_sample_required = NOT_FROZEN`

Reason: there is no frozen numeric downstream action / exposure mapping that can yet translate a change in rank concordance into an economically meaningful tail-risk benefit net of false-alarm cost. Deriving an effect threshold from consumed historical windows or synthetic unit-test fixtures is prohibited.

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

`A_SHARE_EXECUTION_CONTRACT_V0.md` remains preregistered but not a complete execution engine. T+1, suspension, price-limit accessibility, liquidity/capacity, fees, slippage and financing assumptions must be frozen identically across models before any production PnL claim.

`PORTFOLIO_HARD_RISK_GUARD_V0.md` remains an `UNIMPLEMENTED_POLICY_LAYER`; no numeric single-name, theme, beta, gross/net, correlation, liquidity or drawdown limit has been invented.

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

## Current blockers

1. `minimum_effect_delta_tau` is objectively unjustified and remains unfrozen.
2. `minimum_sample_required` therefore remains unfrozen.
3. Raw numeric PIT observations -> Atomic Evidence Ledger categorical extraction is not yet frozen or executable; V1 begins from already-categorical evidence.
4. Live source wiring / timestamp-audited ingestion for the new ledger is not implemented.
5. A-share execution numeric assumptions remain unfrozen.
6. Portfolio hard-risk numeric limits remain unfrozen.
7. `HEDGE / CAPITAL ROTATION` remains `UNIMPLEMENTED_DATA_LAYER`.

## Next admissible work

1. Do not open a new unused formal evaluation set.
2. Do not infer raw-to-atomic numeric thresholds from consumed outcome windows.
3. Attempt `minimum_effect_delta_tau` justification only from an ex-ante decision-utility / exposure mapping or a defensible independent external benchmark; otherwise retain the blocker.
4. Design raw numeric PIT -> atomic category extraction separately, with source contracts and no outcome-derived threshold fitting.
5. If and only if a defensible minimum effect is frozen, version and run the Monte Carlo power simulator to derive `minimum_sample_required`.
6. Only after both the power gate and an end-to-end PIT evidence path are closed may a new unused / prospective formal comparison window be opened.
7. Keep Core10/Core13, XH V0 and MA5 production status unchanged.
