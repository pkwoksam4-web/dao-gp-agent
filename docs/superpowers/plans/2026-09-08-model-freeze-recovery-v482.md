# Model Freeze Recovery V4.82 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fail-closed recovery and promotion layer that materializes every provable V4.82 model-freeze input, freezes the OOS date intent before exposure, and refuses to generate `MODEL_FREEZE_V482` until genuine GP strategy code, parameter, and factor-definition assets exist.

**Architecture:** Add one standard-library Python module with four isolated responsibilities: canonical evidence hashing, recovery checkpoint evaluation, model-freeze promotion, and OOS scope intent/final-scope promotion. Production CI consumes the already closed Formal artifact plus repository universe/calendar evidence, emits a recovery checkpoint, validates a committed scope-intent artifact, and stays operationally green while model promotion remains blocked. Existing Formal and OOS Admission code is unchanged.

**Tech Stack:** Python 3.12 standard library (`argparse`, `base64`, `csv`, `datetime`, `gzip`, `hashlib`, `io`, `json`, `pathlib`, `re`, `unittest`) and GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-08-model-freeze-recovery-v482-design.md`

## Global Constraints

- Version is exactly `V4.82`.
- Formal window is exactly `2020-06-01` through `2026-04-17` inclusive.
- Frozen universe contains exactly 847 unique symbols in source order.
- Liquidity threshold is exactly CNY `80_000_000`.
- Existing OOS Admission and Formal source files are not modified.
- Existing Formal remains `oos_metrics_allowed = false`.
- Scope intent is exactly `2026-04-18` through `2026-09-08` and is frozen before any OOS metric is read.
- Scope intent uses `pre_exposure_confirmed = true`; it contains no OOS performance/metric fields.
- Existing V3.57 calendar evidence may prove the Formal calendar but must not be assumed to cover OOS through `2026-09-08`.
- Missing scorer, parameter set, or factor-definition bytes are validation blockers and must never be replaced by inferred hashes.
- No third-party Python dependencies.
- Production may emit `MODEL_ASSETS_INCOMPLETE_V482` and still exit successfully; unexpected programmer/runtime errors exit non-zero.

---

## File Structure

- Create `scripts/model_freeze_recovery_v482.py` — evidence parsing/hashing, recovery checkpoint, model promotion, scope-intent validation, final-scope promotion, CLI.
- Create `scripts/test_model_freeze_recovery_v482.py` — synthetic and repository-fixture TDD contract.
- Create `data/OOS_SCOPE_INTENT_V482.json` — immutable pre-exposure OOS date intent.
- Create `.github/workflows/model-freeze-recovery-v482.yml` — tests, real Formal artifact recovery run, checkpoint/scope-intent artifact upload.
- Do not create production `data/MODEL_FREEZE_V482.json` while strategy-side blockers exist.
- Do not create production `data/OOS_SCOPE_V482.json` until a genuine model freeze and OOS-capable calendar are available.

### Task 1: RED contract for evidence recovery

**Files:**
- Create: `scripts/test_model_freeze_recovery_v482.py`
- Create: `.github/workflows/model-freeze-recovery-v482.yml`

**Interfaces:**
- Consumes: repository fixture bytes and synthetic dictionaries.
- Produces test contract for `canonical_json_sha256`, `canonical_universe`, `decode_calendar_representations`, `recover_checkpoint`, `validate_scope_intent`, `promote_model_freeze`, and `promote_oos_scope`.

- [ ] **Step 1: Write failing unit tests**

Create tests that deliberately import the nonexistent module:

```python
import model_freeze_recovery_v482 as mod
```

Fixture helper:

```python
def valid_formal():
    return {
        'artifact':'FORMAL_READINESS_FINAL_V482',
        'version':'V4.82',
        'formal_ready':True,
        'oos_metrics_allowed':False,
        'universe_n':847,
        'formal_symbol_n':844,
        'market_data':{
            'market_data_ready':True,
            'liquidity_threshold_cny':80_000_000,
        },
    }
