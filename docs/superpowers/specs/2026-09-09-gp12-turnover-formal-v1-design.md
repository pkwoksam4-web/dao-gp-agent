# GP12 Turnover Formal V1 Design

Status: approved architectural design for closing `TURNOVER_RATIO_UNBOUND` in the Formal-only evidence chain for `GP12_REBUILD_CANDIDATE_V1`. This subsystem is diagnostic and evidence-producing only. It does not approve the candidate, does not freeze a model, does not consume OOS rows, and does not change the F11 formula.

## 1. Purpose

`GP12_FORMAL_INPUT_READINESS_V1` currently leaves `amount_turnover` as:

- `binding_state = UNBOUND`
- `pit_state = PIT_UNVERIFIED`
- blocker `TURNOVER_RATIO_UNBOUND`

F11 `price_fund_efficiency` requires `sum(turnover_ratio[-5:])` and therefore cannot be Formal-ready until a production-grade historical turnover ratio is bound.

The shortest evidence path is:

`Sina historical outstanding-share series`
+ `signed Full RAW V4.82 volume`
→ **GP12 Turnover Formal V1**
→ `GP12_TURNOVER_FORMAL_V1`
→ readiness evidence binding for `amount_turnover`

The canonical calculation is:

`turnover_ratio[d] = volume_shares[d] / outstanding_share_shares[d]`

No price adjustment is required for this calculation.

## 2. Why this path

Three paths were considered:

1. **Recommended: Sina historical outstanding share + signed RAW volume.** Reuses the already-audited Full RAW panel, adds only the missing denominator, and matches the current AKShare Sina implementation semantics for historical turnover.
2. **Eastmoney `f61`.** Structurally direct but the existing GitHub Actions probe observed `RemoteDisconnected` for all sampled symbols, so current source reachability is not proven.
3. **Third-party pre-materialized turnover datasets.** Potentially fast to download but weaker for provenance, PIT semantics, and exact universe/row binding.

The subsystem therefore uses option 1 as the canonical production path. Eastmoney or other datasets may be future cross-checks but cannot silently replace the source contract.

## 3. Existing evidence that must remain authoritative

The subsystem binds to the existing Formal-only evidence package and MUST reject mismatches.

### 3.1 Candidate identity

- `strategy_id = GP12_REBUILD_CANDIDATE_V1`
- candidate parameter canonical SHA256: `22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204`
- candidate factor canonical SHA256: `b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e`
- F11 input family remains exactly `stock_adjusted_close + amount_turnover + main_net_flow`.

### 3.2 Formal boundary and universe

- Formal range: `2020-06-01 .. 2026-04-17` inclusive
- Formal calendar semantic SHA256: `5a872a47cf7a338cc48aa628b8de46053fddc3ed161a2617550199d0607efae7`
- frozen 847-symbol universe SHA256: `dfe5c75692d38e5fde7cd5c32eb2ed090a8ab6dffcfd41d5ebda07dc2d6d96fb`
- Formal artifact semantic SHA256: `e642481399a05635d07b1baa39f57d3aa84dfd1c18e315edd927ec42da553796`

### 3.3 Signed RAW volume

Bind the existing Full RAW evidence identity:

- source artifact: `gp-sohu-full-raw-v482-reaudit`
- source SHA256: `cee7e91f1fda605f7c3bdf41c3f4a7796feeae83f8c3702e50900e6af3fa9550`
- expected/corrected RAW trade rows: `1,011,607`
- universe: 847 symbols
- fields include `symbol,date,open,high,low,close,volume,amount,source`
- Sohu parser normalizes upstream volume from 100-share lots to shares via `volume = raw_volume * 100.0`.

The turnover subsystem MUST NOT refetch or substitute RAW volume when the signed artifact is available.

## 4. Sina outstanding-share source contract

The source endpoint family is the Sina stock share-amount history used by current AKShare `stock_zh_a_daily`:

`https://stock.finance.sina.com.cn/stock/api/jsonp.php/var%20KKE_ShareAmount_{symbol}=/StockService.getAmountBySymbol?_=20&symbol={symbol}`

For each symbol, the collector must retain:

- exchange-qualified GP symbol;
- Sina symbol (`shXXXXXX` / `szXXXXXX`);
- request URL or normalized request identity;
- HTTP status and fetch timestamp;
- exact raw response bytes SHA256;
- decoded dated records;
- normalized `outstanding_share_shares` values;
- parser/version identity.

AKShare currently interprets the endpoint values as units of 10,000 shares and converts by multiplying by 10,000. GP12 Turnover Formal V1 adopts that normalization only after source parsing confirms finite positive numeric values.

