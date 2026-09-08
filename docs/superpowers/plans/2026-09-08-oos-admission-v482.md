# OOS Admission V4.82 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone, fail-closed OOS Admission V4.82 gate that cryptographically binds the completed Formal V4.82 artifact to a frozen model manifest and frozen OOS scope before any OOS metric can run.

**Architecture:** Keep `formal_readiness_v482.py` and `formal_readiness_finalize_v482.py` unchanged with `oos_metrics_allowed = false`. Add a separate pure-Python evaluator that validates Formal invariants, model/scope schemas, canonical SHA256 bindings, time-window isolation, and recursive no-metrics constraints, then emits exactly one decision artifact: admitted or blocked. Because the real GP scoring engine/parameter package is not currently present in this repository, production admission must remain blocked until genuine model assets are recovered; unit tests use synthetic fixtures to prove both ADMITTED and BLOCKED paths.

**Tech Stack:** Python 3.12 standard library (`argparse`, `datetime`, `hashlib`, `json`, `pathlib`, `re`, `unittest`) and GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-08-oos-admission-v482-design.md`

## Global Constraints

- Version is exactly `V4.82`.
- Formal period ends exactly `2026-04-17`; OOS must start strictly after that date.
- Formal checkpoint is exactly `{'PASS':844,'EXACT_TERM_REVIEW':0,'MISSING_EVENT_REVIEW':0,'NOT_APPLICABLE':3}`.
- Formal universe is 847 symbols; 844 are Formal-valid and the exact zero-trade/N/A partition is `600074.SH`, `600485.SH`, `600677.SH`.
- Full RAW rows are exactly `1_011_607`; missing/extra/duplicate trade-date counts are zero.
- Liquidity threshold is exactly CNY `80_000_000` and raw PIT/ST status is `PASS_EXACT_RAW_PITST`.
- `current_trade_violation_n == 0` and `st_overlay_violation_n == 0` are mandatory.
- Existing Formal finalizers must continue to emit `oos_metrics_allowed = false`.
- Admission must never read OOS prices, returns, PnL, signals, or performance summaries.
- Canonical JSON hashing is UTF-8, `sort_keys=True`, `separators=(',', ':')`, `ensure_ascii=False`, with no trailing newline.
- No third-party Python dependency is allowed.
- Missing real model assets are a production blocker, not a reason to invent hashes.

---

## File Structure

- Create `scripts/test_oos_admission_v482.py` — unit contract, fixture builders, all positive/fail-closed cases.
- Create `scripts/oos_admission_v482.py` — canonical hashing, schema validation, deterministic blocker collection, CLI, decision artifact writer.
- Create `.github/workflows/oos-admission-v482.yml` — RED/GREEN tests plus production gate run against the known Formal artifact; missing model/scope inputs produce BLOCKED, never ADMITTED.
- Do not modify `scripts/formal_readiness_v482.py`.
- Do not modify `scripts/formal_readiness_finalize_v482.py`.
- Do not create a fake `data/model_freeze_v482.json` or `data/oos_scope_v482.json`; those production manifests are only added when genuine model assets exist.

### Task 1: RED contract tests and CI harness

**Files:**
- Create: `scripts/test_oos_admission_v482.py`
- Create: `.github/workflows/oos-admission-v482.yml`

**Interfaces:**
- Consumes: no production module yet; imports `oos_admission_v482` deliberately fail in RED.
- Produces: fixture helpers `valid_formal() -> dict`, `valid_model(formal: dict) -> dict`, `valid_scope(model: dict) -> dict`, plus tests describing the gate API `canonical_sha256(obj) -> str` and `evaluate(formal, model, scope) -> dict`.

- [ ] **Step 1: Write the failing unit-test module**

Create `scripts/test_oos_admission_v482.py` with fixture builders that match the exact V4.82 invariants. The core fixture shape must include:

```python
import copy
import json
import unittest

import oos_admission_v482 as mod


def valid_formal():
    return {
        'artifact': 'FORMAL_READINESS_FINAL_V482',
        'version': 'V4.82',
        'checkpoint': {'PASS':844,'EXACT_TERM_REVIEW':0,'MISSING_EVENT_REVIEW':0,'NOT_APPLICABLE':3},
        'universe_n': 847,
        'formal_symbol_n': 844,
        'full_path_pass_n': 844,
        'full_path_fail_n': 0,
        'max_full_path_diff_bp': 0.0,
        'formal_ready': True,
        'validated_global_provenance_emitted': True,
        'oos_metrics_allowed': False,
        'na': {'count':3,'symbols':['600074.SH','600485.SH','600677.SH']},
        'special_provenance': {'materialized_n':11,'blocker_n':0},
        'market_data': {
            'market_data_ready': True,
            'symbol_n': 847,
            'raw_trade_rows': 1_011_607,
            'missing_trade_dates_n': 0,
            'extra_trade_dates_n': 0,
            'duplicate_symbol_dates': 0,
            'zero_trade_symbols': ['600074.SH','600485.SH','600677.SH'],
            'liquidity_threshold_cny': 80_000_000,
            'raw_pitst_status': 'PASS_EXACT_RAW_PITST',
            'current_trade_violation_n': 0,
            'st_overlay_violation_n': 0,
        },
    }


