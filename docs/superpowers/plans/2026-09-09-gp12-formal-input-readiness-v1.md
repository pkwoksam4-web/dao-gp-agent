# GP12 Formal Input Readiness V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Formal-only, fail-closed evidence-binding layer that determines exactly which `GP12_REBUILD_CANDIDATE_V1` feature families and factors are production-ready without approving the candidate, freezing a model, or consuming OOS data.

**Architecture:** Add one focused readiness module that validates candidate package identity, binds audited V4.82 evidence, separates artifact binding from point-in-time validity, and derives factor readiness from the candidate factor contract. A dedicated workflow consumes only previously validated Formal-era artifacts, emits `GP12_FORMAL_INPUT_READINESS_V1.json`, and proves that incomplete inputs remain blocked while all adoption/model-freeze/OOS flags remain false.

**Tech Stack:** Python 3.12 standard library, `unittest`, GitHub Actions, existing V4.82 Formal/Recovery artifacts and GP12 candidate JSON contracts.

**Spec:** `docs/superpowers/specs/2026-09-09-gp12-formal-input-readiness-v1-design.md`

## Global Constraints

- Strategy ID is exactly `GP12_REBUILD_CANDIDATE_V1`.
- Candidate adoption status is always `UNAPPROVED` in this subsystem.
- Formal end is exactly `2026-04-17`; no input row, label, diagnostic, or feature window after that date may influence readiness.
- Candidate package identities are exact canonical SHA256 values: parameters `22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204`; factors `b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e`.
- Never modify candidate formulas, weights, ranking, probability mapping, or policy.
- Never modify historical `GP_V11` recovery blockers or treat this candidate as recovered GP V1.1.
- Never create `MODEL_FREEZE_V482.json` or final `OOS_SCOPE_V482.json` from this subsystem.
- `model_freeze_allowed=false` and `oos_metrics_allowed=false` are invariant in V1 even if a synthetic all-family-ready fixture passes.
- API/structural availability is not substantive production validation.
- RAW close is not adjusted close; amount/volume are not turnover ratio or main net flow.
- QFQ exactness is not automatically PIT-safe; historical adjusted-close use requires explicit known-at proof.
- Market/sector breadth and historical sector membership must be explicitly defined and PIT-valid; the frozen 847-symbol remediation universe is not a proxy.
- 15-minute and 60-minute inputs are independent families.
- Missing production evidence is represented as deterministic blockers, not synthesized values.
- Recursively reject OOS/performance-result keys such as return/returns/pnl/alpha/sharpe/drawdown/hit_rate/win_rate/performance/metrics.

---

### Task 1: Readiness evidence model and fail-closed family states

**Files:**
- Create: `scripts/gp12_formal_input_readiness_v1.py`
- Create: `scripts/test_gp12_formal_input_readiness_v1.py`

**Interfaces:**
- Consumes: candidate parameter/factor JSON objects, a normalized evidence manifest, exact Formal identity values.
- Produces:
  - `canonical_json_sha256(value: object) -> str`
  - `validate_candidate_identity(parameters: dict, factors: dict) -> dict`
  - `evaluate_feature_families(evidence_manifest: dict) -> dict[str, dict]`
  - `build_readiness_report(parameters: dict, factors: dict, evidence_manifest: dict) -> dict`
- Family result schema:
  - `binding_state`: one of `BOUND_VERIFIED_ARTIFACT`, `BOUND_STRUCTURAL_ONLY`, `UNBOUND`, `NOT_DIRECTLY_REQUIRED`
  - `pit_state`: one of `PIT_VERIFIED`, `PIT_PARTIAL`, `PIT_UNVERIFIED`, `PIT_NOT_APPLICABLE`
  - `formal_feature_ready`: bool
  - `source_artifact`: nullable string
  - `source_sha256`: nullable lowercase 64-hex string
  - `coverage_start`: nullable ISO date
  - `coverage_end`: nullable ISO date
  - `blockers`: sorted unique list of deterministic strings