A successful HTTP response is not sufficient evidence. Empty, malformed, ambiguous, or nonpositive share-capital data remain blocked.

## 5. Point-in-time semantics

The core PIT rule is strictly backward-looking piecewise-constant capital state.

For a Formal trade date `d`:

1. consider only source share-capital records with `record_date <= d`;
2. select the latest such record;
3. never backfill from a future share-capital record;
4. never interpolate between future and past records;
5. if no prior/equal dated record exists, the trade row is unresolved and blocks full readiness.

Forward-fill is permitted only from an already-effective earlier/equal source record to later trade dates.

`PIT_VERIFIED` requires evidence that the source record date is an effective/known-at boundary suitable for this use. Merely reproducing AKShare's forward-fill behavior does not by itself prove PIT validity.

The implementation must retain an explicit `share_date_semantics_evidence` record. It may establish the semantics from a documented Sina stock-structure contract/page or from independently retrievable Sina stock-structure history that identifies the same dated capital changes as effective historical states. If neither source path establishes what the date means, the artifact remains `PIT_UNVERIFIED` or `PIT_PARTIAL` with `SINA_SHARE_DATE_SEMANTICS_UNVERIFIED` even when all numeric rows are present.

No row after `2026-04-17` may influence any share-capital state, audit, fallback, or readiness decision.

## 6. Turnover materialization

For every signed RAW trade row:

- require exact symbol/date identity within the frozen 847-symbol universe and Formal calendar;
- read `volume` in shares from the signed RAW panel;
- resolve `outstanding_share_shares` using the PIT rule above;
- require both values finite and strictly positive;
- calculate `turnover_ratio = volume_shares / outstanding_share_shares` using full floating precision;
- do not clip, winsorize, scale, round, or replace the ratio in the evidence artifact.

The candidate F11 scorer remains responsible for its own formula semantics. This subsystem only supplies the raw daily `turnover_ratio` family.

The canonical row schema is:

- `symbol`
- `date`
- `volume_shares`
- `outstanding_share_shares`
- `turnover_ratio`
- `raw_volume_source_artifact`
- `raw_volume_source_sha256`
- `share_source`
- `share_record_date`
- `share_raw_sha256`

Rows must be sorted by frozen universe order, then ascending Formal date, with no duplicates.

## 7. Required artifacts

### 7.1 `SINA_SHARE_AMOUNT_MANIFEST_GP12_V1`

Audit/provenance manifest for all attempted symbols. Required top-level fields:

- `artifact = SINA_SHARE_AMOUNT_MANIFEST_GP12_V1`
- `version = 1.0`
- `formal_end = 2026-04-17`
- `universe_sha256`
- `symbol_n`
- `symbols_fetched`
- `symbols_failed`
- `raw_response_count`
- `normalized_record_count`
- `parser_version`
- `source_endpoint_family`
- `share_date_semantics_evidence`
- `symbol_evidence`
- `blockers`
- `formal_admission = false`
- `model_freeze_allowed = false`
- `oos_metrics_allowed = false`

Each symbol evidence record binds the exact raw response SHA256 and normalized record range.

### 7.2 `GP12_TURNOVER_FORMAL_V1`

Primary Formal turnover artifact. Required summary fields:

- `artifact = GP12_TURNOVER_FORMAL_V1`
- `version = 1.0`
- `strategy_id = GP12_REBUILD_CANDIDATE_V1`
- `formal_start = 2020-06-01`
- `formal_end = 2026-04-17`
- `formal_artifact_sha256`
- `formal_calendar_sha256`
- `universe_sha256`
- `candidate_parameters_sha256`
- `candidate_factors_sha256`
- `raw_volume_source_artifact`
- `raw_volume_source_sha256`
- `share_manifest_sha256`
- `turnover_rows_sha256`
- `symbol_n`
- `expected_trade_rows`
- `materialized_trade_rows`
- `duplicate_row_n`
- `missing_turnover_row_n`
- `extra_turnover_row_n`
- `nonpositive_volume_n`
- `nonpositive_outstanding_share_n`
- `nonfinite_turnover_n`
- `future_share_record_violation_n`
- `unresolved_prior_share_record_n`
- `pit_state`
- `status`
- `blockers`
- `formal_feature_ready`
- `candidate_freeze_ready = false`
- `model_freeze_allowed = false`
- `oos_metrics_allowed = false`

### 7.3 Hash conventions

All JSON semantic hashes in this subsystem use the same canonical encoding as the readiness layer:

- UTF-8;
- recursive key sort;
- separators `(',', ':')`;
- `ensure_ascii = false`;
- finite JSON only;
- no trailing newline included in the canonical bytes.

`share_manifest_sha256` is the canonical JSON SHA256 of the complete `SINA_SHARE_AMOUNT_MANIFEST_GP12_V1` object.

`turnover_rows_sha256` is the SHA256 of the exact UTF-8 CSV bytes after deterministic row ordering and a fixed header/newline convention defined in implementation tests.

The readiness binder sets `amount_turnover.source_sha256` to the canonical JSON SHA256 of the complete `GP12_TURNOVER_FORMAL_V1` summary object. The summary itself does not contain this self-hash, so there is no recursive hashing ambiguity.

The workflow artifact also records the ZIP digest separately. ZIP digest, raw-response hash, row-CSV hash, manifest hash, and summary semantic hash are distinct identities and MUST NOT be substituted for one another.

## 8. Pass and fail-closed states

A full pass requires all of the following:

- exact candidate package identity;
- exact Formal artifact/calendar/universe identity;
- signed RAW volume source identity matches the readiness contract;
- exactly 847 frozen symbols evaluated;
- turnover row set equals the signed RAW trade-row key set exactly;
- no duplicate, missing, or extra rows;
- no nonpositive/nonfinite input or turnover rows;
- no future share-capital record used for an earlier trade date;
- no unresolved trade date lacking a prior/equal share-capital state;
- source date semantics sufficient for `PIT_VERIFIED`.

On full pass:

- `status = PASS_FORMAL_TURNOVER_V1`
- `pit_state = PIT_VERIFIED`
- `formal_feature_ready = true`

Otherwise:

- `status = BLOCKED_FORMAL_TURNOVER_V1`
- `formal_feature_ready = false`
- blockers are sorted and unique.

Network/source unavailability is a validation blocker, not a factor/model FAIL. Unexpected programmer/schema corruption is a nonzero runtime failure.

## 9. Deterministic blockers

At minimum support:

- `CANDIDATE_PACKAGE_IDENTITY_MISMATCH`
- `FORMAL_EVIDENCE_INVALID`
- `FORMAL_BOUNDARY_VIOLATION`
- `CALENDAR_BINDING_INVALID`
- `UNIVERSE_BINDING_INVALID`
- `RAW_VOLUME_ARTIFACT_INVALID`
- `RAW_VOLUME_UNIT_INVALID`
- `SINA_SHARE_SOURCE_UNAVAILABLE`
- `SINA_SHARE_PAYLOAD_INVALID`
- `SINA_SHARE_VALUE_INVALID`
- `SINA_SHARE_DATE_SEMANTICS_UNVERIFIED`
- `SINA_SHARE_COVERAGE_INCOMPLETE`
- `TURNOVER_ROWSET_MISMATCH`
- `TURNOVER_DUPLICATE_ROW`
- `TURNOVER_NONFINITE_VALUE`
- `TURNOVER_FUTURE_SHARE_RECORD_VIOLATION`
- `TURNOVER_PRIOR_SHARE_RECORD_MISSING`
- `FORBIDDEN_OOS_OR_PERFORMANCE_FIELD`

No blocker may be cleared by substituting Eastmoney, current share capital, present-day market-cap data, or a proxy ratio.

## 10. Readiness integration

The turnover subsystem does not modify factor formulas. Its only downstream semantic promotion is the `amount_turnover` family.

If and only if `GP12_TURNOVER_FORMAL_V1` passes all gates, a readiness evidence binder may emit a derived `GP12_FORMAL_INPUT_EVIDENCE_V1` package in which `amount_turnover` becomes:

- `binding_state = BOUND_VERIFIED_ARTIFACT`
- `pit_state = PIT_VERIFIED`
- `source_artifact = GP12_TURNOVER_FORMAL_V1`
- `source_sha256 = canonical SHA256 of the complete GP12_TURNOVER_FORMAL_V1 summary object`
- `coverage_start = 2020-06-01`
- `coverage_end = 2026-04-17`
- `blockers = []`

All other feature-family and supporting-evidence records must remain byte-for-byte semantically unchanged except for deterministic regenerated ordering/serialization.

The derived package is then re-run through the existing `gp12_formal_input_readiness_v1.py` validator. The existing validator remains authoritative for aggregate factor/scoring readiness.

Closing `TURNOVER_RATIO_UNBOUND` MUST NOT clear `MAIN_NET_FLOW_UNBOUND`. Therefore F11 remains blocked until `main_net_flow` is independently bound and `stock_adjusted_close` PIT semantics are also ready.

