# OOS Admission V4.82 Design

## Purpose

Add an independent, fail-closed OOS admission subsystem between the completed Formal V4.82 evidence chain and any out-of-sample metric computation. The subsystem answers only one question: **is this frozen model/evidence package allowed to expose OOS metrics?**

It must not compute return, alpha, Sharpe, drawdown, hit rate, turnover, or any other OOS performance statistic.

## Existing boundary

The current Formal finalizer intentionally terminates with:

- `formal_ready = true` when the Formal evidence chain is closed;
- `market_data_ready = true` when Full RAW and frozen liquidity prerequisites are closed;
- `oos_metrics_allowed = false` unconditionally.

That behavior remains unchanged. OOS admission is a separate downstream authority.

## Architectural decision

Implement a standalone gate rather than extending `formal_readiness_finalize_v482.py` or embedding admission inside the future OOS backtest runner.

Data flow:

```text
PIT/ST -> QFQ/event repair -> Full RAW -> Liquidity -> Formal Final V4.82
                                                        |
                                                        v
                                      FORMAL_READINESS_FINAL_V482.json
                                                        |
                                                        v
                                             OOS Admission V4.82
                                                        |
                           +----------------------------+----------------------------+
                           |                                                         |
                           v                                                         v
                  OOS_BLOCKED_V482                                         OOS_ADMITTED_V482
                  metrics forbidden                                        metrics may run
```

This separation preserves auditability: Formal proves the historical construction is closed; OOS Admission proves the model and scope were frozen before metrics are exposed.

## Components

### 1. `scripts/oos_admission_v482.py`

Single-purpose gate evaluator. It consumes exactly three JSON artifacts:

1. `FORMAL_READINESS_FINAL_V482.json`
2. `MODEL_FREEZE_V482.json`
3. `OOS_SCOPE_V482.json`

It validates their internal invariants, recomputes canonical hashes, verifies cross-artifact bindings, and emits `OOS_ADMISSION_V482.json`.

It never loads OOS prices or computes OOS performance.

### 2. `data/model_freeze_v482.json`

A declarative freeze manifest describing the exact model allowed to enter OOS. Its allowed top-level fields are exactly:

- `artifact = MODEL_FREEZE_V482`
- `version = V4.82`
- `strategy_id`
- `strategy_code_sha256`
- `parameter_sha256`
- `universe_sha256`
- `factor_definition_sha256`
- `calendar_sha256`
- `formal_artifact_sha256`
- `liquidity_threshold_cny = 80000000`
- `formal_end = 2026-04-17`
- `frozen = true`

Unknown top-level fields are rejected. All SHA fields are lowercase 64-character hexadecimal strings.

The manifest binds the strategy implementation, parameters, universe, factor definitions, trading calendar, and exact canonical Formal JSON content. A change to any bound object requires a new model-freeze manifest and therefore a new admission decision.

### 3. `data/oos_scope_v482.json`

A declarative OOS scope manifest. Its allowed top-level fields are exactly:

- `artifact = OOS_SCOPE_V482`
- `version = V4.82`
- `formal_end = 2026-04-17`
- `oos_start`
- `oos_end`
- `calendar_sha256`
- `universe_sha256`
- `model_freeze_sha256`
- `scope_frozen = true`

Unknown top-level fields are rejected.

Rules:

- `oos_start` and `oos_end` are valid ISO `YYYY-MM-DD` dates.
- `oos_start > 2026-04-17`.
- `oos_end >= oos_start`.
- the scope must bind the same calendar and universe hashes as the model freeze;
- the scope must bind the canonical SHA256 of `MODEL_FREEZE_V482.json`.

The gate does not infer or extend OOS dates at runtime.

### 4. `scripts/test_oos_admission_v482.py`

Unit tests for the gate contract and failure modes. Tests are written before implementation and must demonstrate RED before production code is added.

### 5. `.github/workflows/oos-admission-v482.yml`

Manual/reusable workflow that obtains the three required artifacts, runs the gate, and uploads only the admission artifact and logs. The workflow must not invoke an OOS metric/backtest script.

