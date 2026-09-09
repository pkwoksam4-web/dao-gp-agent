# GP12 Turnover Formal V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fail-closed Formal-only turnover evidence subsystem that derives `turnover_ratio = signed RAW volume / PIT-resolved Sina historical outstanding shares`, and only removes `TURNOVER_RATIO_UNBOUND` when the full 847-symbol Formal gate passes.

**Architecture:** Keep source acquisition/provenance, turnover materialization/audit, and readiness binding as separate modules. The source collector records exact Sina raw-response identities and dated share-capital states; the materializer joins only against the already-signed V4.82 RAW trade-row key set and never refetches volume; the readiness binder may change only `amount_turnover`, after which the existing GP12 readiness validator remains authoritative.

**Tech Stack:** Python 3.12 standard library + `requests`, `unittest`, GitHub Actions, existing `gp12_formal_input_readiness_v1.py` contracts/artifacts.

**Spec:** `docs/superpowers/specs/2026-09-09-gp12-turnover-formal-v1-design.md`

## Global Constraints

- Strategy identity remains `GP12_REBUILD_CANDIDATE_V1` and adoption status remains `UNAPPROVED`.
- Formal range is exactly `2020-06-01..2026-04-17`; no post-Formal row may affect collection, PIT resolution, audits, readiness, labels, or diagnostics.
- Candidate parameter SHA256 is `22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204`.
- Candidate factor SHA256 is `b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e`.
- Formal artifact SHA256 is `e642481399a05635d07b1baa39f57d3aa84dfd1c18e315edd927ec42da553796`.
- Formal calendar SHA256 is `5a872a47cf7a338cc48aa628b8de46053fddc3ed161a2617550199d0607efae7`.
- Frozen 847-symbol universe SHA256 is `dfe5c75692d38e5fde7cd5c32eb2ed090a8ab6dffcfd41d5ebda07dc2d6d96fb`.
- Signed RAW source artifact is `gp-sohu-full-raw-v482-reaudit`, digest `cee7e91f1fda605f7c3bdf41c3f4a7796feeae83f8c3702e50900e6af3fa9550`, expected trade rows `1,011,607`.
- RAW `volume` is shares; the subsystem must reject a lot-unit interpretation.
- Sina share-amount source is authoritative only for the missing denominator; Eastmoney/current-capital/proxy data may not silently substitute.
- Latest share record with `record_date <= trade_date` is the only allowed resolver. Future records are never backfilled.
- Reproducing AKShare forward-fill does not prove PIT. Missing date-semantics evidence keeps `SINA_SHARE_DATE_SEMANTICS_UNVERIFIED`.
- Known source/network failure produces a BLOCKED artifact, not a model/factor FAIL and not an uncaught exception.
- Canonical JSON hashing matches the readiness layer: UTF-8, recursively sorted keys, separators `(',', ':')`, `ensure_ascii=false`, finite JSON, no trailing newline in canonical bytes.
- `share_manifest_sha256`, `turnover_rows_sha256`, turnover-summary semantic SHA and ZIP digest are distinct and never interchangeable.
- `candidate_freeze_ready=false`, `model_freeze_allowed=false`, and `oos_metrics_allowed=false` in every production/test terminal state.
- No output may contain forbidden OOS/performance fields.

---

### Task 1: Sina historical share-amount parser, fetch evidence, and PIT resolver

**Files:**
- Create: `scripts/gp12_sina_share_amount_v1.py`
- Create: `scripts/test_gp12_sina_share_amount_v1.py`
- Modify: `.github/workflows/gp12-turnover-formal-v1.yml` only when the first RED workflow is introduced

**Interfaces:**
- Consumes: exchange-qualified symbols such as `600000.SH`; Sina JSONP bytes from `StockService.getAmountBySymbol`; optional explicit date-semantics evidence object.
- Produces:
  - `normalize_symbol(symbol: str) -> str`
  - `to_sina_symbol(symbol: str) -> str`
  - `parse_share_amount_bytes(symbol: str, raw: bytes) -> list[dict]`
  - `resolve_share_state(records: list[dict], trade_date: str) -> dict | None`
  - `build_symbol_evidence(symbol: str, raw: bytes, fetched_at: str, http_status: int) -> dict`
  - `build_share_manifest(symbol_evidence: list[dict], universe_sha256: str, date_semantics_evidence: dict | None) -> dict`
  - `fetch_share_amount(session, symbol, timeout=20, retries=3) -> tuple[bytes, dict]`

