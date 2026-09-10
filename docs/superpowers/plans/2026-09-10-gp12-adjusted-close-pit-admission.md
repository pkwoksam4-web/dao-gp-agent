# GP12 Adjusted-Close PIT Admission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close only the GP12 `ADJUSTED_CLOSE_PIT_UNVERIFIED` blocker by turning the already-materialized V4.82 factor/provenance and event-timing evidence into a reproducible, fail-closed promotion artifact, while leaving turnover and label blockers open.

**Architecture:** Three explicit layers are kept separate. First, an event-timing audit maps every one of the frozen 2,732 V4.81/V4.82 corporate-action ledger events to the exact frozen source evidence and proves its availability date is not after the ex-date. Second, an override-timing audit binds all 270 standard and 11 special V4.82 corrected event ratios to the same announcement/PDF evidence used by the factor closure, with same-day special cases requiring explicit pre-open CNINFO timestamps. Third, an admission runner consumes those two PASS audits plus the 1,011,607-row QFQ provenance candidate and emits promoted row-level provenance and a GP12 blocker checkpoint; it must not close turnover, label, model-freeze, or OOS gates.

**Tech Stack:** Python 3.12, pandas/pyarrow in GitHub Actions, existing V4.81/V4.82 frozen artifacts, GitHub Actions artifact downloads.

**Spec:** `docs/superpowers/specs/2026-08-31-corporate-action-qfq-provenance-design.md`

## Global Constraints

- Formal window remains `2020-06-01..2026-04-17`.
- Frozen V3.67 Sample50 remains unchanged and must stay 50/50 PASS at <=5bp.
- Full Formal factor path remains 844/844 PASS at <=5bp.
- No forward fill.
- No OOS rows may be consumed.
- No event with an availability/publication time after its ex-date may be admitted.
- Same-day special override evidence must prove publication before the 09:30 China-market open, not merely same calendar date.
- The promoted row table must contain exactly 1,011,607 unique `(symbol,date)` rows over 844 traded symbols, positive `qfq_factor`, non-empty unique `provenance_id`, and row factor mismatch <=5bp.
- `TURNOVER_RATIO_UNBOUND` and `LABEL_PROVENANCE_UNBOUND` remain open after this task.
- `model_freeze_allowed` and `oos_metrics_allowed` remain false after this task.

---

### Task 1: Materialize exact 2,732-event PIT timing coverage

**Files:**
- Create: `scripts/test_gp12_event_timing_admission_v482.py`
- Create: `scripts/gp12_event_timing_admission_v482.py`
- Create: `.github/workflows/gp12-event-timing-admission-v482.yml`

**Interfaces:**
- Consumes: `GLOBAL_QFQ_MISSING_EVENT_CLOSURE_V481.json`; Eastmoney full-PIT CSV/JSON; F10 missing-event coverage; F10 unresolved-history evidence; supplemental THS/Sohu/Sina frozen evidence; rights-allotment PIT evidence.
- Produces: `GP12_EVENT_TIMING_ADMISSION_V482.json` and `GP12_EVENT_TIMING_ROWS_V482.csv`.

- [ ] **Step 1: Write failing tests** for exact source partitions, late-date rejection, missing-key rejection, and a fully covered synthetic PASS case.
- [ ] **Step 2: Run the test workflow before production code exists** and verify RED because `gp12_event_timing_admission_v482` cannot be imported.
- [ ] **Step 3: Implement the minimal parser/auditor** that joins by final ledger `(symbol,ex_date,source)`, not by preliminary target counts. Required real-source partition is exactly `2620 + 93 + 8 + 7 + 2 + 1 + 1 = 2732`.
- [ ] **Step 4: Run unit tests and the real artifact workflow**; require `covered_n=2732`, `missing_n=0`, `late_n=0`, and exact source counts.
- [ ] **Step 5: Record artifact digest and workflow run id** in the emitted audit.

### Task 2: Materialize exact 281-override corrected-term timing coverage