## Admission checks

Admission is allowed only if all five layers pass.

### Layer A: Formal evidence lock

The Formal artifact must satisfy all of the following:

- `artifact == FORMAL_READINESS_FINAL_V482`
- `version == V4.82`
- `formal_ready is true`
- `validated_global_provenance_emitted is true`
- `oos_metrics_allowed is false`
- checkpoint exactly equals `{PASS: 844, EXACT_TERM_REVIEW: 0, MISSING_EVENT_REVIEW: 0, NOT_APPLICABLE: 3}`
- `universe_n == 847`
- `formal_symbol_n == 844`
- `full_path_pass_n == 844`
- `full_path_fail_n == 0`
- `max_full_path_diff_bp <= 5.0`
- `market_data.market_data_ready is true`
- `market_data.raw_trade_rows == 1011607`
- `market_data.missing_trade_dates_n == 0`
- `market_data.extra_trade_dates_n == 0`
- `market_data.duplicate_symbol_dates == 0`
- `market_data.zero_trade_symbols == [600074.SH, 600485.SH, 600677.SH]`
- `market_data.liquidity_threshold_cny == 80000000`
- `market_data.raw_pitst_status == PASS_EXACT_RAW_PITST`
- `market_data.current_trade_violation_n == 0`
- `market_data.st_overlay_violation_n == 0`
- `special_provenance.materialized_n == 11`
- `special_provenance.blocker_n == 0`

The canonical SHA256 of the complete Formal JSON must equal `model_freeze.formal_artifact_sha256`.

### Layer B: Model freeze lock

The model manifest must satisfy its artifact/version/schema constants, contain no unknown fields, have `frozen is true`, have valid SHA fields, use `formal_end == 2026-04-17`, and set the liquidity threshold to exactly CNY 80,000,000.

The gate computes a canonical SHA256 for the complete model-freeze manifest. That value becomes `model_freeze_sha256` in the admission artifact and must equal `oos_scope.model_freeze_sha256`.

### Layer C: OOS time-window lock

The OOS scope must be frozen before admission, contain no unknown fields, use the same `formal_end`, and be strictly non-overlapping:

```text
oos_start > 2026-04-17
oos_end >= oos_start
```

No default date, rolling extension, or implicit `today` value is permitted.

### Layer D: Cross-artifact isolation lock

The following hashes must agree exactly between model freeze and OOS scope:

- `calendar_sha256`
- `universe_sha256`

The OOS scope must also bind the exact canonical model-freeze hash.

The Formal artifact presented to the gate must still report `oos_metrics_allowed = false`. If any upstream artifact has already marked OOS metrics as exposed/allowed, admission fails because the pre-exposure guarantee is no longer provable.

### Layer E: No-metrics-before-admission lock

The admission process accepts no price panel, return series, signal result, PnL, or performance summary as input. Its schemas contain no performance fields.

As defense in depth, the implementation recursively scans keys in the model-freeze and OOS-scope documents before schema validation. Key matching is case-insensitive. Any key equal to a reserved metric name is rejected regardless of nesting depth:

- `return`
- `returns`
- `pnl`
- `alpha`
- `sharpe`
- `drawdown`
- `hit_rate`
- `win_rate`
- `performance`
- `metrics`

Strict allowed-field validation plus recursive reserved-key rejection prevents hidden OOS observations from being smuggled into the admission decision.

## State machine

There are exactly two terminal states.

### `OOS_ADMITTED_V482`

Emitted only when every check passes.

Required output properties:

```json
{
  "artifact": "OOS_ADMISSION_V482",
  "version": "V4.82",
  "status": "OOS_ADMITTED_V482",
  "formal_ready": true,
  "model_frozen": true,
  "oos_window_frozen": true,
  "data_isolation_pass": true,
  "formal_artifact_sha256": "<sha256>",
  "model_freeze_sha256": "<sha256>",
  "oos_scope_sha256": "<sha256>",
  "blockers": [],
  "oos_metrics_allowed": true
}
```