- [ ] **Step 1: Write the RED parser/PIT tests**

Create `scripts/test_gp12_sina_share_amount_v1.py` with tests that assert:

```python
class SinaShareAmountV1Tests(unittest.TestCase):
    def test_parse_valid_jsonp_multiplies_10000_share_units(self):
        raw = b'var KKE_ShareAmount_sh600000=[["2020-01-01","123.45"],["2021-01-01","150"]];'
        rows = mod.parse_share_amount_bytes('600000.SH', raw)
        self.assertEqual(rows[0]['outstanding_share_shares'], 1_234_500.0)
        self.assertEqual(rows[1]['outstanding_share_shares'], 1_500_000.0)

    def test_resolver_uses_latest_record_not_after_trade_date(self):
        records = [
            {'record_date':'2020-01-01','outstanding_share_shares':100.0},
            {'record_date':'2020-03-01','outstanding_share_shares':200.0},
        ]
        self.assertEqual(mod.resolve_share_state(records, '2020-02-15')['record_date'], '2020-01-01')

    def test_future_record_is_never_backfilled(self):
        records = [{'record_date':'2020-03-01','outstanding_share_shares':200.0}]
        self.assertIsNone(mod.resolve_share_state(records, '2020-02-15'))

    def test_empty_malformed_or_nonpositive_payload_is_invalid(self):
        for raw in (b'', b'not jsonp', b'var KKE_ShareAmount_sh600000=[["2020-01-01","0"]];'):
            with self.assertRaises(ValueError):
                mod.parse_share_amount_bytes('600000.SH', raw)

    def test_manifest_without_date_semantics_stays_blocked(self):
        manifest = mod.build_share_manifest([valid_symbol_evidence()], 'dfe5c75692d38e5fde7cd5c32eb2ed090a8ab6dffcfd41d5ebda07dc2d6d96fb', None)
        self.assertIn('SINA_SHARE_DATE_SEMANTICS_UNVERIFIED', manifest['blockers'])
        self.assertFalse(manifest['model_freeze_allowed'])
        self.assertFalse(manifest['oos_metrics_allowed'])
```

Also test duplicate record dates, post-Formal records, unknown exchange, raw-response SHA identity, exact endpoint family, and source/network exception normalization to `SINA_SHARE_SOURCE_UNAVAILABLE`.

- [ ] **Step 2: Add the minimal RED workflow and verify failure**

Create `.github/workflows/gp12-turnover-formal-v1.yml` with a `contracts` job that checks out the branch, installs `requests`, sets `PYTHONPATH=scripts`, and runs:

```bash
cd scripts
python -m unittest -v test_gp12_sina_share_amount_v1.py
```

Expected: RED because `gp12_sina_share_amount_v1` does not exist.

- [ ] **Step 3: Implement the minimal parser and resolver**

Implement strict JSONP extraction without `eval`; accepted decoded rows must have canonical ISO dates, finite positive numeric values, sorted unique dates, and no date later than `2026-04-17` in the Formal manifest path. Compute raw-response SHA256 from exact bytes before decoding.

Implement `resolve_share_state` with `bisect` or an equivalent deterministic latest-`<=` lookup. Do not backfill future records.

`build_share_manifest` must emit sorted unique blockers, source identities, `formal_admission=false`, `model_freeze_allowed=false`, and `oos_metrics_allowed=false`. `date_semantics_evidence is None` must retain `SINA_SHARE_DATE_SEMANTICS_UNVERIFIED`.

- [ ] **Step 4: Run Task 1 tests and verify GREEN**

Run:

```bash
cd scripts
python -m unittest -v test_gp12_sina_share_amount_v1.py
```

