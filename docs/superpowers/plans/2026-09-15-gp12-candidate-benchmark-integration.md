# GP12 Candidate Benchmark Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate validated candidate-only `CSI All Share / 000985` benchmark evidence into GP12 candidate package review without changing the frozen factor/parameter hashes or promoting the benchmark to recovered GP V1.1 history.

**Architecture:** Keep benchmark fetching/PIT/calendar verification isolated in `gp12_candidate_benchmark_v1.py`. Add an evidence validator to `gp12_candidate_v1.py` that consumes the emitted validation JSON, gates package review, and reports benchmark closure separately from feature-input readiness. Update the candidate workflow so benchmark validation runs before package review and its evidence is passed forward.

**Tech Stack:** Python 3.12, `unittest`, GitHub Actions, JSON contracts, Eastmoney daily kline source, frozen V4.80 trading-calendar artifact.

**Spec:** `docs/superpowers/specs/2026-09-15-gp12-candidate-benchmark-integration-design.md`

## Global Constraints

- Do not modify `data/GP12_CANDIDATE_FACTORS_V1.json` or `data/GP12_CANDIDATE_PARAMETERS_V1.json`.
- Preserve factor SHA256 `b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e`.
- Preserve parameter SHA256 `22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204`.
- Benchmark remains `CANDIDATE_ONLY_UNAPPROVED` and `NEW_RECONSTRUCTION_CANDIDATE`.
- Never claim `GP V1.1` benchmark recovery.
- Do not substitute benchmark raw/index daily close for the frozen factor family's `market_adjusted_close` semantics.
- Any benchmark evidence failure leaves the benchmark blocker open and makes integrated package review fail closed.

---

### Task 1: Add benchmark-evidence integration regression tests

**Files:**
- Create: `scripts/test_gp12_candidate_benchmark_integration_v1.py`
- Test: `scripts/test_gp12_candidate_benchmark_integration_v1.py`

**Interfaces:**
- Consumes: `gp12_candidate_v1.review_package(parameters_path, factors_path, benchmark_validation_path)`.
- Produces: regression expectations for valid, missing, drifted, blocked, and historically overclaimed benchmark evidence.

- [ ] **Step 1: Write the failing test**

Create tests that construct a valid benchmark validation artifact with the exact 000985 identity, current factor/parameter hashes, 1426-session coverage, PIT valid, source identity valid, no blockers, and historical-recovery flags false. Assert the integrated package review exposes `candidate_benchmark_validated=true`, closes only the benchmark sub-blocker, and keeps feature substitution/adoption restrictions false/open.

Add mutation cases for wrong factor hash, wrong benchmark code, `calendar.full_coverage=false`, `pit.policy_valid=false`, `source.identity_valid=false`, nonempty benchmark blockers, and `gp_v11_benchmark_recovered=true`; each must make `candidate_review_passed=false` and emit a benchmark-specific blocker.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=scripts python -m unittest -v scripts/test_gp12_candidate_benchmark_integration_v1.py
```

Expected: FAIL because `review_package` does not yet accept or validate benchmark evidence.

- [ ] **Step 3: Commit the red test**

Commit only the new test so the red state is auditable.

---

### Task 2: Implement benchmark-evidence validation in candidate review

**Files:**
- Modify: `scripts/gp12_candidate_v1.py`
- Test: `scripts/test_gp12_candidate_benchmark_integration_v1.py`

**Interfaces:**
- Consumes: validation JSON emitted by `scripts/gp12_candidate_benchmark_v1.py`.
- Produces: `_validate_candidate_benchmark_evidence(evidence: object) -> dict` and extended `review_package(..., benchmark_validation_path)` output.

- [ ] **Step 1: Add strict evidence validator**

Validate exact artifact identity, candidate status/origin, 000985 identity, formal window, frozen hashes, 1426 coverage/bounds, PIT policy, source identity, blocker closure, and historical-recovery flags. Return a normalized summary and blocker list; never throw a success path from partial evidence.

- [ ] **Step 2: Extend package review**

Add `benchmark_validation_path` to `review_package`. Missing or invalid evidence adds `CANDIDATE_BENCHMARK_EVIDENCE_INVALID`. Valid evidence sets `candidate_benchmark_validated=true` and `candidate_benchmark_blocker_closed=true`. Always emit `benchmark_feature_binding_allowed=false`, `market_adjusted_close_substitution_allowed=false`, and `historical_benchmark_recovered=false`.

Keep `NEW_STRATEGY_ADOPTION_REQUIRED`, `model_freeze_allowed=false`, `oos_metrics_allowed=false`, and `real_feature_inputs_validated=false` unchanged.

- [ ] **Step 3: Extend CLI**

Add `--benchmark-validation` and pass it into `review_package`.

- [ ] **Step 4: Run integration and existing candidate tests**

Run:

```bash
PYTHONPATH=scripts python -m unittest -v \
  scripts/test_gp12_candidate_benchmark_integration_v1.py \
  scripts/test_gp12_candidate_v1.py
