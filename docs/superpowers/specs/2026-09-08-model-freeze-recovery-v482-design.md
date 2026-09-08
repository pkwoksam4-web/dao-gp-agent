# Model Freeze Recovery V4.82 Design

## Purpose

Create a separate, fail-closed recovery layer for the real GP model assets required by OOS Admission V4.82. The layer must distinguish assets already recoverable from the audited repository/evidence chain from strategy assets that are genuinely missing. It must never synthesize, infer, or substitute strategy-code, parameter, or factor-definition hashes merely to satisfy admission.

## Architectural Boundary

The existing OOS Admission gate remains unchanged.

- `scripts/oos_admission_v482.py` is not modified by this subsystem.
- `FORMAL_READINESS_FINAL_V482` remains the authoritative Formal artifact.
- Formal continues to emit `oos_metrics_allowed = false`.
- Recovery may inspect and hash already frozen Formal/model-input assets, but must not read OOS returns, PnL, Sharpe, drawdown, hit-rate, signals, or performance outputs.
- A recovery checkpoint is evidence inventory, not an OOS admission decision.
- Only a complete, genuine model freeze may create `MODEL_FREEZE_V482.json`.

Implementation branch: `gp/model-freeze-recovery-v482`, based on `gp/oos-admission-v482`.

## Known Recoverable Evidence

The current audited chain already establishes these real assets:

1. **Formal artifact**
   - artifact `FORMAL_READINESS_FINAL_V482`
   - Formal window `2020-06-01` through `2026-04-17`
   - universe 847
   - Formal-valid 844
   - exact N/A/zero-trade symbols: `600074.SH`, `600485.SH`, `600677.SH`
   - liquidity threshold CNY 80,000,000
   - current-trade violations 0
   - ST-overlay violations 0

2. **Universe scope**
   - `data/pit_st_scope_v480.txt`
   - metadata `data/pit_st_scope_v480.meta.json`
   - metadata records 847 unique symbols and Formal window `[2020-06-01, 2026-04-17]`.

3. **Formal trading-calendar evidence**
   - `data/OFFICIAL_A_SHARE_OPEN_DATES_V357.csv.gz.b64`
   - mirrored representation `data/OFFICIAL_A_SHARE_OPEN_DATES_V357.csv.gz.hex`

4. **Liquidity rule**
   - exact threshold CNY 80,000,000, already bound into the closed Formal market-data chain.

These inputs are recoverable evidence. None substitutes for the GP scoring model.

## Genuinely Missing Strategy Assets

Repository history, old branches, prior file-recovery attempts, and early workflow history do not contain a recoverable complete copy of the original GP V1.1 strategy implementation. The recovery layer therefore treats these as independent hard blockers until actual authoritative bytes are supplied or found:

- `STRATEGY_CODE_MISSING`
  - authoritative GP scorer/execution code is absent.
  - historical names such as `gp_v11_scoring.py` and `run_gp_walkforward.py` are search clues only.

- `PARAMETER_SET_MISSING`
  - authoritative frozen strategy parameters, including the original 12-factor weights and thresholds, are absent as a complete frozen asset.

- `FACTOR_DEFINITION_MISSING`
  - authoritative complete factor-definition package is absent.
  - QFQ/PIT-ST/RAW/data-repair code must never be relabeled as the scoring factor definition.

No Sina, Sohu, Eastmoney, Longbridge, Tushare, QFQ, PIT/ST, RAW, liquidity, or event-repair artifact can clear these three strategy-side blockers.

## Recovery Checkpoint

Create deterministic artifact `MODEL_ASSET_RECOVERY_CHECKPOINT_V482.json`.

Required fields:

- `artifact = MODEL_ASSET_RECOVERY_CHECKPOINT_V482`
- `version = V4.82`
- `status` is one of `MODEL_ASSETS_INCOMPLETE_V482` or `MODEL_ASSETS_COMPLETE_V482`
- `formal_artifact_sha256`: lowercase 64-hex SHA256 or null if Formal is invalid
- `universe_sha256`: lowercase 64-hex SHA256 or null if universe is invalid
- `formal_calendar_sha256`: lowercase 64-hex SHA256 or null if Formal calendar is invalid
- `liquidity_threshold_cny = 80000000`
- `formal_end = 2026-04-17`
- `recoverable`: booleans for Formal artifact, universe, Formal calendar, and liquidity rule
- `strategy_assets`: nullable hashes for strategy code, parameter set, and factor definitions
- `blockers`: sorted unique blocker codes
- `model_freeze_allowed`: boolean
- `evidence`: reproducible source paths, counts, ranges, and derived hashes

Status rules:

- any blocker => `MODEL_ASSETS_INCOMPLETE_V482` and `model_freeze_allowed = false`
- zero blockers => `MODEL_ASSETS_COMPLETE_V482` and `model_freeze_allowed = true`

The checkpoint never contains `oos_metrics_allowed`.

## Hashing Rules

### Formal artifact

Use exactly the OOS Admission canonical JSON rule:

- UTF-8 JSON
- `sort_keys=True`
- `separators=(',', ':')`
- `ensure_ascii=False`
- no trailing newline in canonical bytes

For the same Formal JSON object, the recovery hash must equal the hash already produced by OOS Admission.

### Universe

`universe_sha256` is SHA256 of canonical universe bytes, not a Git blob SHA.

Canonicalization:

1. read `data/pit_st_scope_v480.txt` as UTF-8;
2. trim surrounding whitespace per line;
3. reject blank lines;
4. require exactly 847 entries;
5. require all entries unique;
6. preserve frozen source ordering;
7. join with `\n`, no trailing newline.

Transport-only trailing newline differences therefore do not change the canonical universe hash; symbol/order changes do.

### Formal calendar

`formal_calendar_sha256` is SHA256 of the decoded Formal date sequence, not the `.b64` text, `.hex` text, Git object SHA, or gzip bytes.

Canonicalization:

1. decode both repository wrappers;
2. require both wrappers to yield identical gzip payload bytes;
3. decompress and parse the CSV date sequence;
4. select `2020-06-01` through `2026-04-17` inclusive;
5. require strictly increasing unique ISO dates;
6. join selected dates with `\n`, no trailing newline.

The derived Formal date count is recorded at runtime; no count is guessed in this specification.

### Strategy assets

When genuine strategy assets appear:

- `strategy_code_sha256`: SHA256 of exact frozen source bytes. If strategy code is multi-file, an explicit manifest must list files and ordering; silent concatenation is forbidden.
- `parameter_sha256`: SHA256 of canonical JSON for the frozen parameter manifest.
- `factor_definition_sha256`: SHA256 of canonical JSON for the frozen factor-definition manifest, or exact bytes if the authoritative artifact is a single non-JSON file.

Each digest must include reproducible source provenance in the checkpoint.

## Model Freeze Promotion

The recovery layer may emit `MODEL_FREEZE_V482.json` only when the checkpoint is `MODEL_ASSETS_COMPLETE_V482` with zero blockers.

The production manifest must match the existing OOS Admission schema exactly:

- `artifact = MODEL_FREEZE_V482`
- `version = V4.82`
- non-empty stable `strategy_id`
- lowercase 64-hex `strategy_code_sha256`
- lowercase 64-hex `parameter_sha256`
- lowercase 64-hex `universe_sha256`
- lowercase 64-hex `factor_definition_sha256`
- lowercase 64-hex `calendar_sha256`
- lowercase 64-hex `formal_artifact_sha256`
- `liquidity_threshold_cny = 80000000`
- `formal_end = 2026-04-17`
- `frozen = true`

Promotion invariants:

- Formal hash equals the closed Formal canonical hash.
- Universe hash equals the recovery checkpoint universe hash.
- Liquidity threshold is exact.
- No blocker remains.
- No placeholder or inferred hash is permitted.
- `calendar_sha256` must refer to a calendar evidence package proven suitable for the final OOS scope; the Formal-only calendar hash is not automatically promoted into this field.

## OOS Scope Intent Freeze

Freeze the OOS date intent before model recovery to prevent choosing a favorable window after seeing model/OOS behavior.

Create `data/OOS_SCOPE_INTENT_V482.json` with exact fields:

```json
{
  "artifact": "OOS_SCOPE_INTENT_V482",
  "version": "V4.82",
  "formal_end": "2026-04-17",
  "oos_start": "2026-04-18",
  "oos_end": "2026-09-08",
  "intent_frozen": true,
  "pre_exposure_confirmed": true
}
```

Rules:

- dates are frozen by this V4.82 artifact and cannot be edited in place;
- any date change requires a new version/artifact;
- no OOS market data is read to choose these dates;
- the intent may not contain nested or top-level fields named `return`, `returns`, `pnl`, `alpha`, `sharpe`, `drawdown`, `hit_rate`, `win_rate`, `performance`, `metrics`, or signal-result equivalents;
- `pre_exposure_confirmed = true` means this intent was established before this project opened OOS metrics. It is an assertion about workflow state, not a computed performance field.

## Final OOS Scope Promotion

After a genuine `MODEL_FREEZE_V482.json` exists and an official OOS-capable trading calendar is frozen, a promotion step may create the existing Admission-compatible `OOS_SCOPE_V482.json`.

