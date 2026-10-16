# Atomic Evidence Ledger → Canonical Market-State Classifier V1 — Design

Date: 2026-10-16
Branch: `research/market-regime-fragility-v0`
Status: DESIGN_APPROVED / SPEC_REVIEW_PENDING
Production use: PROHIBITED
Formal OOS: NO

## 1. Purpose

Build an auditable bridge from point-in-time market evidence into the research model's canonical market state without inventing retrospective numeric thresholds or allowing downstream logic to reinterpret missing evidence as benign.

This subsystem sits between raw market observations and the existing categorical resolver:

`Raw PIT Evidence -> Atomic Evidence Ledger -> Canonical State Classifier -> RISK_EVIDENCE_SCORE -> Veto / Router`

The subsystem is research-only. It does not change Core10/Core13, `XH_REGIME_GATE_V0`, the rejected standalone MA5 exit rule, A-share execution constraints, or portfolio hard-risk limits.

## 2. Design goals

1. Preserve PIT provenance for every evidence item.
2. Separate raw observations from categorical interpretation.
3. Fail closed on missing, stale, contradictory, or unauditable required evidence.
4. Produce deterministic, versioned canonical-state outputs.
5. Avoid double-counting source, transmission, breadth, and regime evidence.
6. Avoid outcome-derived threshold tuning on consumed historical windows.
7. Keep the classifier explainable through explicit reason codes and evidence hashes.
8. Make future formal unused-set evaluation mechanically reproducible.

## 3. Non-goals

This version will not:

- infer calibrated crash/downside probabilities;
- optimize numeric thresholds on historical returns;
- infer specific institutional identity from flow data;
- implement the `HEDGE / CAPITAL ROTATION` data layer;
- set production position sizes or hard-risk limits;
- create an execution engine;
- open or consume a new formal unused evaluation set;
- authorize production use.

## 4. Architectural boundary

### 4.1 Raw PIT evidence

Source-specific numeric/raw observations remain outside the classifier core. Examples include:

- completed-session index returns;
- breadth / advancer-decliner counts;
- small/mid-cap relative performance;
- turnover and turnover change;
- leadership concentration / continuation evidence;
- verified external event records;
- source-persistence evidence;
- local transmission evidence;
- repair / absorption evidence.

Raw inputs must retain their original timestamp and source/provenance identifiers.

### 4.2 Atomic Evidence Ledger

The ledger is the canonical input interface to the classifier. Each field contains:

- categorical value;
- `observed_at` timestamp;
- `decision_cutoff` timestamp;
- provenance/source reference;
- PIT validity flag;
- optional reason/details;
- deterministic evidence hash contribution.

Initial categorical domains:

- `external_shock`: `VERIFIED | ABSENT | UNAVAILABLE`
- `shock_source_persistence`: `SOURCE_RESOLVING | SOURCE_ONGOING | SOURCE_ESCALATING | SOURCE_TRANSIENT_REPRICING | SOURCE_UNVERIFIED`
- `local_transmission_state`: `PENDING_TRANSMISSION | IN_TRANSMISSION | REALIZED_SHOCK | REPAIRING | UNRESOLVED`
- `breadth_state`: `HEALTHY | DIVERGENT | DETERIORATING | UNAVAILABLE`
- `leadership_state`: `HEALTHY | CONCENTRATED | DETERIORATING | UNAVAILABLE`
- `small_mid_state`: `HEALTHY | WEAK | STRESSED | UNAVAILABLE`
- `turnover_state`: `HEALTHY | DISTRIBUTION | LIQUIDITY_WITHDRAWAL | UNAVAILABLE`
- `repair_state`: `NONE | PARTIAL | BROAD | UNAVAILABLE`

These are evidence facts/categories, not canonical market states.

## 5. Ledger validity contract

A ledger is valid only if:

1. all required fields for the attempted resolution path are present;
2. every used item is PIT-valid at `decision_cutoff`;
3. `observed_at <= decision_cutoff` for every used item;
4. provenance/source is non-empty;
5. enum value belongs to the versioned domain;
6. deterministic evidence hash can be computed;
7. no future-derived field is used.

If a field is unavailable, the ledger stores `UNAVAILABLE` / `UNRESOLVED` explicitly. Missing evidence must never be rewritten as `HEALTHY`, `ABSENT`, or `NORMAL`.

## 6. Canonical output states

Classifier V1 may emit only the already-governed canonical states:

- `NORMAL_RISK_ON`
- `NORMAL`
- `INTERNAL_FRAGILITY_WATCH`
- `INTERNAL_FRAGILITY_CONFIRMED_LOW_SEVERITY`
- `INTERNAL_FRAGILITY_CONFIRMED_HIGH_SEVERITY`
- `EXTERNAL_SHOCK`
- `ACTIVE_DE_RISKING`
- `REPAIR`
- `UNAVAILABLE` (classifier failure / insufficient valid evidence; not mapped to a risk score)

No new state is introduced by this implementation.

## 7. Resolution hierarchy

The classifier uses a deterministic precedence hierarchy for state resolution, while preserving all atomic evidence unchanged in the ledger.

Priority order:

1. `ACTIVE_DE_RISKING`
2. `EXTERNAL_SHOCK`
3. `INTERNAL_FRAGILITY_CONFIRMED_HIGH_SEVERITY`
4. `INTERNAL_FRAGILITY_CONFIRMED_LOW_SEVERITY`
5. `REPAIR`
6. `INTERNAL_FRAGILITY_WATCH`
7. `NORMAL_RISK_ON`
8. `NORMAL`
9. `UNAVAILABLE`

This priority controls only the single canonical market-state output. It does not erase or rewrite lower-priority evidence.

## 8. V1 rule philosophy

V1 will use only categorical evidence relationships already documented by governance and research semantics. It will not convert raw numbers into categories.

Examples:

### 8.1 Active de-risking

Eligible when the ledger already contains evidence consistent with broad active selling, such as:

- `turnover_state = DISTRIBUTION`; and
- broad risk evidence is deteriorating/stressed rather than healthy.

Exact qualifying combinations will be explicit and finite in the classifier contract. No numeric turnover threshold is introduced here.

### 8.2 External shock

Eligible when:

- `external_shock = VERIFIED`; and
- source/transmission evidence indicates unresolved local risk rather than a completed broad repair.

`SOURCE_RESOLVING` and `REPAIRING/BROAD repair` must not be silently treated the same as `SOURCE_ONGOING/ESCALATING`.

### 8.3 Internal fragility

Breadth divergence alone cannot resolve to confirmed fragility.

Confirmed fragility requires multiple independent deterioration channels among:

- breadth;
- leadership;
- small/mid-cap condition;
- turnover/liquidity state;
- persistence/repair failure where represented.

Low versus high severity must be determined by categorical severity/persistence combinations, not by numeric thresholds introduced after seeing outcomes.

### 8.4 Repair

`REPAIR` requires evidence of repair/acceptance and must not simply mean `not currently falling`.

It cannot erase an ongoing external source from the ledger. Downstream veto logic remains responsible for the coexistence of `REPAIR` with unresolved external-source evidence.

### 8.5 Normal / risk-on

A normal state is only available when required evidence is valid and there is affirmative absence of material deterioration. `UNAVAILABLE != NORMAL` remains binding.

## 9. Reason codes

Every classifier result must include machine-readable reason codes. Initial categories:

- `ACTIVE_DISTRIBUTION_CONFIRMED`
- `VERIFIED_EXTERNAL_SHOCK_UNRESOLVED`
- `MULTI_CHANNEL_FRAGILITY_HIGH`
- `MULTI_CHANNEL_FRAGILITY_LOW`
- `FRAGILITY_WATCH_ONLY`
- `BROAD_REPAIR_CONFIRMED`
- `NORMAL_EVIDENCE_SET`
- `RISK_ON_EVIDENCE_SET`
- `REQUIRED_EVIDENCE_UNAVAILABLE`
- `STALE_OR_POST_CUTOFF_EVIDENCE`
- `INVALID_ENUM_VALUE`
- `CONTRADICTORY_REQUIRED_EVIDENCE`

Reason codes are part of the classifier version contract.

## 10. Output schema

The classifier returns at minimum:

```text
classifier_version
canonical_market_state
risk_evidence_score | null
reason_codes[]
missing_fields[]
invalid_fields[]
evidence_hash
full_classifier_resolution_available
production_authorized = false
```

The risk score mapping must reuse `RISK_EVIDENCE_SCORE_MAPPING_V1`; the classifier must not define a second mapping.

## 11. Evidence hashing

The evidence hash must be deterministic over the versioned canonical representation of:

- field names;
- categorical values;
- timestamps;
- provenance IDs;
- PIT-validity flags;
- classifier version.

Field ordering must be canonicalized before hashing. Semantically identical ledgers must produce the same hash; any material input/provenance change must change the hash.

## 12. Conflict handling

