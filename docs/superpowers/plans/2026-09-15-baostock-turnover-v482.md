# BaoStock PIT Turnover V4.82 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close `TURNOVER_RATIO_UNBOUND` only if BaoStock `turn` reproduces the exact V4.82 Formal trade-date panel with audited PIT semantics and an independent Sohu rounding cross-check.

**Architecture:** Reuse the validated V4.80 BaoStock `query_history_k_data_plus` source and exact 847-symbol scope. Extend it additively with `turn`, apply only the five frozen V4.82 false-zero trade-status corrections, reconcile against authoritative PIT-ST expected trade dates, then materialize/merge sharded artifacts. Sohu remains an independent cross-source check with a frozen 0.5 bp tolerance; readiness, model freeze, and OOS remain fail-closed until a downstream binding checkpoint is independently generated.

**Tech Stack:** Python 3.11/3.12, `baostock==0.9.3`, pandas, pyarrow, GitHub Actions, unittest.

**Spec:** Existing V4.82 Formal/PIT-ST contracts in `scripts/pit_st_collector_v480.py`, `scripts/baostock_turnover_v482.py`, and `scripts/sohu_turnover_v482.py`.

## Global Constraints

- Formal window is exactly `2020-06-01` through `2026-04-17`.
- Scope is exactly 847 symbols; expected turnover symbols are 844; expected trade rows are 1,011,607.
- Zero-trade symbols are exactly `600074.SH`, `600485.SH`, `600677.SH`.
- Apply only five exact false-zero corrections: `002087.SZ 2024-06-13`, `300356.SZ 2023-06-20`, `600647.SH 2024-06-13`, `600766.SH 2024-06-13`, `603133.SH 2024-06-13`.
- BaoStock `turn` is percent and must be normalized to ratio by division by 100.
- Sohu/BaoStock cross-source tolerance is frozen at `<=0.5 bp`, reflecting Sohu's two-decimal percentage-point precision.
- Missing, extra, duplicate, nonfinite, negative, query-error, or unresolved rows fail closed.
- `candidate_adoption_status`, model freeze, Formal admission, and OOS remain closed throughout turnover materialization.

---

### Task 1: Exact-date materializer contracts

**Files:**
- Create: `scripts/test_baostock_turnover_full_v482.py`
- Create: `scripts/baostock_turnover_full_v482.py`

**Interfaces:**
- Consumes: authoritative PIT-ST rows plus `apply_trade_status_corrections()` and `audit_and_extract()` from `baostock_turnover_v482.py`.
- Produces: `select_shard()`, `expected_trade_dates()`, `audit_exact_dates()`, and shard/global gate helpers.

- [ ] Write failing tests for deterministic sharding, exact expected-date reconciliation, the three zero-trade symbols, and frozen global counts.
- [ ] Run tests and verify failures are only missing full-materializer functions/module.
- [ ] Implement the minimum pure functions needed to pass.
- [ ] Run all core + full-materializer contract tests to GREEN.

### Task 2: Sharded BaoStock materialization

**Files:**
- Modify: `scripts/baostock_turnover_full_v482.py`
- Create: `.github/workflows/gp12-baostock-turnover-full-v482.yml`

**Interfaces:**
- Consumes: `data/pit_st_scope_v480.txt` and authoritative `gp-pit-st-v480-merged` artifact from run `33971534669`.
- Produces: per-shard parquet/JSON evidence with query status, correction application, expected vs actual dates, row counts, and safety flags.

- [ ] Materialize four or eight deterministic shards using BaoStock 0.9.3.
- [ ] Fail each shard closed on unresolved symbols, bad turnover, or expected-date mismatch.
- [ ] Upload shard artifacts even on failure for diagnosis.

### Task 3: Global merge and independent cross-check

**Files:**
- Modify: `scripts/baostock_turnover_full_v482.py`
- Modify: `.github/workflows/gp12-baostock-turnover-full-v482.yml`

**Interfaces:**
- Produces: merged full turnover parquet plus audit JSON.

- [ ] Merge all shard outputs and require exactly 847 scope / 844 turnover symbols / 1,011,607 rows / 0 missing / 0 extra / 0 duplicate / 0 bad / 0 unresolved.
- [ ] Cross-check Sohu evidence where available using the frozen `<=0.5 bp` rounding tolerance; never tune the threshold to results.
- [ ] Set `turnover_ratio_pit_verified=true` only if source semantics, exact coverage, and cross-check gates all pass.
- [ ] Keep Formal admission, candidate adoption, model freeze, and OOS false.

### Task 4: Downstream readiness binding

**Files:**
- Create or modify a focused downstream binding/checkpoint script and workflow patterned after `gp12-readiness-pit-adjusted-close-v482.yml`.

**Interfaces:**
- Consumes: immutable full-turnover audit artifact.
- Produces: additive readiness checkpoint without mutating frozen V1 evidence.

- [ ] Verify the turnover audit artifact hash and exact gate fields.
- [ ] Replace only `TURNOVER_RATIO_UNBOUND` in the downstream blocker set if the turnover PIT gate is true.
- [ ] Recompute factor readiness from frozen candidate dependencies.
- [ ] Assert candidate adoption/model freeze/OOS remain closed.
- [ ] Run integration contracts and materialize the new checkpoint before updating PR #10.