Expected: all Task 1 tests PASS.

- [ ] **Step 5: Commit Task 1**

Commit message:

```text
test/feat(gp12): add Sina share-amount PIT evidence layer
```

---

### Task 2: Signed RAW volume binding and Formal turnover materialization

**Files:**
- Create: `scripts/gp12_turnover_formal_v1.py`
- Create: `scripts/test_gp12_turnover_formal_v1.py`
- Modify: `.github/workflows/gp12-turnover-formal-v1.yml`

**Interfaces:**
- Consumes: normalized signed RAW rows, frozen universe ordering, share manifest/normalized share records, candidate/formal identities.
- Produces:
  - `canonical_json_bytes(value) -> bytes`
  - `canonical_json_sha256(value) -> str`
  - `canonical_turnover_csv_bytes(rows: list[dict]) -> bytes`
  - `materialize_turnover(raw_rows: list[dict], share_records_by_symbol: dict[str,list[dict]], universe: list[str], share_manifest: dict, *, share_date_semantics_verified: bool) -> tuple[list[dict], dict]`
  - summary artifact `GP12_TURNOVER_FORMAL_V1`.

- [ ] **Step 1: Write RED materialization tests**

Add tests asserting:

```python
class TurnoverFormalV1Tests(unittest.TestCase):
    def test_exact_ratio_uses_raw_volume_shares(self):
        rows, summary = mod.materialize_turnover(
            raw_rows=[{'symbol':'600000.SH','date':'2020-06-01','volume':1_000_000.0}],
            share_records_by_symbol={'600000.SH':[{'record_date':'2020-01-01','outstanding_share_shares':100_000_000.0,'share_raw_sha256':'a'*64}]},
            universe=['600000.SH'],
            share_manifest=synthetic_manifest(),
            share_date_semantics_verified=True,
        )
        self.assertEqual(rows[0]['turnover_ratio'], 0.01)

    def test_future_share_record_never_materializes_prior_trade_row(self):
        ...
        self.assertIn('TURNOVER_PRIOR_SHARE_RECORD_MISSING', summary['blockers'])

    def test_rowset_mismatch_blocks(self):
        ...
        self.assertIn('TURNOVER_ROWSET_MISMATCH', summary['blockers'])

    def test_pit_unverified_cannot_pass_even_with_complete_rows(self):
        ...
        self.assertEqual(summary['status'], 'BLOCKED_FORMAL_TURNOVER_V1')
        self.assertEqual(summary['pit_state'], 'PIT_UNVERIFIED')

    def test_full_synthetic_pass(self):
        ...
        self.assertEqual(summary['status'], 'PASS_FORMAL_TURNOVER_V1')
        self.assertTrue(summary['formal_feature_ready'])
```

Also test duplicate RAW keys, nonpositive volume, nonpositive outstanding shares, nonfinite ratios, post-Formal dates, exact universe count/hash helper behavior, deterministic universe/date ordering, CSV newline/header convention, and distinct manifest/row/summary hashes.

- [ ] **Step 2: Run RED and verify only materializer functionality is missing**

Run:

```bash
cd scripts
python -m unittest -v test_gp12_sina_share_amount_v1.py test_gp12_turnover_formal_v1.py
```

Expected: Task 1 tests remain PASS; Task 2 tests fail because `gp12_turnover_formal_v1` is absent/incomplete.

- [ ] **Step 3: Implement minimal turnover materializer**

Validate RAW identity against:

```python
RAW_ARTIFACT_NAME = 'gp-sohu-full-raw-v482-reaudit'
RAW_ARTIFACT_SHA256 = 'cee7e91f1fda605f7c3bdf41c3f4a7796feeae83f8c3702e50900e6af3fa9550'
EXPECTED_TRADE_ROWS = 1_011_607
FORMAL_START = '2020-06-01'
FORMAL_END = '2026-04-17'
```

Treat input `volume` as shares and reject a separate/ambiguous lot-unit declaration. Resolve outstanding shares using Task 1 only. The row artifact carries `share_record_date` and `share_raw_sha256` for traceability.