```

Expected: PASS with zero failures.

- [ ] **Step 5: Commit implementation**

Commit candidate review changes and green tests.

---

### Task 3: Wire benchmark validation into candidate workflow

**Files:**
- Modify: `.github/workflows/gp12-candidate-v1.yml`
- Modify: `.github/workflows/gp12-candidate-benchmark-000985-v1.yml`

**Interfaces:**
- Consumes: V4.80 frozen calendar artifact and repository factor/parameter contracts.
- Produces: benchmark validation JSON before candidate package review and final workflow assertions for candidate-only semantics.

- [ ] **Step 1: Expand candidate workflow triggers/tests**

Allow the current integration branch and benchmark integration files to trigger the workflow. Add `test_gp12_candidate_benchmark_integration_v1` to candidate contract tests.

- [ ] **Step 2: Generate benchmark validation evidence before package review**

Install `requests`, download the verified V4.80 frozen calendar artifact from run `33977325822`, execute `gp12_candidate_benchmark_v1.py`, then run `gp12_candidate_v1.py --review --benchmark-validation <generated JSON>`.

- [ ] **Step 3: Assert integration semantics**

Require benchmark validated/closed, historical benchmark recovery false, substitution flags false, existing factor/parameter hashes unchanged, adoption status `UNAPPROVED`, and `NEW_STRATEGY_ADOPTION_REQUIRED` still present.

- [ ] **Step 4: Upload integrated evidence**

Include the benchmark binding and benchmark validation JSON in the candidate artifact without modifying factor/parameter files.

- [ ] **Step 5: Run GitHub Actions and inspect logs/artifacts**

Expected: candidate contract tests pass; full benchmark validation shows 1426/1426 exact coverage; integrated review passes candidate review while retaining adoption blocker; artifacts upload successfully.

---

### Task 4: Verify immutable-contract and fail-closed guarantees

**Files:**
- No new production files expected.

**Interfaces:**
- Consumes: branch diff, workflow logs, workflow artifacts.
- Produces: final verification evidence.

- [ ] **Step 1: Compare branch against pre-benchmark base**

Verify `data/GP12_CANDIDATE_FACTORS_V1.json` and `data/GP12_CANDIDATE_PARAMETERS_V1.json` are absent from the changed-file set.

- [ ] **Step 2: Confirm exact hashes from workflow output**

Confirm factors and parameters match the required SHA256 values.

- [ ] **Step 3: Confirm benchmark scope**

Confirm review says `candidate_benchmark_validated=true`, `candidate_benchmark_blocker_closed=true`, `historical_benchmark_recovered=false`, `market_adjusted_close_substitution_allowed=false`, `real_feature_inputs_validated=false`, and `NEW_STRATEGY_ADOPTION_REQUIRED` remains.

- [ ] **Step 4: Confirm final workflow conclusion and artifact**

Only report completion after the fresh workflow run is `completed/success` and the integrated artifact exists.