Contradictory evidence is not resolved by arbitrary narrative preference.

Rules:

1. preserve all conflicting atomic evidence;
2. emit contradiction reason code where the combination invalidates deterministic resolution;
3. return `UNAVAILABLE` if the conflict touches a required discriminator and cannot be resolved by the versioned hierarchy;
4. never coerce a contradiction to `NORMAL`;
5. never modify source fields to make the selected canonical state look internally consistent.

The existing `state_resolution_v1.py` remains downstream and continues to apply veto/router semantics after the canonical state is resolved.

## 13. Testing strategy

Implementation must follow TDD.

### RED tests first

Create tests for:

1. missing required evidence -> `UNAVAILABLE`;
2. post-cutoff timestamp -> fail closed;
3. unavailable evidence never becomes NORMAL;
4. breadth divergence alone -> at most WATCH;
5. multi-channel low-severity fragility -> LOW_SEVERITY;
6. distribution + broad deterioration -> ACTIVE_DE_RISKING;
7. verified external shock with ongoing/escalating source -> EXTERNAL_SHOCK unless a higher-priority active-de-risking state applies;
8. broad repair -> REPAIR without erasing source persistence;
9. deterministic evidence hash;
10. input/provenance mutation changes evidence hash;
11. unknown enum -> fail closed;
12. contradictory required evidence -> `UNAVAILABLE` when unresolved;
13. canonical output reuses existing risk-score mapping;
14. `production_authorized` always false.

### GREEN implementation

Implement the minimum code required to satisfy the locked tests. No empirical return data are used in unit tests.

## 14. CI integration

Add the new classifier and tests to `.github/workflows/market-regime-baseline-v1.yml` path triggers and test discovery.

Expected workflow verification sequence:

1. RED commit/run with missing implementation;
2. GREEN commit/run after implementation;
3. full discovered suite PASS;
4. update `CURRENT_STATUS.md` with exact run IDs and scope limitations.

CI success proves contract execution only, not predictive validity.

## 15. Formal-evaluation interaction

The classifier version and implementation hash must become required fields in the formal-evaluation manifest.

The formal preflight must continue to reject evaluation if:

- classifier version/hash is missing;
- classifier output was not generated from a PIT-valid ledger;
- minimum effect/sample requirement remains unfrozen;
- evaluation set is not genuinely unused;
- definitions were not locked before set opening.

No new unused set is opened as part of this implementation.

## 16. Minimum-effect / power gate

This subsystem does not solve the economic-effect threshold problem.

The following remain blocked:

- `minimum_effect_delta_tau = NOT_FROZEN`
- `minimum_sample_required = NOT_FROZEN`

The classifier may be implemented and tested while these remain blocked, but no formal promotion comparison may begin until the power gate is independently closed.

## 17. Files expected in implementation

Planned research-branch files:

- `research/market_regime_fragility_v0/atomic_evidence_ledger_v1.py`
- `research/market_regime_fragility_v0/test_atomic_evidence_ledger_v1.py`
- `research/market_regime_fragility_v0/canonical_state_classifier_v1.py`
- `research/market_regime_fragility_v0/test_canonical_state_classifier_v1.py`
- updates to `formal_eval_preflight_v1.py` and tests if classifier provenance checks are added;
- update `.github/workflows/market-regime-baseline-v1.yml`;
- update `CURRENT_STATUS.md` after verified CI.

No production-core file is in scope.

## 18. Acceptance criteria

The implementation phase is complete only when all of the following are true:

1. atomic ledger validation is deterministic and fail-closed;
2. canonical classifier introduces no new numeric market thresholds;
3. canonical states are restricted to the existing versioned set;
4. reason codes and evidence hash are emitted;
5. `UNAVAILABLE != NORMAL` is enforced by tests;
6. downstream `state_resolution_v1.py` remains compatible;
7. full research CI passes;
8. `CURRENT_STATUS.md` records exact RED/GREEN evidence;
9. no unused formal evaluation set has been opened;
10. status remains `RESEARCH_ONLY / FORMAL_OOS=NO / PRODUCTION_USE=PROHIBITED`.

## 19. Deferred work

Deferred to later versions / separate designs:

- raw numeric evidence -> atomic category extraction thresholds;
- live data wiring;
- HEDGE / CAPITAL ROTATION implementation;
- economic decision-utility mapping;
- numeric exposure policy;
- Monte Carlo power derivation after minimum effect freeze;
- A-share execution engine;
- portfolio hard-risk numeric limits;
- production promotion.
