# GP12 Formal Input Readiness V1 Design

Status: design for a Formal-only production-evidence binding layer for `GP12_REBUILD_CANDIDATE_V1`. This subsystem does not approve the candidate, does not recover historical GP V1.1, does not freeze a model, and does not consume OOS rows or OOS outcomes.

## 1. Purpose

PR #9 provides a deterministic, explicitly unapproved GP12 reconstruction candidate with exact proposed formulas and a fail-closed source router. The remaining engineering problem is not formula definition; it is proving which required feature families can be built from existing V4.82 production evidence with correct provenance and point-in-time availability.

Create `GP12_FORMAL_INPUT_READINESS_V1` as a separate evidence layer between the existing V4.82 Formal artifacts and the candidate scorer. It must answer, per feature family:

1. Is a concrete source artifact bound?
2. Is its schema/coverage sufficient?
3. Is the data point-in-time valid for the candidate snapshot semantics?
4. Can the family be used by a Formal-only scoring snapshot?
5. Which exact factors remain blocked because one or more required families are not ready?

The layer is diagnostic and fail-closed. It must never infer missing values, substitute related fields, or promote structural/API availability into production validation.

## 2. Non-goals and safety boundaries

This subsystem MUST NOT:

- modify `scripts/gp12_candidate_v1.py` factor formulas, weights, ranking, probability mapping, or policy;
- modify historical `GP_V11` recovery evidence or clear `STRATEGY_CODE_MISSING`, `PARAMETER_SET_MISSING`, or `FACTOR_DEFINITION_MISSING`;
- create `MODEL_FREEZE_V482.json` or final `OOS_SCOPE_V482.json`;
- approve `GP12_REBUILD_CANDIDATE_V1`;
- read rows after `2026-04-17` for feature validation, calibration, labels, scoring, or diagnostics that influence readiness;
- calculate or report strategy return, PnL, alpha, Sharpe, drawdown, hit rate, win rate, or other OOS/performance metrics;
- treat an HTTP/API PASS as substantive provenance;
- treat RAW close as adjusted close;
- treat amount/volume as turnover ratio or main net flow;
- infer market or sector breadth from the frozen 847-symbol remediation universe without an explicit, PIT-valid breadth definition;
- infer sector membership from a current classification when historical membership is required;
- merge 15-minute and 60-minute data into one generic intraday family;
- forward-fill over suspension or missing trading sessions;
- treat a full-history QFQ series as PIT-safe without proving the adjustment information available at each historical snapshot.

All outputs fix:

- `strategy_id = GP12_REBUILD_CANDIDATE_V1`
- `candidate_adoption_status = UNAPPROVED`
- `formal_end = 2026-04-17`
- `model_freeze_allowed = false`
- `oos_metrics_allowed = false`

## 3. Architectural position

The evidence flow is:

`V4.82 Formal evidence artifacts`
→ **GP12 Formal Input Readiness V1**
→ `GP12_FORMAL_INPUT_READINESS_V1.json`
→ future Formal-only materializer(s)
→ candidate scorer

The existing `gp12_source_router_v1.py` remains a structural routing helper. A source-router `PASS` means only that a family has rows. The readiness layer is stricter and is the only component allowed to say a family is `FORMAL_FEATURE_READY`.

No readiness output is passed to OOS Admission or historical GP V1.1 Model Freeze Recovery.

## 4. Evidence model: binding and PIT readiness are separate

Each feature family record has two independent dimensions.

### 4.1 Artifact binding state

Allowed values:

- `BOUND_VERIFIED_ARTIFACT`: exact source artifact identity, hash/digest, schema/coverage invariants and Formal boundary are verified;
- `BOUND_STRUCTURAL_ONLY`: source or rows are structurally available, but production evidence/provenance is insufficient;
- `UNBOUND`: no acceptable source artifact is bound;
- `NOT_DIRECTLY_REQUIRED`: only for evidence objects that support another gate but are not a scorer family.

### 4.2 Temporal/PIT state

Allowed values:

- `PIT_VERIFIED`: exact historical availability semantics are proven and values are known no later than the candidate snapshot;
- `PIT_PARTIAL`: some timing evidence exists but does not prove all rows or all transformations;
- `PIT_UNVERIFIED`: no sufficient historical known-at proof;
- `PIT_NOT_APPLICABLE`: only for immutable contracts/metadata that are not time-varying feature values.

A family is `FORMAL_FEATURE_READY=true` only when:

- artifact binding is `BOUND_VERIFIED_ARTIFACT`;
- PIT state is `PIT_VERIFIED`;
- required Formal coverage and schema checks pass;
- no family-specific blocker remains.

This separation is mandatory for adjusted prices. Existing QFQ/event exactness proves adjustment/data correctness under its own contract; it does not automatically prove that a reconstructed adjusted-close value at date T uses no information learned after T.

## 5. Candidate feature families

The readiness layer consumes the exact families already required by the candidate scorer/router:

1. `market_calendar`
2. `stock_adjusted_close`
3. `market_adjusted_close`
4. `sector_adjusted_close`
5. `amount_turnover`
6. `main_net_flow`
7. `market_breadth`
8. `sector_breadth`
9. `status`
10. `intraday_15m`
11. `intraday_60m`

Additionally, readiness tracks supporting evidence that is not itself a scorer family:

- `formal_universe`
- `raw_daily_panel`
- `liquidity_contract`
- `historical_label_provenance`
- `sector_membership_pit`

These support later materialization/calibration but MUST NOT be silently mapped into a scorer family.

## 6. Initial V1 evidence bindings

The first production run binds only evidence already audited by the V4.82 chain and reports all other families as missing/unverified.

### 6.1 Formal calendar

Bind the verified V4.80/V4.82 Formal calendar:

- range `2020-06-01..2026-04-17`;
- 1426 Formal market dates;
- recovery semantic SHA256 `5a872a47cf7a338cc48aa628b8de46053fddc3ed161a2617550199d0607efae7`;
- legacy frozen SHA256 `0bfa32175dfccbd24d30eb7ceb0605f6cde2ed0bcc31ac2cac61479ba812add0`.

`market_calendar` may be `FORMAL_FEATURE_READY=true` because the calendar itself is an official/frozen market-date contract and does not require per-row market-data known-at transformation.

### 6.2 Formal universe

Bind the frozen 847-symbol scope with canonical SHA256:

`dfe5c75692d38e5fde7cd5c32eb2ed090a8ab6dffcfd41d5ebda07dc2d6d96fb`.

This is supporting evidence only. The 847-symbol remediation scope MUST NOT automatically define market breadth or sector breadth.

### 6.3 RAW daily panel

Bind the Full RAW V4.82 evidence:

- 847 symbols;
- expected/corrected RAW trade rows `1,011,607`;
- fields `symbol,date,open,high,low,close,volume,amount,source`;
- zero duplicate/missing/extra/bad OHLC/volume/amount/shard violations under the existing Formal finalizer contract.

This proves `raw_daily_panel` support only. It does not make any of `stock_adjusted_close`, `amount_turnover`, `main_net_flow`, breadth, or intraday ready.

### 6.4 PIT-ST / tradability support

Bind the existing PIT-ST exact audit and liquidity replay/apply evidence where their exact hashes/digests are available to the workflow.

`status` readiness requires a documented mapping from upstream fields to all three scorer status fields:

- `is_st`
- `tradable`
- `upper_limit`

PIT-ST alone can prove historical ST state and trading-day presence but does not automatically prove an upper-limit execution constraint. Until all three semantics are bound and PIT-verified, `status` remains not fully ready.

### 6.5 Liquidity contract

Bind the frozen contract:

- 20 market-session median daily amount;
- minimum `80,000,000 CNY`;
- minimum trade density `0.8`;
- at least 120 prior actual traded sessions;
- current day traded.

This is a supporting gate, not a substitute for candidate `turnover_ratio`. The candidate's F11 still requires explicit turnover and main-net-flow inputs.

### 6.6 Adjusted close evidence

Bind the V4.82 QFQ/event provenance artifact identities where available, but initial V1 MUST default:

- `stock_adjusted_close`: `PIT_UNVERIFIED` unless a historical known-at transformation is proven;
- `market_adjusted_close`: `UNBOUND` unless a separately identified benchmark series is bound;
- `sector_adjusted_close`: `UNBOUND` unless a PIT-valid sector series and membership definition are bound.

A Sohu/Sina or Eastmoney adapter response is not sufficient by itself.

### 6.7 Initially missing/unvalidated families

Initial production readiness should normally retain blockers for:

- `stock_adjusted_close` PIT semantics if not proven;
- `market_adjusted_close`;
- `sector_adjusted_close`;
- `amount_turnover` because turnover ratio is not present in RAW;
- `main_net_flow`;
- `market_breadth`;
- `sector_membership_pit`;
- `sector_breadth`;
- `status` if upper-limit semantics are not fully bound;
- `intraday_15m`;
- `intraday_60m`;
- `historical_label_provenance`.

The exact set is determined by production evidence, not hard-coded to make the expected report pass.

## 7. Factor-to-family dependency map

The readiness artifact must derive factor readiness from the candidate factor contract rather than duplicating arbitrary assumptions.

Expected dependency map for the current candidate contract:

- F1 `market_regime`: `market_adjusted_close`
- F2 `market_breadth`: `market_breadth`
- F3 `sector_rs`: `sector_adjusted_close` + `market_adjusted_close`
- F4 `sector_slope_r2`: `sector_adjusted_close`
- F5 `sector_breadth`: `sector_breadth` + supporting `sector_membership_pit`
- F6 `position`: `stock_adjusted_close`
- F7 `multi_momentum`: `stock_adjusted_close`
- F8 `trend_quality`: `stock_adjusted_close`
- F9 `efficiency_ratio`: `stock_adjusted_close`
- F10 `drawdown_recovery`: `stock_adjusted_close`
- F11 `price_fund_efficiency`: `stock_adjusted_close` + `amount_turnover` + `main_net_flow`
- F12 `intraday_confirmation`: `intraday_15m` + `intraday_60m`

A factor is ready only when every required family/supporting PIT contract is ready. The subsystem reports `ready_factor_ids`, `blocked_factor_ids`, and deterministic blocker reasons per factor.

No partial factor score is promoted into a full candidate score. Even if F6-F10 become ready first, `candidate_scoring_ready` remains false until all 12 factors and required status/liquidity execution gates are ready.

## 8. Readiness artifact schema

Output file:

`GP12_FORMAL_INPUT_READINESS_V1.json`

Required top-level fields:

- `artifact = GP12_FORMAL_INPUT_READINESS_V1`
- `version = 1.0`
- `strategy_id = GP12_REBUILD_CANDIDATE_V1`
- `candidate_adoption_status = UNAPPROVED`
- `formal_end = 2026-04-17`
- `formal_artifact_sha256`
- `formal_calendar_sha256`
- `universe_sha256`
- `candidate_parameters_sha256`
- `candidate_factors_sha256`
- `supporting_evidence`
- `feature_families`
- `factor_readiness`
- `validated_families`
- `missing_or_unvalidated_families`
- `ready_factor_ids`
- `blocked_factor_ids`
- `blockers`
- `candidate_scoring_ready`
- `candidate_freeze_ready`
- `real_feature_inputs_validated`
- `model_freeze_allowed`
- `oos_metrics_allowed`

The artifact MUST contain no performance or OOS-result fields.

`model_freeze_allowed` and `oos_metrics_allowed` are always false in V1, regardless of readiness completeness. A later explicit candidate-adoption/freeze subsystem would be required to change that.

## 9. Candidate package identity binding

Readiness must bind to the exact candidate package identities already supported by `gp12_candidate_v1.py`:

- parameter canonical SHA256 `22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204`;
- factor canonical SHA256 `b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e`.

Any mismatch, unknown formula set/version, or altered candidate contract blocks readiness generation rather than silently validating a different strategy.

## 10. Deterministic blockers

At minimum support deterministic blocker codes:

- `CANDIDATE_PACKAGE_IDENTITY_MISMATCH`
- `FORMAL_EVIDENCE_INVALID`
- `FORMAL_BOUNDARY_VIOLATION`
- `CALENDAR_BINDING_INVALID`
- `UNIVERSE_BINDING_INVALID`
- `RAW_PANEL_EVIDENCE_INVALID`
- `QFQ_EVIDENCE_INVALID`
- `ADJUSTED_CLOSE_PIT_UNVERIFIED`
- `MARKET_BENCHMARK_UNBOUND`
- `SECTOR_SERIES_UNBOUND`
- `SECTOR_MEMBERSHIP_PIT_UNBOUND`
- `TURNOVER_RATIO_UNBOUND`
- `MAIN_NET_FLOW_UNBOUND`
- `MARKET_BREADTH_UNBOUND`
- `SECTOR_BREADTH_UNBOUND`
- `STATUS_SEMANTICS_INCOMPLETE`
- `INTRADAY_15M_UNBOUND`
- `INTRADAY_60M_UNBOUND`
- `LABEL_PROVENANCE_UNBOUND`
- `FORBIDDEN_OOS_OR_PERFORMANCE_FIELD`

Blockers are sorted and unique. Missing production evidence is a validation state, not an exception. Programmer/schema corruption is an exception/nonzero workflow failure.

## 11. Production workflow behavior

A new isolated workflow will:

1. check out the new readiness branch;
2. run unit tests plus GP12 candidate/source-router and upstream recovery/admission regressions;
3. download or bind exact previously successful Formal-era artifacts needed for calendar/universe/RAW/PIT-ST/liquidity/QFQ evidence;
4. reject any input artifact whose identity/coverage does not match the frozen Formal contract;
5. generate `GP12_FORMAL_INPUT_READINESS_V1.json`;
6. assert `formal_end == 2026-04-17` and no consumed source row/window exceeds Formal end;
7. assert `candidate_adoption_status == UNAPPROVED`;
8. assert `model_freeze_allowed == false` and `oos_metrics_allowed == false`;
9. upload the readiness artifact and evidence manifest.

The workflow must not download OOS market data or invoke any performance/backtest command.

## 12. TDD requirements

Write RED tests before production implementation. Tests must cover at least:

1. exact candidate parameter/factor identity accepted; tampering blocks;
2. verified Formal calendar/universe bindings accepted;
3. RAW panel binds only support evidence and never substitutes adjusted/turnover/flow/breadth/intraday families;
4. QFQ artifact present but PIT-known-at absent leaves adjusted close blocked;
5. a synthetic PIT-proven adjusted-close binding can mark F6-F10 ready without marking full scoring ready;
6. market benchmark missing blocks F1/F3;
7. sector series/membership missing blocks F3/F4/F5;
8. turnover and flow missing independently block F11;
9. 15m and 60m are independently required for F12;
10. incomplete status semantics blocks candidate execution readiness;
11. liquidity contract remains supporting evidence and does not satisfy turnover ratio;
12. OOS dates, OOS outcome fields, or performance fields are rejected recursively;
13. all blocker lists are deterministic/sorted/unique;
14. even a synthetic all-family-ready fixture still leaves adoption/model-freeze/OOS disabled in this V1 subsystem;
15. existing GP12 candidate, source-router, Strategy Recovery, Model Freeze Recovery and OOS Admission tests remain green.

## 13. Planned files

Create on `gp/gp12-formal-input-readiness-v1` after implementation-plan approval:

- `scripts/gp12_formal_input_readiness_v1.py`
- `scripts/test_gp12_formal_input_readiness_v1.py`
- `.github/workflows/gp12-formal-input-readiness-v1.yml`
- `docs/gp12-formal-input-readiness.md`
- production artifact(s) are generated by CI, not committed as fake complete evidence.

Do not edit the candidate formula/parameter JSON unless a separate adoption/design decision explicitly changes the strategy proposal.

## 14. Completion criterion for this subsystem

This subsystem is complete when a production GitHub Actions run emits a source-backed, Formal-only readiness artifact that truthfully distinguishes:

- evidence already bound and PIT-valid;
- evidence bound but PIT-unverified;
- completely missing feature families;
- exact factor dependencies blocked by those gaps;

while keeping `candidate_scoring_ready` false unless all required families are truly ready, and keeping candidate adoption, Model Freeze, and OOS metrics disabled regardless.
