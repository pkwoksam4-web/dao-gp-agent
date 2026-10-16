# Atomic Evidence Ledger + Canonical Classifier V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a deterministic, PIT-auditable `Atomic Evidence Ledger -> Canonical Market State` bridge for the research-only market-regime layer without adding numeric market thresholds or opening an unused formal evaluation set.

**Architecture:** Raw numeric observations stay outside this subsystem. The ledger validates already-categorical atomic evidence, timestamps, provenance and PIT validity, then hashes a canonical representation. The classifier consumes only a valid ledger, applies finite categorical precedence rules, reuses the existing risk-score mapping, and feeds the existing `state_resolution_v1.py` veto/router layer.

**Tech Stack:** Python 3.12, stdlib `unittest`, `datetime`, `hashlib`, `json`; GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-16-atomic-evidence-ledger-canonical-classifier-design.md`

## Global Constraints

- Branch only: `research/market-regime-fragility-v0`; never modify production core or `main`.
- Status remains `RESEARCH_ONLY / FORMAL_OOS=NO / PRODUCTION_USE=PROHIBITED`.
- Do not introduce numeric market thresholds from consumed historical outcomes.
- Do not open or consume a new unused formal evaluation set.
- `UNAVAILABLE != NORMAL` is mandatory.
- `HEDGE / CAPITAL ROTATION` remains `UNIMPLEMENTED_DATA_LAYER`.
- `minimum_effect_delta_tau = NOT_FROZEN`; `minimum_sample_required = NOT_FROZEN`.
- Existing Core10/Core13, `XH_REGIME_GATE_V0`, MA5 standalone-exit status, A-share execution policy and hard-risk policy remain unchanged.
- Every production-code change follows RED -> GREEN TDD and full-suite verification.

## Review Focus

1. Timestamp parsing / timezone ambiguity must fail closed rather than compare naïve and aware timestamps silently — Task 1 tests mixed/invalid timestamps.
2. Missing provenance or `pit_valid != True` must invalidate the ledger — Task 1 tests both.
3. External-shock evidence must not be erased by repair state; classifier output may be `REPAIR` only when the higher-priority unresolved-shock predicate is false — Task 2 tests coexistence inputs and precedence.
4. A single weak channel must never become confirmed fragility; breadth divergence alone is at most WATCH — Task 2 tests single-channel and multi-channel boundaries.
5. Formal preflight must prove classifier output came from a valid versioned ledger, not merely accept a classifier name/hash — Task 3 adds explicit ledger-version / PIT-valid / evidence-hash requirements.

---

### Task 1: Atomic Evidence Ledger V1

**Files:**
- Create: `research/market_regime_fragility_v0/test_atomic_evidence_ledger_v1.py`
- Create: `research/market_regime_fragility_v0/atomic_evidence_ledger_v1.py`

**Interfaces:**
- Produces: `LEDGER_VERSION = "ATOMIC_EVIDENCE_LEDGER_V1"`.
- Produces: `validate_and_hash_ledger(*, decision_cutoff: str, evidence: dict[str, dict], classifier_version: str) -> dict`.
- Return keys: `ledger_version`, `valid`, `normalized_evidence`, `missing_fields`, `invalid_fields`, `reason_codes`, `evidence_hash`.
- Required evidence fields: `external_shock`, `shock_source_persistence`, `local_transmission_state`, `breadth_state`, `leadership_state`, `small_mid_state`, `turnover_state`, `repair_state`.
- Each evidence item requires `value`, `observed_at`, `provenance`, `pit_valid`.

- [ ] **Step 1: Write failing ledger tests**

Cover deterministic hashing; provenance mutation changes hash; missing field; invalid enum; empty provenance; `pit_valid=False`; post-cutoff observation; malformed/mixed timestamp handling; semantically identical input ordering produces identical hash.

- [ ] **Step 2: Run the research test suite and verify RED**

Run: `python -m unittest discover -s research/market_regime_fragility_v0 -p "test_*.py" -v`

Expected: FAIL/ERROR because `atomic_evidence_ledger_v1` does not exist.

- [ ] **Step 3: Implement minimal ledger validation and canonical hashing**

Parse ISO-8601 timestamps into timezone-aware UTC values; reject invalid or naïve timestamps. Validate enums exactly as the design spec. Canonicalize required fields by sorted field name and hash JSON containing ledger version, classifier version, decision cutoff and normalized evidence fields.

- [ ] **Step 4: Run ledger tests and full research suite**

Expected: all existing tests plus new ledger tests PASS.

- [ ] **Step 5: Commit**

Commit message: `research: implement atomic evidence ledger v1`

### Task 2: Canonical Market-State Classifier V1

**Files:**
- Create: `research/market_regime_fragility_v0/test_canonical_state_classifier_v1.py`
- Create: `research/market_regime_fragility_v0/canonical_state_classifier_v1.py`
- Read-only dependency: `research/market_regime_fragility_v0/state_resolution_v1.py`

**Interfaces:**
- Consumes Task 1 validated ledger output.
- Produces: `CLASSIFIER_VERSION = "CANONICAL_STATE_CLASSIFIER_V1"`.
- Produces: `classify_canonical_state(ledger_result: dict) -> dict`.
- Return keys: `classifier_version`, `canonical_market_state`, `risk_evidence_score`, `reason_codes`, `missing_fields`, `invalid_fields`, `evidence_hash`, `full_classifier_resolution_available`, `production_authorized`.
- Risk score mapping must import/reuse `STATE_TO_SCORE` from `state_resolution_v1.py`; no duplicate mapping.

**Finite categorical resolution contract:**
- Invalid ledger or any required `UNAVAILABLE`/`UNRESOLVED` discriminator needed for the chosen path -> `UNAVAILABLE`.
- Contradiction: `external_shock=ABSENT` with `SOURCE_ONGOING` or `SOURCE_ESCALATING`; or `PENDING_TRANSMISSION` with `repair_state=BROAD` -> `UNAVAILABLE`, reason `CONTRADICTORY_REQUIRED_EVIDENCE`.
- `ACTIVE_DE_RISKING`: `turnover_state=DISTRIBUTION` AND at least two of `breadth_state=DETERIORATING`, `leadership_state=DETERIORATING`, `small_mid_state=STRESSED`.
- `EXTERNAL_SHOCK`: `external_shock=VERIFIED` AND source in `{SOURCE_ONGOING,SOURCE_ESCALATING}` AND transmission in `{PENDING_TRANSMISSION,IN_TRANSMISSION,REALIZED_SHOCK}`, unless `ACTIVE_DE_RISKING` already matched.
- High-severity fragility: at least three severe deterioration channels among breadth deteriorating, leadership deteriorating, small/mid stressed, turnover liquidity-withdrawal/distribution; `ACTIVE_DE_RISKING` retains precedence.
- Low-severity fragility: at least two deterioration channels, where mild channel values are breadth divergent/deteriorating, leadership concentrated/deteriorating, small-mid weak/stressed, turnover liquidity-withdrawal; high-severity and shock states retain precedence.
- `REPAIR`: `repair_state=BROAD` or (`local_transmission_state=REPAIRING` and `repair_state in {PARTIAL,BROAD}`), after higher-priority predicates fail. Preserve source fields unchanged.
- `WATCH`: exactly one mild deterioration channel or breadth divergence alone.
- `NORMAL_RISK_ON`: external shock absent, source resolving/transient/unverified as logically compatible, no deterioration channels, all breadth/leadership/small-mid/turnover healthy, `repair_state=NONE`.
- `NORMAL`: valid residual benign/caution configuration after all previous predicates fail.

- [ ] **Step 1: Write failing classifier tests**

Cover all spec cases: unavailable never normal, breadth divergence alone WATCH, low/high fragility, active de-risking precedence, unresolved external shock, repair without source erasure, contradiction fail-closed, score reuse, production authorization false.

- [ ] **Step 2: Run full suite and verify RED**

Expected: FAIL/ERROR because `canonical_state_classifier_v1` does not exist.

- [ ] **Step 3: Implement minimal classifier**

Use pure categorical predicates only; do not inspect returns or numeric market values. Preserve ledger hash and validation diagnostics in output.

- [ ] **Step 4: Run classifier tests and full suite**

Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `research: implement canonical market-state classifier v1`

### Task 3: Formal Evaluation Provenance Gate

**Files:**
- Modify: `research/market_regime_fragility_v0/test_formal_eval_preflight_v1.py`
- Modify: `research/market_regime_fragility_v0/formal_eval_preflight_v1.py`

**Interfaces:**
- Existing manifest keeps `complex_classifier_version` / `complex_classifier_hash`.
- Add required fields: `atomic_ledger_version="ATOMIC_EVIDENCE_LEDGER_V1"`, `classifier_ledger_pit_valid=True`, `classifier_evidence_hash=<non-empty>`.
- Preflight remains evaluation-only and `production_authorized=False`.

- [ ] **Step 1: Add failing preflight tests**

Verify wrong/missing ledger version, false PIT-valid flag, and empty evidence hash each fail closed with distinct reason codes.

- [ ] **Step 2: Run suite and verify RED**

Expected: new tests FAIL against current preflight.

- [ ] **Step 3: Implement the three additional provenance checks**

No change to the still-blocked minimum-effect/sample rules.

- [ ] **Step 4: Run full research suite**

Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `research: require PIT ledger provenance in formal preflight`

### Task 4: CI Wiring, Status, and Final Verification

**Files:**
- Modify: `.github/workflows/market-regime-baseline-v1.yml`
- Modify: `research/market_regime_fragility_v0/CURRENT_STATUS.md`

**Interfaces:**
- CI path filters include the four new ledger/classifier files and the design/plan if needed; test discovery command remains unchanged.
- Status records exact RED/GREEN run IDs and explicitly states that tests prove implementation contracts, not predictive value.

- [ ] **Step 1: Add new files to workflow path filters**

- [ ] **Step 2: Push/commit the CI-wiring change and inspect the resulting full workflow run**

Expected: full discovered research suite PASS.

- [ ] **Step 3: Verify downstream compatibility**

Confirm `state_resolution_v1.py` tests still pass and no production-core path changed.

- [ ] **Step 4: Update CURRENT_STATUS.md with verified evidence**

Record classifier/ledger versions, exact test count/run ID, remaining blockers, and unchanged research-only status.

- [ ] **Step 5: Re-run/inspect final CI for the status commit if workflow path filters trigger; otherwise verify the immediately preceding code/CI commit and record that documentation-only status update does not alter executable state.**

- [ ] **Step 6: Final branch review**

Check diff against spec: no numeric market thresholds, no formal unused set, no Core10/Core13/XH/MA5 change, no production authorization, no HEDGE layer promotion.
