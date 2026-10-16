# A-Share Tradability & Universe PIT Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fail-closed A-share tradability and point-in-time universe gates so RS/theme/timing and formal evaluation cannot assume fills or historical membership that were unavailable at the decision timestamp.

**Architecture:** Add two focused research modules: `a_share_tradability_gate_v1.py` for side-specific execution eligibility and RS eligibility, and `universe_pit_snapshot_v1.py` for deterministic decision-date universe snapshots. Extend the existing formal evaluation preflight to require their provenance identities. No numeric liquidity/new-listing/price-limit thresholds are invented.

**Tech Stack:** Python 3.12, stdlib `unittest`, SHA256/JSON canonicalization, existing GitHub Actions unittest workflow.

**Spec:** `docs/superpowers/specs/2026-10-16-a-share-tradability-universe-pit-gate-design.md`

## Global Constraints

- Branch remains `research/market-regime-fragility-v0`.
- Production use remains prohibited.
- Do not change Core10/Core13 ranking weights, XH V0, or MA5 status.
- Do not open an E3 unused set.
- Missing critical execution/universe evidence fails closed.
- Do not invent numeric liquidity thresholds, new-listing windows, price-limit percentages, fees, slippage, or hard-risk limits.
- Formal evaluation remains blocked while `minimum_effect_delta_tau` and `minimum_sample_required` are unfrozen.

## Review Focus

- One-word limit sessions with a valid close but no executable side liquidity must not be treated as fills.
- A symbol not listed / already delisted at the decision date must not enter the historical universe.
- A post-cutoff mutable field must invalidate the PIT record rather than be silently accepted.
- Missing policy versions must fail closed instead of falling back to current/default rules.
- RS eligibility must require actual trades and normal two-sided tradability, not merely unchanged price.

---

### Task 1: A-Share Tradability Gate V1

**Files:**
- Create: `research/market_regime_fragility_v0/test_a_share_tradability_gate_v1.py`
- Create: `research/market_regime_fragility_v0/a_share_tradability_gate_v1.py`
- Modify: `.github/workflows/market-regime-baseline-v1.yml`

**Interfaces:**
- Consumes: a dictionary matching the per-security input contract from the spec.
- Produces: `evaluate_tradability(record: dict) -> dict` with `buy_eligible`, `sell_eligible`, `rs_eligible`, `reasons`, `production_authorized`.

- [ ] **Step 1: Write failing tests** for suspended, locked limit-up, locked limit-down, T+1 zero sell quantity, missing critical evidence, and normal two-sided tradability.
- [ ] **Step 2: Wire the test/module paths into the existing research CI workflow and run CI to verify RED** because the implementation does not exist.
- [ ] **Step 3: Implement minimal `evaluate_tradability(record: dict) -> dict`** with fail-closed semantics and no exchange-specific numeric price-limit logic.
- [ ] **Step 4: Run the full research unittest suite and verify GREEN.**
- [ ] **Step 5: Commit the implementation.**

### Task 2: Universe PIT Snapshot V1

**Files:**
- Create: `research/market_regime_fragility_v0/test_universe_pit_snapshot_v1.py`
- Create: `research/market_regime_fragility_v0/universe_pit_snapshot_v1.py`
- Modify: `.github/workflows/market-regime-baseline-v1.yml`

**Interfaces:**
- Consumes: `build_universe_snapshot(records: list[dict], asof: str, policy_manifest: dict) -> dict` inputs with PIT timestamps/provenance.
- Produces: deterministic `universe_snapshot_hash`, eligible/ineligible/unresolved symbol sets, policy versions and `production_authorized=false`.

- [ ] **Step 1: Write failing tests** for deterministic ordering/hash, not-yet-listed/delisted exclusion, missing policy identity, post-cutoff mutable data, and unresolved policy parameters.
- [ ] **Step 2: Run CI to verify RED** before implementation exists.
- [ ] **Step 3: Implement minimal snapshot validation/canonical hashing** without inventing policy thresholds.
- [ ] **Step 4: Run the full research suite and verify GREEN.**
- [ ] **Step 5: Commit.**

### Task 3: Formal Evaluation Preflight Integration

**Files:**
- Modify: `research/market_regime_fragility_v0/test_formal_eval_preflight_v1.py`
- Modify: `research/market_regime_fragility_v0/formal_eval_preflight_v1.py`

**Interfaces:**
- Consumes manifest fields `universe_snapshot_hash`, `universe_pit_valid`, `tradability_policy_version`, `tradability_filter_applied_before_ranking`, `market_structure_regime_schedule_version`.
- Produces: fail-closed reason codes while preserving `production_authorized=false`.

- [ ] **Step 1: Add failing tests** showing each missing/false field blocks evaluation.
- [ ] **Step 2: Run CI and verify RED.**
- [ ] **Step 3: Add minimal preflight checks.**
- [ ] **Step 4: Run the full research suite and verify GREEN.**
- [ ] **Step 5: Commit.**

### Task 4: Governance Documentation and Status

**Files:**
- Create: `research/market_regime_fragility_v0/A_SHARE_DATA_PIT_CONTRACT_V1.md`
- Create: `research/market_regime_fragility_v0/MARKET_STRUCTURE_REGIME_CONTRACT_V1.md`
- Modify: `research/market_regime_fragility_v0/CURRENT_STATUS.md`

**Interfaces:**
- Documents price/corporate-action snapshots, financial announcement-time semantics, mutable vendor-field snapshots and source-backed structural-regime metadata.

- [ ] **Step 1: Document immutable snapshot/hash requirements and announcement-time rules without historical dates/numbers not yet source-audited.**
- [ ] **Step 2: Mark market-structure regime schedule as required but `NOT_YET_SOURCE_BOUND`.**
- [ ] **Step 3: Update current blockers and architecture ordering.**
- [ ] **Step 4: Run the full research suite again as final verification and record exact test count/run.**
- [ ] **Step 5: Compare branch changes against the pre-task head and confirm no production-core files changed.**