## 11. OOS and model-freeze safety

Every production and test artifact in this subsystem fixes:

- `candidate_adoption_status = UNAPPROVED` where applicable;
- `candidate_freeze_ready = false`;
- `model_freeze_allowed = false`;
- `oos_metrics_allowed = false`.

The subsystem must recursively reject forbidden OOS/performance keys already used by the readiness layer, including `return`, `returns`, `pnl`, `alpha`, `sharpe`, `drawdown`, `hit_rate`, `win_rate`, `performance`, and `metrics`.

No OOS row, future outcome, score, rank, signal, or performance statistic is needed to close the turnover evidence blocker.

## 12. Workflow architecture

Use a dedicated workflow on `gp/gp12-turnover-formal-v1` with isolated jobs:

1. unit/regression tests;
2. read-only single-symbol Sina source probe;
3. only if the probe is structurally valid, production 847-symbol share-capital collection with conservative throttling/retries;
4. bind/download the signed Full RAW artifact;
5. materialize and audit turnover;
6. if full pass, generate derived readiness evidence and rerun existing readiness validator;
7. upload all provenance, manifests, normalized rows, turnover rows, audit summaries, and hashes.

The workflow may complete successfully while the turnover artifact is fail-closed BLOCKED because a known data/source blocker is not a programmer error. CI must print the terminal state and blockers explicitly so a green workflow is never confused with a green data gate.

Do not merge or overwrite the parent readiness branch automatically.

## 13. Planned implementation files

Expected implementation surface after spec approval:

- `scripts/gp12_sina_share_amount_v1.py`
- `scripts/test_gp12_sina_share_amount_v1.py`
- `scripts/gp12_turnover_formal_v1.py`
- `scripts/test_gp12_turnover_formal_v1.py`
- `scripts/gp12_turnover_readiness_bind_v1.py`
- `scripts/test_gp12_turnover_readiness_bind_v1.py`
- `.github/workflows/gp12-turnover-formal-v1.yml`
- `docs/superpowers/plans/2026-09-09-gp12-turnover-formal-v1.md` after the written-spec review gate.

No production turnover or share-capital data file is committed to git merely to make tests pass. Production evidence belongs in signed workflow artifacts unless a later explicit policy freezes a compact manifest in-repo.

## 14. TDD and regression requirements

Implementation uses Python 3.12 `unittest` with RED before production code.

Required tests include:

1. Sina JSONP parser accepts a valid dated share-capital series and normalizes 10,000-share units correctly.
2. malformed/empty/nonpositive share-capital payloads block.
3. PIT resolver uses latest record with `record_date <= trade_date` only.
4. future record is never backfilled into an earlier trade date.
5. missing prior/equal capital record blocks that trade row.
6. signed RAW volume unit contract is shares, not lots.
7. turnover calculation uses exact RAW volume divided by resolved outstanding shares.
8. exact row-set equality with the signed RAW trade keys is enforced.
9. duplicate/missing/extra rows block.
10. Formal end `2026-04-17` is enforced and post-Formal rows are rejected.
11. 847-symbol universe identity/count are enforced.
12. source/network failure emits deterministic source blocker instead of model/factor FAIL.
13. full synthetic pass yields `PASS_FORMAL_TURNOVER_V1`, `PIT_VERIFIED`, and `formal_feature_ready=true`.
14. incomplete PIT/source semantics cannot be promoted to ready.
15. readiness binder changes only `amount_turnover` on full pass.
16. `MAIN_NET_FLOW_UNBOUND` remains after turnover promotion.
17. F11 remains blocked while any of `stock_adjusted_close`, `amount_turnover`, or `main_net_flow` is not ready.
18. existing GP12 readiness tests remain green.
19. existing Formal V4.82 regression tests remain green.
20. no test fixture contains forbidden OOS/performance fields in production outputs.
21. manifest, row CSV, summary semantic hash, and ZIP digest identities cannot be interchanged.

## 15. Success criterion

This subsystem succeeds when it truthfully reaches one of two terminal outcomes:

- **PASS**: a 847-symbol, exact Formal-row, PIT-verified turnover artifact is produced and `TURNOVER_RATIO_UNBOUND` is removed from the derived readiness evidence; or
- **BLOCKED**: the exact remaining source/PIT/coverage blocker is emitted without fabricating turnover values or changing any unrelated readiness state.

A PASS does not mean GP12 is scoring-ready, adopted, frozen, or OOS-enabled. It only closes the `amount_turnover` evidence family.