It must inherit these date fields exactly from `OOS_SCOPE_INTENT_V482`:

- `formal_end`
- `oos_start`
- `oos_end`

It then adds the existing Admission-required bindings:

- `calendar_sha256`
- `universe_sha256`
- `model_freeze_sha256`
- `scope_frozen = true`

Only this final scope is eligible for OOS Admission.

## Calendar Coverage Boundary

The V3.57 open-date artifact is trusted for the completed Formal chain, but the recovery layer must not assume it covers the intended OOS period through `2026-09-08`.

Therefore:

- the existing evidence may immediately produce `formal_calendar_sha256` after representation and range validation;
- a distinct OOS-capable calendar evidence check must prove official coverage through `2026-09-08` before final model/scope calendar binding;
- if available calendar evidence ends before the intended OOS end, emit `OOS_CALENDAR_COVERAGE_MISSING`;
- never extend dates by weekday inference or an unverified exchange-calendar library.

## Fail-Closed Blockers

At minimum:

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

Known missing strategy assets are validation blockers, not runtime exceptions. Unexpected programmer/runtime errors terminate non-zero rather than being converted into a complete checkpoint.

## Data Flow

```text
Closed Formal V4.82
  + frozen universe
  + Formal calendar evidence
  + frozen liquidity rule
  + real strategy code (missing)
  + real parameter set (missing)
  + real factor definitions (missing)
          |
          v
MODEL_ASSET_RECOVERY_CHECKPOINT_V482
          |
          +-- blockers --> MODEL_ASSETS_INCOMPLETE_V482
          |
          +-- zero blockers --> MODEL_ASSETS_COMPLETE_V482
                                  |
                                  v
                           MODEL_FREEZE_V482

Separately, before any OOS exposure:

Formal end 2026-04-17
          |
          v
OOS_SCOPE_INTENT_V482
2026-04-18 .. 2026-09-08
          |
          v
After model + official OOS calendar freeze:
OOS_SCOPE_V482
          |
          v
Existing OOS Admission V4.82
```

## Testing Strategy

Use Python 3.12 `unittest` and standard library only. Implementation begins RED.

Required coverage:

1. valid Formal + universe + Formal calendar materialize recoverable hashes;
2. universe hash ignores transport trailing newline but detects symbol/order changes;
3. duplicate or non-847 universe blocks;
4. `.b64`/`.hex` calendar payload mismatch blocks;
5. malformed or non-increasing calendar blocks;
6. exact Formal range is enforced;
7. insufficient OOS calendar coverage emits `OOS_CALENDAR_COVERAGE_MISSING`;
8. each missing strategy-side asset emits its own blocker;
9. malformed strategy asset digest/manifest blocks;
10. checkpoint cannot set `model_freeze_allowed=true` with any blocker;
11. model-freeze promotion rejects incomplete checkpoint;
12. valid synthetic complete assets produce schema-valid `MODEL_FREEZE_V482`;
13. scope intent exact dates pass;
14. changed scope-intent dates fail;
15. nested forbidden result/metric fields in scope intent fail;
16. final scope promotion must inherit intent dates exactly;
17. existing OOS Admission tests remain green;
18. existing Formal readiness/finalizer tests remain green.

Initial production CI is expected to succeed operationally while emitting `MODEL_ASSETS_INCOMPLETE_V482`, `model_freeze_allowed = false`, and the three missing strategy blockers. It may additionally emit `OOS_CALENDAR_COVERAGE_MISSING` if existing official calendar evidence does not cover the frozen intent end.

## Planned Files

On `gp/model-freeze-recovery-v482`:

- `docs/superpowers/specs/2026-09-08-model-freeze-recovery-v482-design.md`
- `scripts/model_asset_recovery_v482.py`
- `scripts/test_model_asset_recovery_v482.py`
- `scripts/model_freeze_promote_v482.py`
- `scripts/test_model_freeze_promote_v482.py`
- `data/OOS_SCOPE_INTENT_V482.json`
- `.github/workflows/model-freeze-recovery-v482.yml`

Do not create production `data/MODEL_FREEZE_V482.json` until the real three strategy-side assets exist.

Do not create production `data/OOS_SCOPE_V482.json` until both a genuine model freeze and OOS-capable official calendar are frozen.

## Success Criteria

This phase is complete when:

- recoverable Formal/universe/Formal-calendar/liquidity evidence is cryptographically materialized;
- missing strategy assets are explicit machine-readable blockers;
- OOS date intent is frozen before any OOS metric exposure;
- incomplete/fake strategy packages cannot be promoted;
- production remains fail-closed until genuine GP model assets are recovered;
- existing Formal and OOS Admission boundaries remain unchanged.
