# Model Freeze Recovery V4.82 Design

## Purpose

Create a separate, fail-closed recovery layer for the real GP model assets required by OOS Admission V4.82. The subsystem must distinguish between assets that are already recoverable from the audited repository/evidence chain and assets that are genuinely missing. It must never synthesize, infer, or substitute strategy-code, parameter, or factor-definition hashes merely to satisfy admission.

This layer sits between the completed Formal/OOS Admission work and any future production OOS admission attempt.

## Architectural Boundary

The existing OOS Admission gate remains unchanged. In particular:

- `scripts/oos_admission_v482.py` is not modified by this subsystem.
- `FORMAL_READINESS_FINAL_V482` remains the authoritative Formal artifact.
- Formal continues to emit `oos_metrics_allowed = false`.
- The recovery layer may inspect and hash already frozen Formal/model-input assets, but it must not read OOS returns, PnL, Sharpe, drawdown, hit-rate, signals, or performance outputs.
- A recovery checkpoint is evidence inventory, not an admission decision.
- Only a complete, genuine model freeze can produce `MODEL_FREEZE_V482.json`.

Recommended branch: `gp/model-freeze-recovery-v482`, based on `gp/oos-admission-v482` so that its manifests match the already frozen OOS Admission schema.

## Known Recoverable Evidence

The current audited repository/evidence chain already establishes the following real assets:

1. **Formal artifact**
   - artifact: `FORMAL_READINESS_FINAL_V482`
   - Formal window: `2020-06-01` through `2026-04-17`
   - universe: 847 symbols
   - Formal-valid symbols: 844
   - exact N/A / zero-trade symbols: `600074.SH`, `600485.SH`, `600677.SH`
   - liquidity threshold: CNY 80,000,000
   - current trade violations: 0
   - ST overlay violations: 0
   - current OOS Admission run already bound a canonical Formal JSON SHA256.

2. **Universe scope**
   - `data/pit_st_scope_v480.txt`
   - 847 symbols
   - source metadata: `data/pit_st_scope_v480.meta.json`
   - metadata explicitly records the Formal window `[2020-06-01, 2026-04-17]` and 847 unique symbols.

3. **Formal trading calendar source**
   - `data/OFFICIAL_A_SHARE_OPEN_DATES_V357.csv.gz.b64`
   - mirrored representation: `data/OFFICIAL_A_SHARE_OPEN_DATES_V357.csv.gz.hex`
   - these are evidence for the already completed Formal chain.

4. **Liquidity rule**
   - exact threshold is CNY 80,000,000.
   - full market-data and liquidity application were already bound into `FORMAL_READINESS_FINAL_V482`.

These are valid recovery inputs. They are not substitutes for the GP scoring model.

## Genuinely Missing Strategy-Side Assets

Repository history, old branches, current File Library recovery attempts, and early GitHub workflow history do not contain a recoverable complete copy of the original GP V1.1 strategy implementation. The recovery layer must therefore treat the following as independent hard blockers until actual bytes are supplied or found:

- `STRATEGY_CODE_MISSING`
  - authoritative GP scorer / execution code is absent.
  - historical names such as `gp_v11_scoring.py` or `run_gp_walkforward.py` are search clues only, not required filenames.

- `PARAMETER_SET_MISSING`
  - authoritative frozen strategy parameters, including the original 12-factor weight set and thresholds, are absent as a complete signed/frozen asset.

- `FACTOR_DEFINITION_MISSING`
  - authoritative complete factor-definition package is absent. Data repair/QFQ/PIT-ST code must not be hashed and mislabeled as the scoring factor definition.

No combination of Formal, QFQ, PIT/ST, RAW, liquidity, Sina, Sohu, Eastmoney, Longbridge, Tushare, or event-repair artifacts can clear these strategy-side blockers.

## Subsystem 1: Recovery Checkpoint

Create a deterministic artifact:

`MODEL_ASSET_RECOVERY_CHECKPOINT_V482.json`

It records exactly what can be proven without fabricating model assets.

### Required top-level schema