- [ ] **Step 1: Write RED tests for candidate identity, schema strictness, forbidden fields, and family-state rules**

Add tests equivalent to:

```python
class FormalInputReadinessIdentityTests(unittest.TestCase):
    def test_exact_candidate_package_identity_is_accepted(self):
        report = mod.build_readiness_report(
            load_parameters(), load_factors(), minimal_evidence())
        self.assertEqual(
            report['candidate_parameters_sha256'],
            '22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204')
        self.assertEqual(
            report['candidate_factors_sha256'],
            'b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e')

    def test_candidate_tampering_is_rejected(self):
        params = load_parameters()
        params['policy']['top_n'] = 11
        with self.assertRaises(ValueError):
            mod.build_readiness_report(params, load_factors(), minimal_evidence())

    def test_recursive_oos_or_performance_field_is_rejected(self):
        evidence = minimal_evidence()
        evidence['sources']['raw_daily_panel']['nested'] = {'sharpe': 1.2}
        with self.assertRaises(ValueError):
            mod.build_readiness_report(load_parameters(), load_factors(), evidence)

    def test_structural_pass_is_not_formal_feature_ready(self):
        evidence = minimal_evidence()
        evidence['feature_families']['main_net_flow'] = {
            'binding_state': 'BOUND_STRUCTURAL_ONLY',
            'pit_state': 'PIT_UNVERIFIED',
            'source_artifact': 'probe',
            'source_sha256': 'a' * 64,
            'coverage_start': '2020-06-01',
            'coverage_end': '2026-04-17',
            'blockers': [],
        }
        report = mod.build_readiness_report(load_parameters(), load_factors(), evidence)
        self.assertFalse(report['feature_families']['main_net_flow']['formal_feature_ready'])
```

Also test: unknown top-level fields, duplicate blocker normalization, invalid SHA/date formats, coverage past Formal end, and invariant `candidate_adoption_status/model_freeze_allowed/oos_metrics_allowed` values.

- [ ] **Step 2: Run tests and verify RED is caused by the missing module**

Run:

```bash
cd scripts
PYTHONPATH=. python -m unittest -v test_gp12_formal_input_readiness_v1.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'gp12_formal_input_readiness_v1'`.

- [ ] **Step 3: Implement minimal canonicalization, strict schema validation, candidate identity binding, forbidden-field scan, and family-state evaluation**

Implement constants exactly:

```python
STRATEGY_ID = 'GP12_REBUILD_CANDIDATE_V1'
ARTIFACT = 'GP12_FORMAL_INPUT_READINESS_V1'
VERSION = '1.0'
FORMAL_END = '2026-04-17'
PARAMETERS_SHA256 = '22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204'
FACTORS_SHA256 = 'b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e'
```

`formal_feature_ready` must be computed, never caller-supplied:

```python
ready = (
    binding_state == 'BOUND_VERIFIED_ARTIFACT'
    and pit_state == 'PIT_VERIFIED'
    and coverage_end <= FORMAL_END
    and not family_blockers
)
```

Supporting evidence may use `NOT_DIRECTLY_REQUIRED/PIT_NOT_APPLICABLE`, but scorer families may not use `NOT_DIRECTLY_REQUIRED`.

- [ ] **Step 4: Run focused tests to GREEN**

Run the Task 1 test module and require PASS.

- [ ] **Step 5: Commit Task 1**

Commit message:

```text
test/feat(gp12): add fail-closed Formal input readiness model
```

---

### Task 2: Derive factor readiness from the candidate factor contract

**Files:**
- Modify: `scripts/gp12_formal_input_readiness_v1.py`
- Modify: `scripts/test_gp12_formal_input_readiness_v1.py`

**Interfaces:**
- Consumes: `data/GP12_CANDIDATE_FACTORS_V1.json` and Task 1 family states.
- Produces:
  - `derive_factor_dependencies(factors_contract: dict) -> dict[str, tuple[str, ...]]`
  - `derive_factor_readiness(factors_contract: dict, family_states: dict, supporting_states: dict) -> dict`