The summary must never pass unless row keys equal the signed RAW key set exactly, source-date semantics are verified, and all required identity/count/quality invariants are zero-violation.

- [ ] **Step 4: Run Task 1+2 tests and verify GREEN**

Run the same unittest command and require all PASS.

- [ ] **Step 5: Commit Task 2**

Commit message:

```text
feat(gp12): materialize Formal turnover from signed RAW volume
```

---

### Task 3: Readiness binder that may change only `amount_turnover`

**Files:**
- Create: `scripts/gp12_turnover_readiness_bind_v1.py`
- Create: `scripts/test_gp12_turnover_readiness_bind_v1.py`
- Modify: `.github/workflows/gp12-turnover-formal-v1.yml`

**Interfaces:**
- Consumes: parent `GP12_FORMAL_INPUT_EVIDENCE_V1.json`, turnover summary, turnover summary canonical SHA.
- Produces:
  - `bind_turnover(parent_evidence: dict, turnover_summary: dict) -> dict`
  - derived Formal input evidence object that changes only `feature_families.amount_turnover` on full PASS.

- [ ] **Step 1: Write RED binder tests**

Required assertions:

```python
class TurnoverReadinessBindV1Tests(unittest.TestCase):
    def test_blocked_turnover_does_not_modify_parent_evidence(self):
        out = mod.bind_turnover(parent_evidence(), blocked_turnover())
        self.assertEqual(out, parent_evidence())

    def test_pass_changes_only_amount_turnover(self):
        before = parent_evidence()
        after = mod.bind_turnover(before, passing_turnover())
        self.assertEqual(after['feature_families']['main_net_flow'], before['feature_families']['main_net_flow'])
        self.assertEqual(after['feature_families']['stock_adjusted_close'], before['feature_families']['stock_adjusted_close'])
        self.assertEqual(after['feature_families']['amount_turnover']['binding_state'], 'BOUND_VERIFIED_ARTIFACT')
        self.assertEqual(after['feature_families']['amount_turnover']['pit_state'], 'PIT_VERIFIED')
        self.assertEqual(after['feature_families']['amount_turnover']['blockers'], [])

    def test_main_net_flow_blocker_remains(self):
        readiness = readiness_mod.build_readiness(
            mod.bind_turnover(parent_evidence(), passing_turnover()),
            candidate_parameters(),
            candidate_factors(),
        )
        self.assertIn('MAIN_NET_FLOW_UNBOUND', readiness['blockers'])
        self.assertIn('F11', readiness['blocked_factor_ids'])
        self.assertFalse(readiness['candidate_scoring_ready'])
```

Also assert that turnover summary identity mismatch, non-PASS status, non-`PIT_VERIFIED`, or `formal_feature_ready=false` cannot modify parent evidence.

- [ ] **Step 2: Run RED**

Run:

```bash
cd scripts
python -m unittest -v \
  test_gp12_sina_share_amount_v1.py \
  test_gp12_turnover_formal_v1.py \
  test_gp12_turnover_readiness_bind_v1.py \
  test_gp12_formal_input_readiness_v1.py
```

Expected: prior tasks PASS; binder tests fail because binder does not exist.

- [ ] **Step 3: Implement minimal binder**

Deep-copy parent evidence. On non-PASS, return a semantic copy unchanged. On exact PASS, update only:

```python
feature_families['amount_turnover'] = {
    'binding_state': 'BOUND_VERIFIED_ARTIFACT',
    'pit_state': 'PIT_VERIFIED',
    'source_artifact': 'GP12_TURNOVER_FORMAL_V1',
    'source_sha256': canonical_json_sha256(turnover_summary),
    'coverage_start': '2020-06-01',
    'coverage_end': '2026-04-17',
    'blockers': [],
}
```

Immediately rerun `gp12_formal_input_readiness_v1` validation in tests. Do not alter factor definitions, candidate package, main-flow family, adjusted-close family, status, labels, or any OOS/freeze flag.

- [ ] **Step 4: Run binder/readiness tests and verify GREEN**