### `OOS_BLOCKED_V482`

Any expected validation failure produces a blocked decision. The evaluator must not downgrade failures into warnings.

Blocked output contains:

- `artifact = OOS_ADMISSION_V482`
- `version = V4.82`
- `status = OOS_BLOCKED_V482`
- available hash fields if they were safely computable
- one or more deterministic blocker codes
- `oos_metrics_allowed = false`

Expected blocker codes include:

- `FORMAL_ARTIFACT_INVALID`
- `FORMAL_NOT_READY`
- `FORMAL_HASH_MISMATCH`
- `MODEL_FREEZE_INVALID`
- `MODEL_NOT_FROZEN`
- `MODEL_FREEZE_HASH_MISMATCH`
- `OOS_SCOPE_INVALID`
- `OOS_WINDOW_OVERLAP`
- `OOS_WINDOW_NOT_FROZEN`
- `CALENDAR_HASH_MISMATCH`
- `UNIVERSE_HASH_MISMATCH`
- `UPSTREAM_OOS_ALREADY_OPEN`
- `FORBIDDEN_OOS_METRIC_FIELD`

Malformed/unreadable input or any unexpected internal exception fails the workflow and must never generate an admitted artifact.

## Canonical hashing

For cross-artifact binding, canonical JSON bytes are produced with:

- UTF-8 encoding;
- object keys sorted recursively by the JSON serializer;
- separators `(',', ':')`;
- `ensure_ascii = false`;
- no trailing newline included in the hashed payload.

SHA256 is computed over those canonical bytes. In V4.82, `*_sha256` bindings in this subsystem are semantic canonical-JSON hashes, not hashes of indentation/whitespace bytes.

This binds JSON content while avoiding dependence on file formatting or key order.

## Compatibility rule

`formal_readiness_v482.py` and `formal_readiness_finalize_v482.py` retain `oos_metrics_allowed = false`. They are not modified to open OOS.

A future OOS runner must consume `OOS_ADMISSION_V482.json` and independently require:

- `status == OOS_ADMITTED_V482`
- `oos_metrics_allowed is true`
- the expected `model_freeze_sha256`
- the expected `oos_scope_sha256`

That future runner is outside this subsystem's implementation scope.

## Testing strategy

Tests must cover both positive admission and fail-closed behavior.

Minimum cases:

1. valid Formal + valid frozen model + valid non-overlapping scope -> admitted;
2. Formal says `oos_metrics_allowed = true` -> blocked;
3. Formal checkpoint changes -> blocked;
4. Formal max diff exceeds 5bp -> blocked;
5. Formal market-data violation count becomes non-zero -> blocked;
6. Formal zero-trade partition changes -> blocked;
7. Formal artifact hash differs from model binding -> blocked;
8. invalid/missing SHA in model freeze -> blocked;
9. unknown field in model freeze -> blocked;
10. `frozen = false` -> blocked;
11. scope starts on or before 2026-04-17 -> blocked;
12. scope end before start -> blocked;
13. unknown field in OOS scope -> blocked;
14. scope/model calendar hashes differ -> blocked;
15. scope/model universe hashes differ -> blocked;
16. scope binds a different model-freeze SHA -> blocked;
17. forbidden metric key appears at top level or nested in model/scope -> blocked;
18. canonical hashing is stable across JSON key order/whitespace differences.

Workflow verification must also prove the admission job does not invoke any OOS metric/backtest command.

## Success criteria

The subsystem is complete when:

- all unit tests pass;
- the workflow can emit `OOS_BLOCKED_V482` and `OOS_ADMITTED_V482` deterministically from fixture artifacts;
- existing Formal tests remain green;
- existing Formal finalizer behavior remains unchanged with `oos_metrics_allowed = false`;
- no OOS performance metric is computed or consumed before an admitted artifact exists;
- every admitted artifact cryptographically binds the canonical Formal artifact, model freeze, and OOS scope used for the decision.