```

Add explicit tests for:

1. canonical JSON hashing stability across key order/whitespace;
2. universe canonicalization strips only transport trailing newline and preserves source ordering;
3. 846/848 symbols, duplicates, blanks, or reordered expected fixture are invalid;
4. `.b64` and `.hex` representations decode to identical gzip bytes;
5. representation mismatch is blocked;
6. Formal-date extraction returns exactly requested range and rejects malformed/non-increasing dates;
7. recovery checkpoint with no strategy assets emits all three missing strategy blockers and `model_freeze_allowed=false`;
8. invalid liquidity rule blocks;
9. real/provided strategy bytes + parameter JSON + factor-definition JSON clear corresponding blockers;
10. incomplete checkpoint cannot promote model freeze;
11. synthetic complete checkpoint with valid OOS-capable calendar hash promotes exact Admission-compatible model schema;
12. exact scope intent passes;
13. changed start/end or `pre_exposure_confirmed=false` fails;
14. recursive forbidden metric field fails;
15. final scope promotion inherits dates exactly and rejects mutation;
16. calendar coverage ending before `2026-09-08` emits `OOS_CALENDAR_COVERAGE_MISSING`.

- [ ] **Step 2: Add RED-only workflow**

Create `.github/workflows/model-freeze-recovery-v482.yml` initially with:

```yaml
name: GP V4.82 Model Freeze Recovery

on:
  push:
    branches: [gp/model-freeze-recovery-v482]
    paths:
      - 'scripts/model_freeze_recovery_v482.py'
      - 'scripts/test_model_freeze_recovery_v482.py'
      - 'data/OOS_SCOPE_INTENT_V482.json'
      - '.github/workflows/model-freeze-recovery-v482.yml'
      - 'docs/superpowers/specs/2026-09-08-model-freeze-recovery-v482-design.md'
      - 'docs/superpowers/plans/2026-09-08-model-freeze-recovery-v482.md'
  workflow_dispatch:

permissions:
  contents: read
  actions: read

jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Model freeze recovery tests
        env:
          PYTHONPATH: scripts
        run: |
          cd scripts
          python -m unittest -v test_model_freeze_recovery_v482.py
```

- [ ] **Step 3: Verify RED in GitHub Actions**

Expected failure:

```text
ModuleNotFoundError: No module named 'model_freeze_recovery_v482'
```

- [ ] **Step 4: Commit RED state**

```bash
git add scripts/test_model_freeze_recovery_v482.py .github/workflows/model-freeze-recovery-v482.yml
git commit -m "test(v482): define RED model freeze recovery contract"
```

### Task 2: Canonical evidence recovery and checkpoint evaluator

**Files:**
- Create: `scripts/model_freeze_recovery_v482.py`
- Test: `scripts/test_model_freeze_recovery_v482.py`

**Interfaces:**
- Produces:
  - `canonical_json_sha256(obj: object) -> str`
  - `canonical_universe(text: str, expected_count: int = 847) -> tuple[list[str], str]`
  - `decode_calendar_representations(b64_text: str, hex_text: str) -> bytes`
  - `parse_calendar_dates(gzip_bytes: bytes) -> list[str]`
  - `calendar_range_sha256(dates: list[str], start: str, end: str) -> tuple[list[str], str]`
  - `recover_checkpoint(...) -> dict`

- [ ] **Step 1: Implement canonical JSON and universe functions**

Canonical JSON:

```python
def canonical_json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def canonical_json_sha256(obj):
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()
```

Universe:

```python
def canonical_universe(text, expected_count=847):
    raw_lines=text.splitlines()
    lines=[line.strip() for line in raw_lines]
    if any(not line for line in lines):
        raise ValueError('blank universe symbol')
    if len(lines)!=expected_count:
        raise ValueError('universe count mismatch')
    if len(set(lines))!=len(lines):
        raise ValueError('duplicate universe symbol')
    payload='\n'.join(lines).encode('utf-8')
    return lines, hashlib.sha256(payload).hexdigest()