Require all tests in the Step 2 command PASS.

- [ ] **Step 5: Commit Task 3**

Commit message:

```text
feat(gp12): bind verified turnover into Formal readiness
```

---

### Task 4: Production probe, date-semantics evidence, and 847-symbol collector workflow

**Files:**
- Modify: `.github/workflows/gp12-turnover-formal-v1.yml`
- Modify: `scripts/gp12_sina_share_amount_v1.py`
- Modify: `scripts/test_gp12_sina_share_amount_v1.py`

**Interfaces:**
- Consumes: Sina source endpoint, frozen universe file/artifact, explicit share-date-semantics evidence.
- Produces: single-symbol probe JSON; `SINA_SHARE_AMOUNT_MANIFEST_GP12_V1.json`; normalized per-symbol share rows/raw-response hashes.

- [ ] **Step 1: Add RED tests for production evidence semantics**

Add tests that require `share_date_semantics_evidence` to contain a strict object with:

```python
{
  'source': 'SINA_STOCK_STRUCTURE_HISTORY',
  'evidence_type': 'EFFECTIVE_HISTORICAL_SHARE_STATE',
  'verified': True,
  'source_identity': '<nonempty stable description>',
}
```

Unknown/missing keys, `verified=false`, or generic AKShare behavior must retain `SINA_SHARE_DATE_SEMANTICS_UNVERIFIED`.

- [ ] **Step 2: Implement semantics-evidence validator and rerun unit tests**

Keep the validator isolated from HTTP parsing. A structurally valid share payload plus invalid semantics evidence is still BLOCKED.

- [ ] **Step 3: Add `probe` job**

The workflow `probe` job must:

1. fetch one liquid long-lived symbol, `600000.SH`;
2. save exact raw bytes as an artifact file;
3. print HTTP status, byte length, raw SHA256, decoded record count/date range;
4. never print/compute any factor or performance metric;
5. emit `SINA_SHARE_SOURCE_UNAVAILABLE` or `SINA_SHARE_PAYLOAD_INVALID` as a known blocked terminal state rather than failing the workflow.

- [ ] **Step 4: Add `collect` job gated on structurally valid probe**

The collector reads the frozen 847-symbol universe, uses conservative low concurrency/retries/backoff, and emits one symbol-evidence record per frozen symbol. Source failures remain explicit; no alternate provider fallback is allowed.

The collect job may be workflow-SUCCESS with `MODEL/DATA GATE = BLOCKED`; this distinction must be printed in the log.

- [ ] **Step 5: Run production probe first and inspect raw output before full collection**

If the probe is unavailable/malformed, do not run 847 collection. Record the exact source blocker and stop this production path fail-closed.

If the probe is structurally valid but date semantics remain unverified, collection may proceed only if useful for structural coverage diagnostics; readiness still cannot pass.

- [ ] **Step 6: Commit Task 4**

Commit message:

```text
ci(gp12): add fail-closed Sina share-amount production probe
```

---

### Task 5: Bind signed RAW artifact, run production turnover audit, and publish terminal artifact

**Files:**
- Modify: `.github/workflows/gp12-turnover-formal-v1.yml`
- Modify: `scripts/gp12_turnover_formal_v1.py`
- Create or modify: `docs/gp12-turnover-formal-v1.md` only after real production output exists

**Interfaces:**
- Consumes: signed RAW workflow artifact, `SINA_SHARE_AMOUNT_MANIFEST_GP12_V1`, normalized share records, parent GP12 Formal input evidence.
- Produces: `GP12_TURNOVER_FORMAL_V1.json`, deterministic turnover CSV, hash manifest, optional derived GP12 readiness evidence, workflow artifact `gp12-turnover-formal-v1`.

- [ ] **Step 1: Add production CLI tests RED**

Require `gp12_turnover_formal_v1.py` CLI arguments for:

```text
--raw-dir
--share-manifest
--share-records-dir
--universe
--calendar
--candidate-parameters
--candidate-factors
--out-dir
```

