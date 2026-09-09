# GP Audit Remediation V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen the V4.82 evidence chain with exact byte identity, explicit readiness semantics, sampled PIT/ST evidence labeling, fixed-probe namespacing, and a repository-resident audit manifest before any BaoStock 847 scale-out.

**Architecture:** Add a small reusable audit-evidence module that computes deterministic file/schema identities and validates evidence records. Existing RAW and Liquidity materializers emit exact-byte bindings; the Formal finalizer consumes and cross-checks those bindings. Separate repository-resident artifacts describe status semantics, PIT/ST sample coverage, fixed-probe identities, and unresolved governance/permanent-byte blockers without changing strategy or OOS state.

**Tech Stack:** Python 3.12/3.11, pandas, pyarrow, unittest, GitHub Actions, JSON/CSV evidence artifacts.

**Spec:** `docs/superpowers/specs/2026-09-09-audit-remediation-v1-design.md`

## Global Constraints

- Base lineage is exactly `gp/gp12-formal-input-readiness-v1@b815773d00e4c6bf775b3ce111aef3fc458cd741`.
- No BaoStock 847 scale-out.
- No strategy factor/parameter changes and no GP12 approval.
- No OOS metric consumption; `oos_metrics_allowed=false` throughout this remediation.
- Existing numerical/row-level gates remain mandatory; byte identity is additive.
- Large parquet bytes remain outside normal Git; Actions-only bytes must remain explicitly non-permanent.
- PIT/ST external evidence is labeled sampled unless every observed transition is independently evidenced.
- Bare `fixed5` is forbidden in promotion artifacts.

---

### Task 1: Audit identity primitives

**Files:**
- Create: `scripts/audit_evidence_v1.py`
- Create: `scripts/test_audit_evidence_v1.py`

**Interfaces:**
- Produces: `sha256_file(path) -> str`, `schema_fingerprint(frame) -> str`, `validate_sha256(value) -> bool`, `validate_evidence_manifest(doc) -> list[str]`, `validate_status_model(doc) -> list[str]`.

- [ ] **Step 1: Write failing tests** covering stable file SHA, deterministic schema fingerprint, malformed SHA rejection, conflicting evidence identity rejection, Actions-only bytes forbidden from claiming permanence, and upward status inference rejection.
- [ ] **Step 2: Run** `cd scripts && python -m unittest -v test_audit_evidence_v1.py` and verify RED because `audit_evidence_v1` does not exist.
- [ ] **Step 3: Implement minimal production module** with streaming SHA256, deterministic JSON schema signature from ordered column names/dtypes, strict evidence classes, blocker generation, and five-state readiness validation.
- [ ] **Step 4: Re-run the focused tests** and require all PASS.
- [ ] **Step 5: Commit** `test/feat(audit): add evidence identity primitives`.

### Task 2: Hash-bind Full RAW

**Files:**
- Modify: `scripts/sohu_full_panel_v482.py`
- Modify: `scripts/test_sohu_full_panel_v482.py`

**Interfaces:**
- Consumes: `sha256_file`, `schema_fingerprint` from Task 1.
- Produces in `SOHU_RAW_FULL_AUDIT_V482.json`: `full_parquet_sha256`, `full_parquet_bytes`, `schema_fingerprint`.

- [ ] **Step 1: Add failing tests** asserting merge output contains valid SHA/byte/schema fields and that a one-byte file mutation changes the SHA.
- [ ] **Step 2: Run focused RAW tests** and verify RED because current report lacks these fields.
- [ ] **Step 3: Modify merge flow** so the parquet is written first, then hashed/stat-ed, then the audit JSON is emitted with exact identities.
- [ ] **Step 4: Run RAW focused tests plus `test_audit_evidence_v1.py`** and require PASS.
- [ ] **Step 5: Commit** `feat(v482): bind full RAW parquet identity`.

### Task 3: Hash-bind Liquidity inputs and panel

**Files:**
- Modify: `scripts/liquidity_apply_v482.py`
- Modify: `scripts/test_liquidity_apply_v482.py`

**Interfaces:**
- Produces in `LIQUIDITY_80M_APPLY_AUDIT_V482.json`: `panel_parquet_sha256`, `panel_parquet_bytes`, `schema_fingerprint`, `input_full_raw_sha256`, `input_pitst_sha256`.
- `run()` computes input hashes before loading and output hash after writing.

- [ ] **Step 1: Add failing tests** for output panel identity, RAW/PIT-ST input hash propagation, and mutation mismatch behavior.
- [ ] **Step 2: Run focused Liquidity tests** and verify RED.
- [ ] **Step 3: Implement minimal hash capture** without changing eligibility math.
- [ ] **Step 4: Run Liquidity, RAW, and evidence primitive tests** and require PASS.
- [ ] **Step 5: Commit** `feat(v482): bind liquidity panel and inputs`.

### Task 4: Make Formal require byte bindings

**Files:**
- Modify: `scripts/formal_readiness_finalize_v482.py`
- Modify: `scripts/test_formal_readiness_finalize_v482.py`

**Interfaces:**
- Formal `byte_bindings` includes `full_raw_sha256`, `liquidity_panel_sha256`, `pitst_sha256`, and available calendar/QFQ identity fields.
- `validate_market_data_readiness()` rejects missing/malformed bindings and RAW/Liquidity cross-hash mismatches.