```

Do not sort symbols.

- [ ] **Step 2: Implement dual calendar decoding**

```python
def decode_calendar_representations(b64_text, hex_text):
    b64_payload=base64.b64decode(''.join(b64_text.split()), validate=True)
    hex_payload=bytes.fromhex(''.join(hex_text.split()))
    if b64_payload != hex_payload:
        raise ValueError('calendar representation mismatch')
    return b64_payload
```

Then gzip-decompress and parse CSV dates. Accept a header only if it is non-date text; every parsed date must be ISO `YYYY-MM-DD`, strictly increasing, and unique.

- [ ] **Step 3: Implement exact Formal-range hashing and OOS coverage inspection**

`calendar_range_sha256` must select every decoded date `start <= d <= end`, require first selected date equals `start` if `start` is an open date and last selected date equals `end` if `end` is an open date only when those exact dates exist in decoded evidence, and always require a non-empty strictly increasing range. The canonical hash is newline-joined selected dates with no trailing newline.

Recovery checkpoint records decoded calendar min/max and emits `OOS_CALENDAR_COVERAGE_MISSING` when the maximum decoded date is earlier than `2026-09-08`.

- [ ] **Step 4: Implement recovery checkpoint**

Signature:

```python
def recover_checkpoint(
    formal: dict,
    universe_text: str,
    calendar_b64_text: str,
    calendar_hex_text: str,
    strategy_code_bytes: bytes | None = None,
    parameters: dict | None = None,
    factor_definition: dict | None = None,
) -> dict:
```

The checkpoint must produce deterministic sorted blockers. Strategy asset rules:

```python
strategy_code_sha256 = hashlib.sha256(strategy_code_bytes).hexdigest() if strategy_code_bytes else None
parameter_sha256 = canonical_json_sha256(parameters) if isinstance(parameters, dict) else None
factor_definition_sha256 = canonical_json_sha256(factor_definition) if isinstance(factor_definition, dict) else None
```

Missing values emit:

```text
STRATEGY_CODE_MISSING
PARAMETER_SET_MISSING
FACTOR_DEFINITION_MISSING
```

Malformed supplied values emit the corresponding `*_INVALID` blocker rather than `*_MISSING`.

`model_freeze_allowed` is true only when no blocker remains except no blocker is ever ignored. Because Formal-only calendar coverage may be insufficient for OOS, `OOS_CALENDAR_COVERAGE_MISSING` also keeps promotion closed.

- [ ] **Step 5: Run tests and commit GREEN checkpoint evaluator**

```bash
cd scripts
python -m unittest -v test_model_freeze_recovery_v482.py
```

Expected: evidence/checkpoint tests pass.

Commit:

```bash
git add scripts/model_freeze_recovery_v482.py scripts/test_model_freeze_recovery_v482.py
git commit -m "feat(v482): recover canonical model freeze evidence"
```

### Task 3: Freeze and validate OOS scope intent

**Files:**
- Create: `data/OOS_SCOPE_INTENT_V482.json`
- Modify: `scripts/model_freeze_recovery_v482.py`
- Modify: `scripts/test_model_freeze_recovery_v482.py`

**Interfaces:**
- Produces `validate_scope_intent(scope: dict) -> list[str]`.

- [ ] **Step 1: Commit the exact pre-exposure intent object**

Create exactly:

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

- [ ] **Step 2: Implement strict scope-intent validation**

Exact top-level key set is required. Recursive reserved metric keys are rejected case-insensitively:

```python
RESERVED={'return','returns','pnl','alpha','sharpe','drawdown','hit_rate','win_rate','performance','metrics','signal_result','signal_results'}
```

Require exact date values from the committed V4.82 intent; no `today`, rolling, or inferred dates.

- [ ] **Step 3: Run scope tests and commit**

```bash
cd scripts
python -m unittest -v test_model_freeze_recovery_v482.py
```

Commit:

```bash
git add data/OOS_SCOPE_INTENT_V482.json scripts/model_freeze_recovery_v482.py scripts/test_model_freeze_recovery_v482.py
git commit -m "data(v482): freeze pre-exposure OOS scope intent"
```

### Task 4: Model-freeze and final-scope promotion functions

**Files:**
- Modify: `scripts/model_freeze_recovery_v482.py`
- Modify: `scripts/test_model_freeze_recovery_v482.py`

**Interfaces:**
- Produces:
  - `promote_model_freeze(checkpoint: dict, strategy_id: str, calendar_sha256: str) -> dict`
  - `promote_oos_scope(intent: dict, model_freeze: dict, calendar_sha256: str) -> dict`

- [ ] **Step 1: Write/verify failing promotion tests**

Tests must require:

```python
with self.assertRaises(ValueError):
    mod.promote_model_freeze(incomplete_checkpoint, 'GP_V11', 'a'*64)