Test that invalid source identity, post-Formal data, row mismatch, or PIT-unverified share semantics yields a BLOCKED summary; malformed schema/programmer errors exit nonzero.

- [ ] **Step 2: Implement CLI and deterministic outputs**

Write:

```text
GP12_TURNOVER_FORMAL_V1.json
GP12_TURNOVER_FORMAL_V1.csv
GP12_TURNOVER_FORMAL_V1.hashes.json
```

`hashes.json` must distinguish summary semantic SHA, turnover CSV SHA, share-manifest SHA, and any downloaded source artifact/ZIP digest.

- [ ] **Step 3: Add production audit job**

Download/revalidate the signed RAW artifact used by the parent readiness chain. Assert exact artifact identity and existing RAW invariants before reading volume rows.

Run materialization only inside the Formal boundary and frozen 847-symbol universe.

- [ ] **Step 4: Add conditional readiness bind job**

If and only if turnover status is `PASS_FORMAL_TURNOVER_V1`, bind `amount_turnover`, rerun existing readiness validator, and assert:

```python
assert 'TURNOVER_RATIO_UNBOUND' not in readiness['blockers']
assert 'MAIN_NET_FLOW_UNBOUND' in readiness['blockers']
assert 'F11' in readiness['blocked_factor_ids']
assert readiness['candidate_scoring_ready'] is False
assert readiness['candidate_freeze_ready'] is False
assert readiness['model_freeze_allowed'] is False
assert readiness['oos_metrics_allowed'] is False
```

If turnover is BLOCKED, upload the BLOCKED summary/manifest and do not modify parent readiness evidence.

- [ ] **Step 5: Run full regressions**

Run at minimum:

```bash
cd scripts
python -m unittest -v \
  test_gp12_sina_share_amount_v1.py \
  test_gp12_turnover_formal_v1.py \
  test_gp12_turnover_readiness_bind_v1.py \
  test_gp12_formal_input_readiness_v1.py \
  test_gp12_formal_input_readiness_production_v1.py \
  test_gp12_candidate_v1.py \
  test_oos_admission_v482.py \
  test_formal_readiness_v482.py \
  test_formal_readiness_finalize_v482.py
```

Expected: all PASS. No regression may change historical GP V1.1 blockers, candidate adoption status, Model Freeze state, or OOS state.

- [ ] **Step 6: Verify production artifact against the 95%-confidence project rule**

Before claiming PASS/BLOCKED, perform the project response-quality reverse check:

1. Assume the terminal state is wrong.
2. Re-check source identity, RAW unit, row-key equality, share-record date choice, PIT semantics evidence, Formal boundary, and artifact hashes from fresh run output.
3. Distinguish workflow SUCCESS from data-gate PASS.
4. If any material uncertainty remains, report BLOCKED/uncertain rather than promote readiness.

- [ ] **Step 7: Write observed-state documentation only from fresh evidence**

Create/update `docs/gp12-turnover-formal-v1.md` with actual run ID, terminal status, blockers, source coverage, row counts, hashes, and explicit statement that closing turnover alone does not make F11 or GP12 scoring-ready.

- [ ] **Step 8: Commit Task 5**

Commit message:

```text
ci/docs(gp12): finalize Formal turnover evidence gate
```

---

## Plan Self-Review

- Spec coverage: Tasks 1-5 cover source parsing/provenance, PIT semantics, exact RAW-volume binding, materialization, hashes, pass/block states, readiness integration, production workflow, OOS/freeze safety, and required regressions.
- Placeholder scan: no implementation step depends on `TBD`, `TODO`, or an undefined function. Ellipses above appear only inside illustrative unittest snippets whose complete required assertions are spelled out in the surrounding step; implementers must write concrete fixtures before running the RED test.
- Type consistency: Task 1 produces normalized share records consumed by Task 2; Task 2 produces turnover summary consumed by Task 3/5; Task 3 returns the same parent evidence schema consumed by the existing readiness validator.
- Reverse-check focus: the plan explicitly tests the three most likely false-positive routes—volume unit mismatch, future-capital backfill, and HTTP/structural success being mistaken for PIT readiness.