```json
{
  "artifact": "MODEL_ASSET_RECOVERY_CHECKPOINT_V482",
  "version": "V4.82",
  "status": "MODEL_ASSETS_INCOMPLETE_V482",
  "formal_artifact_sha256": "<64 hex>",
  "universe_sha256": "<64 hex or null>",
  "formal_calendar_sha256": "<64 hex or null>",
  "liquidity_threshold_cny": 80000000,
  "formal_end": "2026-04-17",
  "recoverable": {
    "formal_artifact": true,
    "universe": true,
    "formal_calendar": true,
    "liquidity_rule": true
  },
  "strategy_assets": {
    "strategy_code_sha256": null,
    "parameter_sha256": null,
    "factor_definition_sha256": null
  },
  "blockers": [
    "STRATEGY_CODE_MISSING",
    "PARAMETER_SET_MISSING",
    "FACTOR_DEFINITION_MISSING"
  ],
  "model_freeze_allowed": false
}
```

### Status rules

There are two terminal checkpoint states:

- `MODEL_ASSETS_INCOMPLETE_V482`
  - at least one blocker exists;
  - `model_freeze_allowed = false`.

- `MODEL_ASSETS_COMPLETE_V482`
  - all required evidence is present and validated;
  - all six model-freeze hash inputs are available and valid;
  - `model_freeze_allowed = true`.

The recovery checkpoint itself never sets `oos_metrics_allowed`.

## Hashing Rules

### Formal artifact

Use the same canonical JSON SHA256 rule as OOS Admission:

- UTF-8 JSON
- `sort_keys=True`
- `separators=(',', ':')`
- `ensure_ascii=False`
- no trailing newline in canonical bytes.

The checkpoint must reproduce the same Formal canonical SHA256 used by OOS Admission for the exact same Formal JSON object.

### Universe

`universe_sha256` is SHA256 of a canonical universe representation, not a Git blob SHA.

Canonical universe representation:

1. read `data/pit_st_scope_v480.txt` as UTF-8;
2. trim surrounding whitespace on each line;
3. reject blank lines;
4. require exactly 847 symbols;
5. require all symbols unique;
6. preserve the frozen source ordering;
7. canonical bytes are the symbols joined by `\n`, with no trailing newline.

The raw repository file may contain a trailing newline; canonicalization deliberately removes that transport difference.

### Formal calendar

`formal_calendar_sha256` must be calculated from the decoded trading-date sequence, not from the `.b64` wrapper text, `.hex` wrapper text, Git object SHA, or compressed gzip bytes.

Canonical Formal calendar representation:

1. decode the embedded gzip payload;
2. parse dates from the decoded CSV;
3. select the exact Formal range `2020-06-01` through `2026-04-17` inclusive;
4. require strictly increasing unique ISO dates;
5. canonical bytes are the ISO dates joined by `\n`, with no trailing newline.

The `.b64` and `.hex` repository representations must decode to the same gzip payload. A mismatch is a blocker.

### Strategy assets

When real strategy assets become available:

- `strategy_code_sha256` is SHA256 of the exact frozen source bytes after no semantic normalization. File concatenation is not allowed unless a manifest explicitly lists multiple files and ordering.
- `parameter_sha256` is SHA256 of canonical JSON for the frozen parameter manifest.
- `factor_definition_sha256` is SHA256 of canonical JSON for the frozen factor-definition manifest, or exact source bytes if the authoritative artifact is a single non-JSON source file.

The recovery implementation must store provenance paths and source hashes so that each digest can be independently reproduced.

## Subsystem 2: Model Freeze Promotion

The recovery layer may emit `MODEL_FREEZE_V482.json` only if the recovery checkpoint is complete.

Required production schema remains compatible with OOS Admission:

```json
{
  "artifact": "MODEL_FREEZE_V482",
  "version": "V4.82",
  "strategy_id": "<non-empty stable id>",
  "strategy_code_sha256": "<64 hex>",
  "parameter_sha256": "<64 hex>",
  "universe_sha256": "<64 hex>",
  "factor_definition_sha256": "<64 hex>",
  "calendar_sha256": "<64 hex>",
  "formal_artifact_sha256": "<64 hex>",
  "liquidity_threshold_cny": 80000000,
  "formal_end": "2026-04-17",
  "frozen": true
}
```

Promotion rules:

- all hashes must be lowercase 64-hex SHA256;
- `formal_artifact_sha256` must equal the current closed Formal canonical hash;
- `universe_sha256` must equal the recovery checkpoint universe hash;
- `calendar_sha256` must be a calendar hash suitable for both model freeze and OOS-scope binding; therefore the Formal-only calendar hash is not automatically promoted into this field unless calendar coverage is proven sufficient for the future OOS scope;
- `liquidity_threshold_cny` must equal 80,000,000;
- no blocker may remain;
- no inferred or placeholder value is permitted.

## Subsystem 3: OOS Scope Intent Freeze

To prevent choosing an advantageous test window after the model is recovered, create a separate pre-model artifact:

`OOS_SCOPE_INTENT_V482.json`

This artifact freezes only the OOS date intent and pre-exposure boundary. It is not the final OOS scope and does not contain `model_freeze_sha256`.

### Frozen scope intent

```json
{
  "artifact": "OOS_SCOPE_INTENT_V482",
  "version": "V4.82",
  "formal_end": "2026-04-17",
  "oos_start": "2026-04-18",
  "oos_end": "2026-09-08",
  "intent_frozen": true,
  "oos_metrics_observed": false
}
```

Rules:

- `oos_start` must be exactly one day after the frozen Formal end for this V4.82 intent.
- `oos_end` is frozen at 2026-09-08, the current project date at the time this intent is established.
- once committed, date changes require a new version/artifact and invalidate this V4.82 scope intent.
- the intent file cannot contain returns, PnL, Sharpe, drawdown, win-rate, hit-rate, alpha, performance, metrics, or signal-result fields.
- it must not read any OOS market data to decide the dates.

### Final OOS scope promotion

Later, after a real `MODEL_FREEZE_V482.json` exists and an OOS-capable official trading calendar is frozen, a promotion step may create the existing Admission-compatible `OOS_SCOPE_V482.json`.

It must inherit `formal_end`, `oos_start`, and `oos_end` exactly from `OOS_SCOPE_INTENT_V482`; date mutation is forbidden.

It then adds:

- `calendar_sha256`
- `universe_sha256`
- `model_freeze_sha256`
- `scope_frozen = true`

Only that final scope may be passed to OOS Admission.

## Calendar Coverage Boundary

The existing V3.57 open-date artifact is trusted for the completed Formal chain, but the recovery system must not assume it covers the intended OOS period through 2026-09-08.

Therefore:

- `formal_calendar_sha256` can be recovered immediately from the existing Formal calendar evidence.
- a distinct OOS-capable calendar evidence check must prove coverage through `2026-09-08` before final `MODEL_FREEZE_V482.calendar_sha256` / `OOS_SCOPE_V482.calendar_sha256` promotion.
- if the existing decoded calendar ends before the intended OOS end, emit `OOS_CALENDAR_COVERAGE_MISSING`.
- do not extend dates by weekday inference or by using an unverified exchange calendar library.

This preserves the same fail-closed standard used throughout V4.80–V4.82.

## Provenance Requirements

Every recoverable hash entry must record enough source provenance in an audit section to reproduce it. The checkpoint should contain an `evidence` object with entries such as:

```json
{
  "universe": {
    "path": "data/pit_st_scope_v480.txt",
    "count": 847,
    "sha256": "..."
  },
  "formal_calendar": {
    "b64_path": "data/OFFICIAL_A_SHARE_OPEN_DATES_V357.csv.gz.b64",
    "hex_path": "data/OFFICIAL_A_SHARE_OPEN_DATES_V357.csv.gz.hex",
    "start": "2020-06-01",
    "end": "2026-04-17",
    "date_n": "<derived integer>",
    "sha256": "..."
  }
}
```

Derived counts must be computed, not guessed in the spec.

## Fail-Closed Blockers

At minimum the evaluator recognizes:

- `FORMAL_ARTIFACT_INVALID`
- `FORMAL_HASH_MISMATCH`
- `UNIVERSE_INVALID`
- `UNIVERSE_COUNT_MISMATCH`
- `FORMAL_CALENDAR_INVALID`
- `FORMAL_CALENDAR_REPRESENTATION_MISMATCH`
- `OOS_CALENDAR_COVERAGE_MISSING`
- `LIQUIDITY_RULE_MISMATCH`
- `STRATEGY_CODE_MISSING`
- `STRATEGY_CODE_INVALID`
- `PARAMETER_SET_MISSING`
- `PARAMETER_SET_INVALID`
- `FACTOR_DEFINITION_MISSING`
- `FACTOR_DEFINITION_INVALID`
- `FORBIDDEN_OOS_METRIC_FIELD`
- `SCOPE_INTENT_INVALID`