- Exact dependency result for current contract:

```python
{
  'F1': ('market_adjusted_close',),
  'F2': ('market_breadth',),
  'F3': ('sector_adjusted_close', 'market_adjusted_close'),
  'F4': ('sector_adjusted_close',),
  'F5': ('sector_breadth', 'sector_membership_pit'),
  'F6': ('stock_adjusted_close',),
  'F7': ('stock_adjusted_close',),
  'F8': ('stock_adjusted_close',),
  'F9': ('stock_adjusted_close',),
  'F10': ('stock_adjusted_close',),
  'F11': ('stock_adjusted_close', 'amount_turnover', 'main_net_flow'),
  'F12': ('intraday_15m', 'intraday_60m'),
}
```

- [ ] **Step 1: Add RED tests for dependency derivation and partial-ready behavior**

Add tests:

```python
def test_synthetic_pit_adjusted_close_only_makes_f6_to_f10_ready():
    evidence = minimal_evidence()
    mark_ready(evidence, 'stock_adjusted_close')
    report = mod.build_readiness_report(load_parameters(), load_factors(), evidence)
    self.assertEqual(report['ready_factor_ids'], ['F6','F7','F8','F9','F10'])
    self.assertFalse(report['candidate_scoring_ready'])


def test_market_benchmark_missing_blocks_f1_and_f3():
    report = mod.build_readiness_report(load_parameters(), load_factors(), minimal_evidence())
    self.assertIn('F1', report['blocked_factor_ids'])
    self.assertIn('F3', report['blocked_factor_ids'])


def test_turnover_and_flow_block_f11_independently():
    evidence = minimal_evidence()
    mark_ready(evidence, 'stock_adjusted_close')
    mark_ready(evidence, 'amount_turnover')
    report = mod.build_readiness_report(load_parameters(), load_factors(), evidence)
    self.assertIn('main_net_flow', report['factor_readiness']['F11']['missing_dependencies'])


def test_f12_requires_both_intraday_families():
    evidence = minimal_evidence()
    mark_ready(evidence, 'intraday_15m')
    report = mod.build_readiness_report(load_parameters(), load_factors(), evidence)
    self.assertFalse(report['factor_readiness']['F12']['ready'])
```

Also test F5 requires supporting `sector_membership_pit` even if `sector_breadth` is ready.

- [ ] **Step 2: Run the new tests and verify RED is for missing dependency functions/fields**

Run the focused module; expected failures mention missing `derive_factor_dependencies`, `factor_readiness`, or wrong ready-factor output.

- [ ] **Step 3: Implement dependency extraction with contract cross-checking**

Do not hard-code only factor IDs. Read `input_families` from the factor contract and apply the one explicit supporting override:

```python
SUPPORTING_DEPENDENCIES = {'F5': ('sector_membership_pit',)}
```

Require factor IDs exactly `F1..F12`, unique, and require the derived family set to match the candidate scorer/router vocabulary. A formula-contract drift raises `ValueError('candidate factor dependency contract mismatch')`.

- [ ] **Step 4: Implement factor readiness and candidate-scoring gate**

`candidate_scoring_ready` is true only when:

```python
all(factor_readiness[f]['ready'] for f in F1_TO_F12)
and feature_families['status']['formal_feature_ready']
and supporting_evidence['liquidity_contract']['ready']
```

Even if this becomes true in a synthetic fixture:

```python
candidate_freeze_ready = False
model_freeze_allowed = False
oos_metrics_allowed = False
candidate_adoption_status = 'UNAPPROVED'
```

- [ ] **Step 5: Run Task 2 tests and Task 1 regressions to GREEN**

Run the full readiness test module.

- [ ] **Step 6: Commit Task 2**

Commit message:

```text
feat(gp12): derive factor readiness from exact candidate contract
```

---

### Task 3: Bind current V4.82 Formal production evidence without over-promoting it

**Files:**
- Create: `data/GP12_FORMAL_INPUT_EVIDENCE_V1.json`
- Modify: `scripts/gp12_formal_input_readiness_v1.py`
- Modify: `scripts/test_gp12_formal_input_readiness_v1.py`