def valid_model(formal):
    return {
        'artifact':'MODEL_FREEZE_V482','version':'V4.82','strategy_id':'GP_V11_RECOVERED',
        'strategy_code_sha256':'1'*64,'parameter_sha256':'2'*64,'universe_sha256':'3'*64,
        'factor_definition_sha256':'4'*64,'calendar_sha256':'5'*64,
        'formal_artifact_sha256':mod.canonical_sha256(formal),
        'liquidity_threshold_cny':80_000_000,'formal_end':'2026-04-17','frozen':True,
    }


def valid_scope(model):
    return {
        'artifact':'OOS_SCOPE_V482','version':'V4.82','formal_end':'2026-04-17',
        'oos_start':'2026-04-18','oos_end':'2026-09-08',
        'calendar_sha256':model['calendar_sha256'],'universe_sha256':model['universe_sha256'],
        'model_freeze_sha256':mod.canonical_sha256(model),'scope_frozen':True,
    }
```

The class must include explicit tests for all 14 cases in the spec, including a nested forbidden metric field such as `scope['nested']={'metrics':{'sharpe':2.0}}` and a canonical-hash stability test using differently ordered dictionaries.

- [ ] **Step 2: Add a test-only GitHub Actions workflow and verify RED**

Create `.github/workflows/oos-admission-v482.yml` initially with a `tests` job only:

```yaml
name: GP V4.82 OOS Admission

on:
  push:
    branches: [gp/oos-admission-v482]
    paths:
      - 'scripts/oos_admission_v482.py'
      - 'scripts/test_oos_admission_v482.py'
      - '.github/workflows/oos-admission-v482.yml'
      - 'docs/superpowers/specs/2026-09-08-oos-admission-v482-design.md'
      - 'docs/superpowers/plans/2026-09-08-oos-admission-v482.md'
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
      - name: OOS admission contract tests
        env:
          PYTHONPATH: scripts
        run: |
          cd scripts
          python -m unittest -v test_oos_admission_v482.py
```

Expected RED: import failure `ModuleNotFoundError: No module named 'oos_admission_v482'`.

- [ ] **Step 3: Commit RED state**

```bash
git add scripts/test_oos_admission_v482.py .github/workflows/oos-admission-v482.yml
git commit -m "test(v482): define RED OOS admission contract"
```

### Task 2: Canonical hash and deterministic fail-closed evaluator

**Files:**
- Create: `scripts/oos_admission_v482.py`
- Test: `scripts/test_oos_admission_v482.py`

**Interfaces:**
- Consumes: three Python dictionaries: Formal artifact, model-freeze manifest, OOS-scope manifest.
- Produces: `canonical_sha256(obj: object) -> str`, `evaluate(formal: dict, model: dict, scope: dict) -> dict`.

- [ ] **Step 1: Implement canonical hashing and exact schema constants**

Use only standard library code:

```python
def canonical_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def canonical_sha256(obj):
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()
```

Define exact allowed-key sets for model and scope, exact required constants, `SHA_RE = re.compile(r'^[0-9a-f]{64}$')`, and `FORMAL_END = '2026-04-17'`.

- [ ] **Step 2: Implement recursive metric/unknown-field validation**

Implement a recursive walker that returns deterministic path strings. Reserved metric names must be compared case-insensitively at every dictionary depth. Model and scope top-level keys must match their exact allowlists; nested dictionaries are not part of the production schema, so any unknown top-level field is blocked before admission.

```python
RESERVED = {'return','returns','pnl','alpha','sharpe','drawdown','hit_rate','win_rate','performance','metrics'}


def find_forbidden_metric_paths(value, path='$'):
    hits=[]
    if isinstance(value, dict):
        for k,v in value.items():
            child=f'{path}.{k}'
            if str(k).lower() in RESERVED:
                hits.append(child)
            hits.extend(find_forbidden_metric_paths(v, child))
    elif isinstance(value, list):
        for i,v in enumerate(value):
            hits.extend(find_forbidden_metric_paths(v, f'{path}[{i}]'))
    return hits