Known missing strategy assets are validation blockers, not execution exceptions.

Unexpected programmer/runtime errors must terminate non-zero rather than being converted into a complete recovery checkpoint.

## Data Flow

```text
Closed Formal V4.82
  + frozen universe
  + Formal calendar evidence
  + frozen liquidity rule
  + real strategy code (currently missing)
  + real parameter set (currently missing)
  + real factor definitions (currently missing)
          |
          v
MODEL_ASSET_RECOVERY_CHECKPOINT_V482
          |
          +-- blockers remain --> MODEL_ASSETS_INCOMPLETE_V482
          |
          +-- zero blockers --> MODEL_ASSETS_COMPLETE_V482
                                  |
                                  v
                           MODEL_FREEZE_V482

Separately, before model recovery:

2026-04-17 Formal end
          |
          v
OOS_SCOPE_INTENT_V482
  2026-04-18 .. 2026-09-08
          |
          +-- no OOS data/metrics read
          |
          v
After model + OOS calendar freeze:
OOS_SCOPE_V482
          |
          v
Existing OOS Admission V4.82
```

## Testing Strategy

Use Python 3.12 `unittest` and standard library only, matching the current repository.

The implementation must begin RED and cover at least:

1. valid Formal + universe + Formal calendar recover into checkpoint hashes;
2. canonical universe hash stable against transport trailing newline but sensitive to symbol/order changes;
3. duplicate or non-847 universe blocks;
4. `.b64` and `.hex` calendar payload mismatch blocks;
5. malformed/non-increasing calendar blocks;
6. Formal calendar exact range is enforced;
7. insufficient OOS calendar coverage emits `OOS_CALENDAR_COVERAGE_MISSING`;
8. missing strategy code blocks;
9. missing parameter set blocks;
10. missing factor definitions block;
11. fake/non-64-hex model asset hashes block;
12. recovery checkpoint cannot set `model_freeze_allowed=true` with any blocker;
13. model freeze promotion fails with incomplete checkpoint;
14. valid synthetic complete strategy assets produce schema-valid `MODEL_FREEZE_V482`;
15. scope intent exact dates pass;
16. changed scope-intent dates fail;
17. any nested forbidden metric field in scope intent fails;
18. final scope promotion must inherit intent dates exactly;
19. existing OOS Admission tests remain green;
20. existing Formal readiness/finalizer tests remain green.

Production CI at the initial stage is expected to succeed operationally while emitting:

```json
{
  "status": "MODEL_ASSETS_INCOMPLETE_V482",
  "model_freeze_allowed": false,
  "blockers": [
    "STRATEGY_CODE_MISSING",
    "PARAMETER_SET_MISSING",
    "FACTOR_DEFINITION_MISSING"
  ]
}
```

Additional blockers such as `OOS_CALENDAR_COVERAGE_MISSING` are allowed if the decoded existing calendar does not cover the frozen intent end.

## Files Planned

On `gp/model-freeze-recovery-v482`:

- `docs/superpowers/specs/2026-09-08-model-freeze-recovery-v482-design.md`
- `scripts/model_asset_recovery_v482.py`
- `scripts/test_model_asset_recovery_v482.py`
- `scripts/model_freeze_promote_v482.py`
- `scripts/test_model_freeze_promote_v482.py`
- `data/OOS_SCOPE_INTENT_V482.json`
- `.github/workflows/model-freeze-recovery-v482.yml`

Do not create production `data/MODEL_FREEZE_V482.json` until the real three strategy-side assets exist.

Do not create production `data/OOS_SCOPE_V482.json` until both the real model freeze and the OOS-capable calendar are frozen.

## Success Criteria

This phase is successful when:

- recoverable Formal/universe/calendar/liquidity evidence is cryptographically materialized;
- missing strategy assets are machine-readable blockers rather than vague notes;
- OOS window intent is frozen before any OOS metric exposure;
- the system proves it cannot promote a fake/incomplete model freeze;
- production remains fail-closed until the genuine GP model assets are recovered;
- existing Formal and OOS Admission boundaries remain unchanged.