```

and prove a synthetic complete checkpoint produces exactly the OOS Admission model schema.

- [ ] **Step 2: Implement model-freeze promotion**

Promotion requires checkpoint:

```text
artifact == MODEL_ASSET_RECOVERY_CHECKPOINT_V482
version == V4.82
status == MODEL_ASSETS_COMPLETE_V482
model_freeze_allowed == true
blockers == []
```

`calendar_sha256` must be valid lowercase 64-hex and represents an OOS-capable frozen calendar supplied only after coverage is independently proven. It must not automatically copy `formal_calendar_sha256`.

- [ ] **Step 3: Implement final-scope promotion**

`promote_oos_scope` validates the intent, requires a schema-valid frozen model, and emits exactly:

```json
{
  "artifact":"OOS_SCOPE_V482",
  "version":"V4.82",
  "formal_end":"2026-04-17",
  "oos_start":"2026-04-18",
  "oos_end":"2026-09-08",
  "calendar_sha256":"<64 hex>",
  "universe_sha256":"<model value>",
  "model_freeze_sha256":"<canonical model JSON hash>",
  "scope_frozen":true
}
```

The three dates are copied, never accepted as promotion arguments.

- [ ] **Step 4: Run tests and commit**

```bash
cd scripts
python -m unittest -v test_model_freeze_recovery_v482.py
```

Commit:

```bash
git add scripts/model_freeze_recovery_v482.py scripts/test_model_freeze_recovery_v482.py
git commit -m "feat(v482): gate model and OOS scope promotion"
```

### Task 5: CLI and real production recovery workflow

**Files:**
- Modify: `scripts/model_freeze_recovery_v482.py`
- Modify: `.github/workflows/model-freeze-recovery-v482.yml`
- Test: `scripts/test_model_freeze_recovery_v482.py`

**Interfaces:**
- CLI consumes `--formal`, `--universe`, `--calendar-b64`, `--calendar-hex`, `--scope-intent`, `--out-dir`.
- Optional future strategy flags: `--strategy-code`, `--parameters`, `--factor-definition`.
- Produces `MODEL_ASSET_RECOVERY_CHECKPOINT_V482.json` and `OOS_SCOPE_INTENT_VALIDATION_V482.json`.

- [ ] **Step 1: Add CLI path tests**

Known missing optional strategy assets must produce an incomplete checkpoint, not a process failure. Missing/malformed required Formal/universe/calendar/scope-intent input is a deterministic blocked checkpoint/validation artifact when possible; unexpected internal exceptions remain non-zero.

- [ ] **Step 2: Implement CLI**

Write output directory files:

```text
MODEL_ASSET_RECOVERY_CHECKPOINT_V482.json
OOS_SCOPE_INTENT_VALIDATION_V482.json
```

Scope validation artifact:

```json
{
  "artifact":"OOS_SCOPE_INTENT_VALIDATION_V482",
  "version":"V4.82",
  "status":"SCOPE_INTENT_VALID_V482",
  "blockers":[],
  "scope_intent_sha256":"<canonical hash>"
}
```

or `SCOPE_INTENT_INVALID_V482` with blockers.

- [ ] **Step 3: Extend workflow to real Formal evidence**

After test job, production job downloads the same closed Formal artifact used by OOS Admission:

```yaml
      - uses: actions/download-artifact@v4
        with:
          name: gp-formal-readiness-final-v482
          path: formal
          run-id: 34192462041
          github-token: ${{ github.token }}
