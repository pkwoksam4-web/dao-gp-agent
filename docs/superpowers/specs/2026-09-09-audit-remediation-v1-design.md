# GP Audit Remediation V1 — Design

Date: 2026-09-09
Status: DESIGN_FROZEN_FOR_REVIEW
Base lineage: `gp/gp12-formal-input-readiness-v1@b815773d00e4c6bf775b3ce111aef3fc458cd741`
Implementation branch: `gp/audit-remediation-v1`

## 1. Purpose

Repair the evidence-chain weaknesses found by the 2026-09-09 adversarial review before any BaoStock 847 scale-out, model freeze, or OOS execution.

This remediation does **not** change the historical strategy, reconstruct missing GP V1.1 logic, tune GP12, consume OOS metrics, or broaden the 847 universe. It only strengthens provenance, byte identity, status semantics, and audit labeling.

## 2. Problem statement

The current project has strong mathematical and row-level gates, but several evidence-governance weaknesses remain:

1. Final Formal readiness validates RAW/Liquidity summaries and fixed counts but does not bind the final full parquet bytes by SHA256.
2. Several critical upstream evidence objects live only as GitHub Actions artifacts with 30-day retention.
3. `FORMAL_READY_V482` can be misread as strategy/model/OOS readiness.
4. PIT/ST independent transition evidence covers 6 of 386 observed state transitions, while current wording can be read as stronger than sample validation.
5. The term `fixed5` is overloaded across different probes and symbol sets.
6. Existing branches are not a safe canonical production lineage; `main` and the active research chain have diverged.
7. Some components report a local `CLOSED` state while source-byte identity is enforced only by the surrounding workflow.

## 3. Design choice

### Selected: Evidence Capsule + Hash-bound Gate

Create a remediation layer that:

- produces a permanent, repository-resident evidence manifest for all small critical audit documents;
- records exact SHA256, byte count, schema/row facts, source run, artifact id/name, and artifact digest for large binary evidence;
- requires downstream Formal promotion to bind the exact RAW and Liquidity file hashes, not only their audit summaries;
- separates evidence preservation from byte preservation: if a large upstream artifact still exists only under expiring Actions retention, the manifest records that fact and leaves `PERMANENT_BYTE_ARCHIVE_OPEN` as a blocker;
- introduces explicit readiness stages and prevents stronger states from being inferred from weaker ones;
- relabels PIT/ST independent validation as sampled evidence with exact coverage counts;
- namespaces all fixed-5 probes by purpose and exact symbol-set hash;
- records canonical branch/head lineage in an immutable audit manifest.

### Rejected alternative A: Commit all parquet bytes into Git

Rejected because it would bloat normal Git history, degrade cloning and review, and is unnecessary for source control. Large-byte permanence should use a dedicated immutable archive backend, not ordinary Git blobs.

### Rejected alternative B: Hashes only

Rejected because a hash without a source/artifact digest, file size, row/schema facts, and re-materialization lineage is too weak for forensic reconstruction after artifact expiry.

## 4. New artifacts

### 4.1 `AUDIT_EVIDENCE_MANIFEST_V1.json`

Repository-resident canonical evidence inventory. Required fields:

- `artifact`, `version`, `generated_at_utc`
- `canonical_lineage`
  - repository
  - base_branch
  - base_head_sha
  - remediation_branch
  - remediation_head_sha when generated in CI
- `status_model`
- `evidence_items[]`
  - logical_name
  - class: `SMALL_PERSISTED` or `LARGE_HASH_BOUND`
  - source_run_id
  - source_artifact_id
  - source_artifact_name
  - source_artifact_digest
  - source_head_sha when known
  - file_name
  - sha256
  - bytes
  - row_count when applicable
  - schema_fingerprint when applicable
  - persisted_repository_path for small evidence
  - permanent_bytes_available
  - expiry_at when bytes are still Actions-only
- `blockers[]`
- `formal_promotion_allowed`
- `model_freeze_allowed`
- `oos_metrics_allowed`