```

- [ ] **Step 3: Implement the Formal lock**

Add a validator that returns blocker codes rather than warnings. It must verify every Global Constraint Formal invariant, including exact N/A symbols, exact zero-trade symbols, `current_trade_violation_n == 0`, `st_overlay_violation_n == 0`, and upstream `oos_metrics_allowed is False`.

- [ ] **Step 4: Implement model/scope validation and cross-hash binding**

The evaluator must:

```python
formal_sha = canonical_sha256(formal)
model_sha = canonical_sha256(model)
scope_sha = canonical_sha256(scope)
```

Then require:

```python
model['formal_artifact_sha256'] == formal_sha
scope['model_freeze_sha256'] == model_sha
scope['calendar_sha256'] == model['calendar_sha256']
scope['universe_sha256'] == model['universe_sha256']
scope['formal_end'] == model['formal_end'] == FORMAL_END
```

Parse dates with `datetime.date.fromisoformat` and require `oos_start > date(2026,4,17)` and `oos_end >= oos_start`.

- [ ] **Step 5: Implement exact terminal decisions**

When `blockers` is empty return:

```python
{
    'artifact':'OOS_ADMISSION_V482','version':'V4.82','status':'OOS_ADMITTED_V482',
    'formal_ready':True,'model_frozen':True,'oos_window_frozen':True,
    'data_isolation_pass':True,'formal_artifact_sha256':formal_sha,
    'model_freeze_sha256':model_sha,'oos_scope_sha256':scope_sha,
    'blockers':[],'oos_metrics_allowed':True,
}
```

Otherwise return `status='OOS_BLOCKED_V482'`, `oos_metrics_allowed=False`, and sorted unique blocker codes. Do not convert unexpected programmer errors into admission.

- [ ] **Step 6: Run unit tests and verify GREEN**

Run:

```bash
cd scripts
python -m unittest -v test_oos_admission_v482.py
```

Expected: all OOS admission tests PASS.

- [ ] **Step 7: Commit evaluator**

```bash
git add scripts/oos_admission_v482.py scripts/test_oos_admission_v482.py
git commit -m "feat(v482): add fail-closed OOS admission gate"
```

### Task 3: CLI, missing-input blocking, and artifact emission

**Files:**
- Modify: `scripts/oos_admission_v482.py`
- Modify: `scripts/test_oos_admission_v482.py`

**Interfaces:**
- Consumes filesystem paths `--formal`, `--model-freeze`, `--oos-scope`, `--out-dir`.
- Produces `OUT_DIR/OOS_ADMISSION_V482.json` and process exit code `0` for a deterministic decision artifact, including BLOCKED; malformed/unexpected execution failures exit non-zero.

- [ ] **Step 1: Add failing CLI tests**

Use `tempfile.TemporaryDirectory()` and call `mod.run_paths(...)` directly. Cover:

```python
def test_missing_model_file_emits_blocked(self):
    decision = mod.run_paths(formal_path, missing_model_path, scope_path)
    self.assertEqual(decision['status'], 'OOS_BLOCKED_V482')
    self.assertIn('MODEL_FREEZE_INVALID', decision['blockers'])
    self.assertFalse(decision['oos_metrics_allowed'])
```

Add the equivalent missing-scope case and malformed-JSON case. Missing required inputs are expected validation failures; unreadable/corrupt JSON maps to the corresponding deterministic blocker, never ADMITTED.

- [ ] **Step 2: Implement path loading and CLI**

Implement:

```python
def run_paths(formal_path: pathlib.Path, model_path: pathlib.Path, scope_path: pathlib.Path) -> dict:
    # Load each input independently. Known missing/invalid input becomes the matching blocker.
    # If a dict cannot be obtained, emit BLOCKED without attempting hashes for that object.
```

`main()` must always write `OOS_ADMISSION_V482.json` for known validation failures and print a compact JSON summary containing `status`, `blockers`, and `oos_metrics_allowed`.

- [ ] **Step 3: Run tests**

```bash
cd scripts
python -m unittest -v test_oos_admission_v482.py
```

Expected: PASS.

- [ ] **Step 4: Commit CLI**

```bash
git add scripts/oos_admission_v482.py scripts/test_oos_admission_v482.py
git commit -m "feat(v482): emit deterministic OOS admission artifacts"
```

### Task 4: Production workflow wired to real Formal evidence, intentionally blocked without real model freeze

**Files:**
- Modify: `.github/workflows/oos-admission-v482.yml`

**Interfaces:**
- Consumes real Formal artifact `gp-formal-readiness-final-v482` from successful workflow run `34192462041` / artifact `10042687724`.
- Consumes optional future repository files `data/model_freeze_v482.json` and `data/oos_scope_v482.json`; absence is passed through the evaluator and must produce BLOCKED.
- Produces artifact `gp-oos-admission-v482` containing only `OOS_ADMISSION_V482.json` and logs.

- [ ] **Step 1: Extend workflow after tests**

Add an `admission` job with `needs: tests`. Download the real Formal artifact:

```yaml
      - name: Download closed Formal V4.82 artifact
        uses: actions/download-artifact@v4
        with:
          name: gp-formal-readiness-final-v482
          path: formal
          run-id: 34192462041
          github-token: ${{ github.token }}