```

Then:

```yaml
      - name: Recover model-freeze evidence
        env:
          PYTHONPATH: scripts
        run: |
          python scripts/model_freeze_recovery_v482.py \
            --formal formal/FORMAL_READINESS_FINAL_V482.json \
            --universe data/pit_st_scope_v480.txt \
            --calendar-b64 data/OFFICIAL_A_SHARE_OPEN_DATES_V357.csv.gz.b64 \
            --calendar-hex data/OFFICIAL_A_SHARE_OPEN_DATES_V357.csv.gz.hex \
            --scope-intent data/OOS_SCOPE_INTENT_V482.json \
            --out-dir artifact_model_freeze_recovery_v482
```

No strategy arguments are supplied until genuine files are recovered.

- [ ] **Step 4: Assert production remains truthful**

Require checkpoint:

```text
formal artifact recoverable == true
universe recoverable == true
formal calendar recoverable == true
liquidity rule recoverable == true
STRATEGY_CODE_MISSING present
PARAMETER_SET_MISSING present
FACTOR_DEFINITION_MISSING present
model_freeze_allowed == false
```

Do not assert `OOS_CALENDAR_COVERAGE_MISSING` either way before the real decoded maximum date is observed; log the decoded calendar end and let evidence decide.

Also require scope-intent validation status `SCOPE_INTENT_VALID_V482`.

- [ ] **Step 5: Upload artifact**

```yaml
      - uses: actions/upload-artifact@v4
        with:
          name: gp-model-freeze-recovery-v482
          path: artifact_model_freeze_recovery_v482/
          if-no-files-found: error
          retention-days: 30
```

- [ ] **Step 6: Run final workflow and capture real hashes**

Record from artifact/logs:

- canonical Formal SHA256;
- canonical 847-universe SHA256;
- canonical Formal-calendar SHA256;
- decoded calendar minimum/maximum and Formal date count;
- scope-intent SHA256;
- exact remaining blockers.

### Task 6: Regression and boundary verification

**Files:**
- Verify only.

**Interfaces:**
- Confirms recovery subsystem did not weaken Admission/Formal or fabricate production model artifacts.

- [ ] **Step 1: Run fresh recovery suite**

```bash
cd scripts
python -m unittest -v test_model_freeze_recovery_v482.py
```

- [ ] **Step 2: Run existing OOS Admission and Formal regression suites**

```bash
cd scripts
python -m unittest -v \
  test_oos_admission_v482.py \
  test_formal_readiness_v482.py \
  test_formal_readiness_finalize_v482.py
```

- [ ] **Step 3: Verify no production model/final scope was fabricated**

```bash
test ! -e data/MODEL_FREEZE_V482.json
test ! -e data/OOS_SCOPE_V482.json
```

- [ ] **Step 4: Compare branch boundaries**

Against `gp/oos-admission-v482`, expected additions are only recovery spec/plan, recovery script/test, scope intent, and recovery workflow. Existing Admission/ Formal/RAW/Liquidity production files must show no modifications.

## Self-Review Result

- Spec coverage: evidence recovery, canonical hashes, dual calendar representation, Formal/OOS calendar separation, strategy blockers, scope-intent freeze, model promotion, final scope promotion, CLI, CI, and regressions each have explicit tasks.
- Placeholder scan: no `TBD`, `TODO`, generic error-handling placeholder, or unspecified test step remains.
- Type consistency: `recover_checkpoint`, `validate_scope_intent`, `promote_model_freeze`, and `promote_oos_scope` signatures are used consistently across tasks.
- Safety: no production scorer/parameter/factor hash is invented; no production `MODEL_FREEZE_V482.json` or final `OOS_SCOPE_V482.json` is created while blockers remain.