The manifest is fail-closed: missing hash, malformed digest, inconsistent row facts, duplicate logical names, duplicate source identities with conflicting hashes, or an unknown evidence class is an error.

### 4.2 `AUDIT_STATUS_MODEL_V1.json`

Defines only these ordered readiness states:

1. `FORMAL_DATA_READY`
2. `FEATURE_INPUT_READY`
3. `STRATEGY_READY`
4. `MODEL_FROZEN`
5. `OOS_ADMITTED`

Rules:

- No state implies the next state.
- `FORMAL_DATA_READY` explicitly means historical market-data/provenance readiness only.
- GP12 `UNAPPROVED` candidate can never produce `STRATEGY_READY`.
- Missing historical GP V1.1 strategy code/parameters/factor definitions keeps `STRATEGY_READY=false`.
- OOS remains impossible unless all lower gates are explicit and hash-linked.

### 4.3 `PIT_ST_EVIDENCE_COVERAGE_V1.json`

Records:

- total observed transition symbols
- total observed transitions
- independently crosschecked symbols
- independently crosschecked transitions
- exact sampled transition ids
- transition coverage percentage
- symbol coverage percentage
- label `INDEPENDENT_SAMPLE_CROSSCHECK`

The artifact must never emit a field named `independent_full_transition_audit_pass` unless every observed transition is independently evidenced.

### 4.4 `FIXED_PROBE_REGISTRY_V1.json`

Every small probe receives a unique semantic id and exact symbol hash.

Initial required registrations:

- `QFQ_SEMANTIC_FIXED5_V477`
- `RAW_PITST_SOURCE_FIXED5_V482`

Each entry includes ordered symbols, sorted-symbol SHA256, purpose, source branch/run, and a rule forbidding the bare label `fixed5` in promotion artifacts.

## 5. Hash binding changes

### 5.1 Full RAW

`SOHU_RAW_FULL_AUDIT_V482.json` must include:

- `full_parquet_sha256`
- `full_parquet_bytes`
- deterministic schema fingerprint
- existing row/date/quality facts

The hash is calculated after the final parquet is written.

### 5.2 Liquidity panel

`LIQUIDITY_80M_APPLY_AUDIT_V482.json` must include:

- `panel_parquet_sha256`
- `panel_parquet_bytes`
- deterministic schema fingerprint
- `input_full_raw_sha256`
- `input_pitst_sha256`

### 5.3 Final Formal

`FORMAL_READINESS_FINAL_V482.json` must include a `byte_bindings` object containing at minimum:

- Full RAW parquet SHA256
- Liquidity panel parquet SHA256
- PIT/ST source SHA256
- calendar SHA256
- relevant QFQ/source-census identity already used by the full-path audit

Formal finalization must reject:

- missing bindings;
- invalid SHA format;
- mismatch between audit JSON and actual downloaded file;
- RAW hash mismatch between RAW and Liquidity audit;
- PIT/ST hash mismatch between Liquidity and Formal inputs.

The existing numerical checks remain mandatory; byte bindings are additive, not a replacement.

## 6. Permanent evidence policy

### Small evidence

Critical JSON/CSV manifests and audit summaries required to explain a promoted gate are copied into a repository-resident `evidence/audit-remediation-v1/` capsule with exact SHA256 recorded in the top-level manifest.

### Large evidence

Large parquet/raw binary evidence is not committed to normal Git in V1. Instead:

- exact file SHA256/bytes/schema/rows are permanent in Git;
- source Actions artifact id/name/digest/run/head and expiry are recorded;
- `permanent_bytes_available=false` until a non-expiring immutable byte archive is provisioned;
- top-level blocker `PERMANENT_BYTE_ARCHIVE_OPEN` remains visible.

This means V1 closes **identity binding**, but does not falsely claim that expiring large bytes have already been permanently archived.

## 7. Canonical lineage rule

Audit Remediation V1 starts only from:

`gp/gp12-formal-input-readiness-v1@b815773d00e4c6bf775b3ce111aef3fc458cd741`

The manifest records this base explicitly. No evidence produced from the older BaoStock fixed5 branch may be promoted directly into the canonical chain. Fixed5 results may be referenced as probe evidence only after their source head/run and exact symbol registry entry are recorded.