**Interfaces:**
- Consumes exact known V4.82 identities and evidence summaries.
- Produces `validate_production_evidence_manifest(manifest: dict) -> dict` and the initial production readiness report.

**Initial authoritative/support bindings:**

```text
formal_artifact_sha256 = e642481399a05635d07b1baa39f57d3aa84dfd1c18e315edd927ec42da553796
formal_calendar_sha256 = 5a872a47cf7a338cc48aa628b8de46053fddc3ed161a2617550199d0607efae7
legacy_calendar_sha256 = 0bfa32175dfccbd24d30eb7ceb0605f6cde2ed0bcc31ac2cac61479ba812add0
universe_sha256 = dfe5c75692d38e5fde7cd5c32eb2ed090a8ab6dffcfd41d5ebda07dc2d6d96fb
formal_dates = 1426
formal_range = 2020-06-01..2026-04-17
raw_trade_rows = 1011607
raw_symbol_n = 847
liquidity_threshold_cny = 80000000
liquidity_lookback_market_sessions = 20
liquidity_statistic = median
minimum_trade_density_20 = 0.8
required_prior_traded_sessions = 120
current_session_must_be_traded = true
```

- [ ] **Step 1: Write RED tests for exact Formal/calendar/universe/RAW/liquidity bindings and non-substitution rules**

Add tests that mutate each invariant and require deterministic blocker/exception behavior. Add explicit tests:

```python
def test_raw_panel_does_not_satisfy_adjusted_turnover_flow_or_breadth():
    report = build_from_production_manifest()
    for family in ('stock_adjusted_close','amount_turnover','main_net_flow','market_breadth','sector_breadth'):
        self.assertFalse(report['feature_families'][family]['formal_feature_ready'])


def test_qfq_evidence_without_known_at_remains_pit_unverified():
    report = build_from_production_manifest()
    self.assertEqual(report['feature_families']['stock_adjusted_close']['pit_state'], 'PIT_UNVERIFIED')
    self.assertIn('ADJUSTED_CLOSE_PIT_UNVERIFIED', report['blockers'])


def test_liquidity_contract_is_support_only_not_turnover_ratio():
    report = build_from_production_manifest()
    self.assertTrue(report['supporting_evidence']['liquidity_contract']['ready'])
    self.assertFalse(report['feature_families']['amount_turnover']['formal_feature_ready'])
```

- [ ] **Step 2: Run tests and verify RED reflects absent production-manifest validation**

Require the focused failures before implementation.

- [ ] **Step 3: Add the production evidence manifest with exact source identities and explicit unknowns**

The JSON must explicitly mark currently unbound/unverified families rather than omit them. Expected initial states include:

```json
{
  "market_calendar": {"binding_state":"BOUND_VERIFIED_ARTIFACT","pit_state":"PIT_VERIFIED"},
  "stock_adjusted_close": {"binding_state":"BOUND_VERIFIED_ARTIFACT","pit_state":"PIT_UNVERIFIED"},
  "market_adjusted_close": {"binding_state":"UNBOUND","pit_state":"PIT_UNVERIFIED"},
  "sector_adjusted_close": {"binding_state":"UNBOUND","pit_state":"PIT_UNVERIFIED"},
  "amount_turnover": {"binding_state":"UNBOUND","pit_state":"PIT_UNVERIFIED"},
  "main_net_flow": {"binding_state":"UNBOUND","pit_state":"PIT_UNVERIFIED"},
  "market_breadth": {"binding_state":"UNBOUND","pit_state":"PIT_UNVERIFIED"},
  "sector_breadth": {"binding_state":"UNBOUND","pit_state":"PIT_UNVERIFIED"},
  "status": {"binding_state":"BOUND_STRUCTURAL_ONLY","pit_state":"PIT_PARTIAL"},
  "intraday_15m": {"binding_state":"UNBOUND","pit_state":"PIT_UNVERIFIED"},
  "intraday_60m": {"binding_state":"UNBOUND","pit_state":"PIT_UNVERIFIED"}
}
```