- [ ] **Step 1: Add failing tests** proving current summary-only RAW/Liquidity evidence is rejected, mismatched RAW hashes fail, malformed SHA fails, and matching bindings succeed.
- [ ] **Step 2: Run focused Formal tests** and verify RED against current permissive behavior.
- [ ] **Step 3: Add strict byte-binding validation** while preserving all current numeric invariants and `oos_metrics_allowed=false`.
- [ ] **Step 4: Run Formal + RAW + Liquidity regression tests** and require PASS.
- [ ] **Step 5: Commit** `feat(v482): require byte-bound Formal market data`.

### Task 5: PIT/ST sample coverage and fixed-probe registry

**Files:**
- Create: `scripts/audit_semantics_v1.py`
- Create: `scripts/test_audit_semantics_v1.py`
- Create: `data/AUDIT_STATUS_MODEL_V1.json`
- Create: `data/FIXED_PROBE_REGISTRY_V1.json`
- Create: `data/PIT_ST_EVIDENCE_COVERAGE_V1.json`

**Interfaces:**
- Produces exact baseline facts: 233 transition symbols, 386 transitions, 3 independently checked symbols, 6 independently checked transitions, coverage `6/386`.
- Registers `QFQ_SEMANTIC_FIXED5_V477` and `RAW_PITST_SOURCE_FIXED5_V482` with exact ordered symbols and sorted-symbol SHA256.

- [ ] **Step 1: Write failing tests** for ambiguous bare `fixed5`, wrong symbol-set hash, false full-audit claim, and status-state upward inference.
- [ ] **Step 2: Run tests** and verify RED.
- [ ] **Step 3: Implement semantic validators and create the three repository data artifacts** with fail-closed labels.
- [ ] **Step 4: Run focused tests** and require PASS.
- [ ] **Step 5: Commit** `feat(audit): separate readiness and sampled evidence semantics`.

### Task 6: Repository-resident evidence manifest and governance blockers

**Files:**
- Create: `scripts/build_audit_manifest_v1.py`
- Create: `scripts/test_build_audit_manifest_v1.py`
- Create: `data/AUDIT_EVIDENCE_SOURCES_V1.json`
- Create: `.github/workflows/audit-remediation-v1.yml`

**Interfaces:**
- Builds `AUDIT_EVIDENCE_MANIFEST_V1.json` and copies small evidence into `evidence/audit-remediation-v1/` within CI artifact output.
- Manifest includes canonical base SHA, source run/artifact/digest/head metadata, exact hashes, permanence flags, and blockers `PERMANENT_BYTE_ARCHIVE_OPEN` and `REPOSITORY_BRANCH_PROTECTION_OPEN` where applicable.

- [ ] **Step 1: Add failing tests** for missing lineage, malformed artifact digest, conflicting evidence identity, expiring bytes falsely marked permanent, and absence of required governance blockers.
- [ ] **Step 2: Run tests** and verify RED.
- [ ] **Step 3: Implement manifest builder and workflow**. Workflow downloads only the exact frozen runs needed for the first remediation census, verifies available hashes, runs tests, builds the manifest, and uploads `gp-audit-remediation-v1` with `oos_metrics_allowed=false`.
- [ ] **Step 4: Run all new local unit tests** and require PASS.
- [ ] **Step 5: Commit** `feat(audit): add fail-closed evidence manifest`.

### Task 7: Full regression and adversarial acceptance

**Files:**
- Modify only if a regression exposes a remediation defect; do not relax tests.
- Create: `docs/evidence/AUDIT_REMEDIATION_V1_CHECKPOINT.md`

**Interfaces:**
- Produces final remediation checkpoint with separate booleans for identity binding, permanence, Formal data readiness, feature readiness, strategy readiness, model freeze, OOS admission, and BaoStock scale-out permission.

- [ ] **Step 1: Run** all remediation tests plus existing Formal/OOS/RAW/Liquidity/PIT-ST/QFQ regression tests referenced by current production workflows.
- [ ] **Step 2: Run the GitHub Actions remediation workflow** on `gp/audit-remediation-v1`; inspect job steps and artifact digest.
- [ ] **Step 3: Download the generated artifact and independently recompute key JSON/file hashes where bytes are available.**
- [ ] **Step 4: Perform adversarial assertions:** one-byte/hash mutation fails; sampled PIT/ST cannot claim full independent audit; `FORMAL_DATA_READY` cannot imply Strategy/Model/OOS; Actions-only large bytes keep permanence blocker; BaoStock scale-out stays blocked until acceptance passes.
- [ ] **Step 5: Write `AUDIT_REMEDIATION_V1_CHECKPOINT.md`** with exact run/commit/artifact identities and unresolved blockers.
- [ ] **Step 6: Commit** `docs(audit): record remediation V1 adversarial checkpoint`.

## Plan self-review

- Spec coverage: all design sections map to Tasks 1–7; permanent large-byte storage is deliberately represented as unresolved rather than implemented.
- Placeholder scan: no TBD/TODO/“implement later” placeholders.
- Type consistency: RAW/Liquidity/Formal use the same SHA256 string convention; readiness and evidence semantics are separate from byte identity primitives.
- Safety: no task opens OOS, freezes a model, changes GP12 strategy logic, or scales BaoStock to 847.