Because repository branch protection is currently off, the remediation cannot claim organizational branch protection. Instead it must fail closed on lineage identity inside CI and emit `REPOSITORY_BRANCH_PROTECTION_OPEN` as a governance blocker until external protection is enabled.

## 8. PIT/ST semantics correction

The existing BaoStock PIT/ST dataset remains usable; this design does not invalidate it.

However, terminology changes:

- old semantic implication: `transition_crosscheck_all_pass`
- new externally visible label: `independent_sample_transition_crosscheck_pass`

Current observed baseline to lock in tests:

- 233 symbols with at least one observed ST transition
- 386 observed transitions
- 3 independently crosschecked symbols
- 6 independently crosschecked transitions
- event coverage approximately 1.5544%

If future data changes these counts, CI must require an explicit manifest update rather than silently accepting drift.

## 9. Local-vs-workflow closure rule

A reusable library function may report only a local semantic result unless it itself validates source identity.

Examples:

- Liquidity replay function-level result becomes `SEMANTICS_REPRODUCED`.
- Workflow may promote it to `FROZEN_SOURCE_REPRODUCED` only after exact source SHA and shape checks pass.

This prevents direct Python calls from masquerading as workflow-grade evidence.

## 10. Error handling

All new gates fail closed.

Hard failures include:

- missing or malformed SHA256;
- file hash mismatch;
- source artifact digest mismatch;
- duplicate or conflicting evidence identity;
- missing canonical lineage;
- unknown readiness status;
- promotion from Formal directly to Strategy/Model/OOS;
- bare ambiguous `fixed5` promotion label;
- claim of full PIT/ST independent validation without full transition coverage.

Governance conditions that are real but not locally fixable remain explicit blockers instead of being ignored, including unprotected branches and non-permanent large-byte storage.

## 11. Testing strategy

TDD is mandatory.

### Contract tests

1. RED: current RAW audit lacks full parquet hash.
2. RED: current Liquidity audit lacks panel/input hashes.
3. RED: Formal finalizer accepts summary-only market-data evidence.
4. RED: PIT/ST sample can be mislabeled as full independent audit.
5. RED: bare `fixed5` has ambiguous registry meaning.
6. RED: source-semantic `CLOSED` can be emitted without source SHA at function level.

### Positive tests

1. Exact RAW bytes produce stable SHA/bytes/schema fingerprint.
2. One-byte RAW mutation fails Formal binding.
3. Exact Liquidity panel binds RAW and PIT/ST identities.
4. One-byte/one-hash input mutation fails.
5. Status state machine rejects upward inference.
6. PIT/ST coverage artifact emits 233/386 and 3/6 baseline facts.
7. Fixed-probe registry distinguishes both fixed5 sets.
8. Evidence manifest rejects expiring Actions-only bytes as `permanent_bytes_available=true`.
9. Canonical lineage must equal the approved base SHA.
10. All existing Formal/OOS regression tests continue to pass with OOS still off.

## 12. Acceptance criteria

Audit Remediation V1 is complete only when:

- all new tests pass;
- existing relevant regressions pass;
- RAW, Liquidity, PIT/ST and Formal exact-byte identities are chained;
- small critical evidence is repository-persisted;
- large-byte permanence is truthfully represented;
- PIT/ST validation wording reflects sample coverage;
- fixed5 ambiguity is eliminated;
- canonical lineage is explicit;
- status model prevents Formal/Strategy/Model/OOS conflation;
- `model_freeze_allowed=false` remains true unless separately satisfied by authoritative strategy recovery;
- `oos_metrics_allowed=false` remains true;
- BaoStock 847 scale-out remains blocked until this remediation itself passes adversarial review.

## 13. Non-goals

- no 847 BaoStock expansion;
- no new strategy factors;
- no GP12 approval;
- no fitting/calibration;
- no OOS data consumption or metrics;
- no modification of the frozen OOS intent window;
- no claim that Actions artifact bytes are permanently archived until a real non-expiring byte store exists.