`stock_adjusted_close` may bind the QFQ correctness artifact identity but must retain blocker `ADJUSTED_CLOSE_PIT_UNVERIFIED` until historical known-at proof exists.

- [ ] **Step 4: Implement exact production-manifest validators**

Validate frozen identities and return deterministic blockers:

```text
CANDIDATE_PACKAGE_IDENTITY_MISMATCH
FORMAL_EVIDENCE_INVALID
FORMAL_BOUNDARY_VIOLATION
CALENDAR_BINDING_INVALID
UNIVERSE_BINDING_INVALID
RAW_PANEL_EVIDENCE_INVALID
QFQ_EVIDENCE_INVALID
ADJUSTED_CLOSE_PIT_UNVERIFIED
MARKET_BENCHMARK_UNBOUND
SECTOR_SERIES_UNBOUND
SECTOR_MEMBERSHIP_PIT_UNBOUND
TURNOVER_RATIO_UNBOUND
MAIN_NET_FLOW_UNBOUND
MARKET_BREADTH_UNBOUND
SECTOR_BREADTH_UNBOUND
STATUS_SEMANTICS_INCOMPLETE
INTRADAY_15M_UNBOUND
INTRADAY_60M_UNBOUND
LABEL_PROVENANCE_UNBOUND
FORBIDDEN_OOS_OR_PERFORMANCE_FIELD
```

Blockers are sorted/unique. Missing evidence produces a report; malformed schema/programmer corruption raises an exception.

- [ ] **Step 5: Run production-manifest tests and all readiness tests to GREEN**

Require all readiness tests PASS.

- [ ] **Step 6: Commit Task 3**

Commit message:

```text
data(gp12): bind audited Formal evidence without PIT overclaim
```

---

### Task 4: Production GitHub Actions evidence binding and regression proof

**Files:**
- Create: `.github/workflows/gp12-formal-input-readiness-v1.yml`
- Create: `docs/gp12-formal-input-readiness-v1.md`
- Modify: `scripts/gp12_formal_input_readiness_v1.py` to add CLI only if not already present.

**Interfaces:**
- CLI:

```text
python scripts/gp12_formal_input_readiness_v1.py \
  --parameters data/GP12_CANDIDATE_PARAMETERS_V1.json \
  --factors data/GP12_CANDIDATE_FACTORS_V1.json \
  --evidence data/GP12_FORMAL_INPUT_EVIDENCE_V1.json \
  --out out/GP12_FORMAL_INPUT_READINESS_V1.json
```

- [ ] **Step 1: Add RED CLI/workflow contract tests**

Add tests that run the CLI in a temp directory and assert:

```python
self.assertEqual(report['artifact'], 'GP12_FORMAL_INPUT_READINESS_V1')
self.assertEqual(report['formal_end'], '2026-04-17')
self.assertEqual(report['candidate_adoption_status'], 'UNAPPROVED')
self.assertFalse(report['candidate_scoring_ready'])
self.assertFalse(report['candidate_freeze_ready'])
self.assertFalse(report['real_feature_inputs_validated'])
self.assertFalse(report['model_freeze_allowed'])
self.assertFalse(report['oos_metrics_allowed'])
```

Also assert the production report contains no forbidden OOS/performance keys recursively.

- [ ] **Step 2: Run CLI tests and verify RED**

Expected failure: CLI or writer entry point absent.

- [ ] **Step 3: Implement the minimal CLI and deterministic JSON writer**

Use UTF-8, sorted keys, 2-space indentation plus one trailing newline for the artifact file. Hash identity calculations remain canonical JSON without whitespace/trailing newline.

- [ ] **Step 4: Add isolated workflow**

Workflow name: `GP12 Formal Input Readiness V1`.

Jobs:

```text
contracts:
  - checkout exact branch commit
  - Python 3.12
  - run test_gp12_formal_input_readiness_v1
  - run test_gp12_candidate_v1
  - run test_gp12_eastmoney_adapter_v1
  - run test_gp12_sohu_qfq_adapter_v1
  - run test_gp12_source_router_v1
  - run test_strategy_asset_recovery_v482
  - run test_model_freeze_recovery_v482
  - run test_oos_admission_v482

production-readiness:
  - depends on contracts
  - consume only Formal-era evidence / repository-bound exact manifests
  - run readiness CLI
  - assert formal_end == 2026-04-17
  - assert candidate_adoption_status == UNAPPROVED
  - assert model_freeze_allowed == false
  - assert oos_metrics_allowed == false
  - assert no OOS/performance keys
  - upload readiness JSON + evidence manifest
```

Do not add network downloads of OOS market data. If a previously validated artifact must be downloaded, pin its successful run/artifact identity and inspect the contents before declaring it bound.

- [ ] **Step 5: Add human-readable readiness note**

`docs/gp12-formal-input-readiness-v1.md` must state the exact distinction between:
- source exists,
- artifact is bound,
- PIT is verified,
- family is Formal-feature-ready,
- all 12 factors are scoring-ready,
- candidate adoption/freeze is still not approved.

List the production ready/unready families from the generated artifact, not from assumptions.

- [ ] **Step 6: Run local/CI regression suite**

Required command equivalent:

```bash
cd scripts
PYTHONPATH=. python -m unittest -v \
  test_gp12_formal_input_readiness_v1 \
  test_gp12_candidate_v1 \
  test_gp12_eastmoney_adapter_v1 \
  test_gp12_sohu_qfq_adapter_v1 \
  test_gp12_source_router_v1 \
  test_strategy_asset_recovery_v482 \
  test_model_freeze_recovery_v482 \
  test_oos_admission_v482
```

Require all tests PASS.

- [ ] **Step 7: Inspect real Actions logs and artifact**

Do not claim completion from workflow status alone. Read the production job logs and downloaded artifact. Verify:
- exact candidate hashes;
- exact Formal/calendar/universe identities;
- no date after `2026-04-17` is consumed;
- actual `validated_families`, `missing_or_unvalidated_families`, `ready_factor_ids`, `blocked_factor_ids`, and blocker list;
- `candidate_scoring_ready=false` unless every required production family truly passed;
- all adoption/freeze/OOS flags remain false.

- [ ] **Step 8: Commit Task 4**

Commit message:

```text
ci(gp12): materialize Formal input readiness evidence
```

---

### Task 5: Isolation review and draft PR

**Files:**
- No new production files expected; only fix concrete review findings if verification discovers them.

**Interfaces:**
- Base branch: `gp/strategy-package-candidate-v482`
- Head branch: `gp/gp12-formal-input-readiness-v1`

- [ ] **Step 1: Compare branch isolation**

Require `behind_by=0` relative to the candidate head used for the branch and confirm changed files are restricted to readiness spec/plan/module/test/evidence/workflow/readiness documentation.

- [ ] **Step 2: Verify PR #9 candidate files are not modified**

Explicitly compare and require no modifications to:

```text
scripts/gp12_candidate_v1.py
data/GP12_CANDIDATE_PARAMETERS_V1.json
data/GP12_CANDIDATE_FACTORS_V1.json
scripts/gp12_eastmoney_adapter_v1.py
scripts/gp12_sohu_qfq_adapter_v1.py
scripts/gp12_source_router_v1.py
```

- [ ] **Step 3: Run verification-before-completion checklist**

Use fresh CI/log/artifact evidence. Do not rely on prior run counts or cached claims.

- [ ] **Step 4: Open a draft PR without merging**

Title:

```text
feat(gp12): add Formal-only production input readiness gate
```

Body must report actual observed production readiness, exact run/artifact IDs, and explicitly state:

```text
historical GP V1.1 recovery blockers unchanged
candidate adoption remains UNAPPROVED
model_freeze_allowed=false
oos_metrics_allowed=false
no OOS data/performance consumed
```

Do not merge automatically.