**Files:**
- Create: `scripts/test_gp12_override_timing_admission_v482.py`
- Create: `scripts/gp12_override_timing_admission_v482.py`
- Create: `.github/workflows/gp12-override-timing-admission-v482.yml`

**Interfaces:**
- Consumes: six V4.82 standard-closure stages, reparsed provenance, four official CNINFO evidence sets, 11-row special provenance, and the two-row same-day pre-open timestamp audit.
- Produces: `GP12_OVERRIDE_TIMING_ADMISSION_V482.json` and `GP12_OVERRIDE_TIMING_ROWS_V482.csv`.

- [ ] **Step 1: Write failing tests** for announcement-id/SHA mismatch, late announcement rejection, same-day-special-without-preopen-proof rejection, and complete synthetic PASS.
- [ ] **Step 2: Run tests before implementation** and verify RED.
- [ ] **Step 3: Implement exact standard merge and evidence binding**: 67 effective + 124 secondary + 17 reparsed + 54 recovered + 3 final-six + 5 final-four deduplicate to 270; every row must bind the same announcement id and PDF SHA to an evidence record carrying `announcementTime`.
- [ ] **Step 4: Implement special handling**: all 11 materialized CNINFO special records require adjunct-date <= ex-date; the two same-day cases `000697.SZ/2025-11-28` and `600306.SH/2023-12-26` additionally require the frozen timestamp audit to prove `announcement_time < 09:30 Asia/Shanghai`.
- [ ] **Step 5: Run real workflow**; require `standard_pass_n=270`, `special_pass_n=11`, `total_pass_n=281`, `missing_n=0`, `late_n=0`.

### Task 3: Promote row-level adjusted-close provenance only

**Files:**
- Create: `scripts/test_gp12_adjusted_close_pit_admission_v482.py`
- Create: `scripts/gp12_adjusted_close_pit_admission_v482.py`
- Create: `.github/workflows/gp12-adjusted-close-pit-admission-v482.yml`

**Interfaces:**
- Consumes: Task 1 PASS audit, Task 2 PASS audit, `GP12_QFQ_ROW_PROVENANCE_CANDIDATE_V482` row table/audit, frozen Sample50 exact audit, and V4.82 Formal readiness final audit.
- Produces: `GP12_QFQ_ROW_PROVENANCE_ADMITTED_V482.parquet` plus `GP12_ADJUSTED_CLOSE_PIT_ADMISSION_V482.json`.

- [ ] **Step 1: Write failing tests** proving admission requires all three evidence layers and proving the resulting blocker state is exactly adjusted-close closed / turnover open / label open / model freeze false / OOS false.
- [ ] **Step 2: Run tests before implementation** and verify RED.
- [ ] **Step 3: Implement minimal admission logic** that changes only `validation_status` to `VALIDATED_GLOBAL_PROVENANCE` after rechecking 1,011,607 unique rows, 844 symbols, positive factors, unique provenance ids, mismatch <=5bp, Sample50 50/50 PASS, V4.82 844/844 PASS, Task 1 PASS, and Task 2 PASS.
- [ ] **Step 4: Run unit tests and real workflow**; reject any upstream digest/run mismatch or missing artifact.
- [ ] **Step 5: Verify emitted blocker checkpoint** contains `ADJUSTED_CLOSE_PIT_UNVERIFIED=false`, `TURNOVER_RATIO_UNBOUND=true`, `LABEL_PROVENANCE_UNBOUND=true`, `model_freeze_allowed=false`, `oos_metrics_allowed=false`.

## Self-Review

- Spec coverage: retains complete event coverage, independent Sample50 <=5bp, full 847-scope row provenance, and fail-closed promotion requirements from V4.71/V4.82.
- No semantic relaxation: timing evidence is added; the factor formula/threshold/sample are not changed.
- No unrelated promotion: turnover and label semantics remain explicitly out of scope and open.
- No placeholders: all counts, files, source partitions, thresholds, and promotion invariants are explicit.