```

Then run:

```yaml
      - name: Evaluate OOS admission without exposing OOS metrics
        env:
          PYTHONPATH: scripts
        run: |
          python scripts/oos_admission_v482.py \
            --formal formal/FORMAL_READINESS_FINAL_V482.json \
            --model-freeze data/model_freeze_v482.json \
            --oos-scope data/oos_scope_v482.json \
            --out-dir artifact_oos_admission_v482
```

The initial production result is expected to be `OOS_BLOCKED_V482` with missing model/scope blocker(s), because genuine scoring assets have not been recovered.

- [ ] **Step 2: Assert workflow contains no OOS metric runner**

Add a shell/Python verification step that fails if the workflow text contains any invocation token matching known runner/metric commands (`run_gp_walkforward.py`, `backtest`, `sharpe`, `pnl`, `oos_metrics.py`). This check inspects workflow command lines; descriptive comments are excluded from the check.

- [ ] **Step 3: Upload the admission artifact**

```yaml
      - uses: actions/upload-artifact@v4
        with:
          name: gp-oos-admission-v482
          path: artifact_oos_admission_v482/
          if-no-files-found: error
          retention-days: 30
```

- [ ] **Step 4: Commit workflow**

```bash
git add .github/workflows/oos-admission-v482.yml
git commit -m "ci(v482): add isolated OOS admission workflow"
```

### Task 5: Regression, invariant proof, and completion gate

**Files:**
- Verify only; production Formal files remain unchanged.

**Interfaces:**
- Consumes completed branch state.
- Produces evidence that the new subsystem does not weaken any existing Formal gate.

- [ ] **Step 1: Run focused OOS tests**

```bash
cd scripts
python -m unittest -v test_oos_admission_v482.py
```

Expected: PASS.

- [ ] **Step 2: Run existing Formal finalizer regression tests**

```bash
cd scripts
python -m unittest -v test_formal_readiness_v482.py test_formal_readiness_finalize_v482.py
```

Expected: PASS.

- [ ] **Step 3: Verify Formal source remains OOS-closed**

Run:

```bash
grep -n "oos_metrics_allowed.*False" scripts/formal_readiness_v482.py scripts/formal_readiness_finalize_v482.py
```

Expected: both Formal paths still explicitly keep OOS closed.

- [ ] **Step 4: Verify no production manifest was fabricated**

Run:

```bash
test ! -e data/model_freeze_v482.json
test ! -e data/oos_scope_v482.json
```

Expected: both commands succeed until genuine GP scorer/parameter/factor-definition assets are recovered.

- [ ] **Step 5: Inspect the GitHub Actions run**

Expected final branch workflow result at this stage:

```json
{
  "artifact": "OOS_ADMISSION_V482",
  "version": "V4.82",
  "status": "OOS_BLOCKED_V482",
  "oos_metrics_allowed": false
}
```

The unit suite must separately prove that valid synthetic frozen inputs yield `OOS_ADMITTED_V482`; production remains blocked because the real model-freeze inputs are absent.

- [ ] **Step 6: Commit any verification-only corrections if needed**

```bash
git add scripts/oos_admission_v482.py scripts/test_oos_admission_v482.py .github/workflows/oos-admission-v482.yml
git commit -m "test(v482): close OOS admission regression proof"
```

## Self-Review Result

- Spec coverage: Formal lock, model freeze, OOS window, cross-artifact hashes, recursive no-metrics rule, canonical hashing, two terminal states, workflow isolation, and Formal regression are all assigned to explicit tasks.
- No-placeholder scan: no `TBD`, `TODO`, deferred implementation instruction, or unspecified test requirement remains.
- Type/interface consistency: `canonical_sha256(obj) -> str`, `evaluate(formal, model, scope) -> dict`, and `run_paths(formal_path, model_path, scope_path) -> dict` are used consistently.
- Safety correction: the plan deliberately does not fabricate a production model freeze because the actual GP scoring code/12-factor parameter package is not present. This preserves the pre-exposure guarantee while still allowing the subsystem itself to be fully implemented and tested.