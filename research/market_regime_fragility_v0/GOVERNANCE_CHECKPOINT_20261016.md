# GOVERNANCE CHECKPOINT — 2026-10-16

Status: RESEARCH_ONLY
Production use: PROHIBITED
Formal OOS: NO
Threshold promotion: BLOCKED

This checkpoint records only governance/execution/PIT progress. It does not claim predictive improvement, economic alpha, formal OOS evidence or production readiness.

## 1. A-share tradability and Universe PIT

Implemented research contracts:

- `A_SHARE_TRADABILITY_GATE_V1`
- `UNIVERSE_PIT_SNAPSHOT_V1`

Binding order:

`Universe PIT -> side-specific tradability -> RS/theme/timing ranking`

Key semantic boundaries:

- suspended/no-trade securities cannot be RS survivors merely because price did not fall;
- one-sided locked price-limit securities without executable side liquidity are not assumed fillable;
- account T+1 sell-eligible quantity is separate from market-level RS tradability;
- current/today rules may not be backfilled into historical rows;
- missing policy identity or post-cutoff mutable evidence fails closed.

Historical ST/trading-status source discovery now reuses DAO2 Module D rather than re-downloading by default. Exact frozen audit/artifact identities remain known, but the checked GitHub Actions row carriers currently return 404 / zero retained artifacts. Therefore old audit provenance remains bound while current row replayability does not.

Authoritative recovery boundary:

`SOURCE_RECOVERY_CHECKPOINT_20261016.md`

## 2. Market-structure regime schedule

Version:

`A_SHARE_MARKET_STRUCTURE_REGIME_SCHEDULE_V1`

Artifacts:

- `MARKET_STRUCTURE_SOURCE_BINDING_V1.md`
- `market_structure_regime_schedule_v1.json`
- `market_structure_schedule_v1.py`
- `MARKET_STRUCTURE_REGIME_CONTRACT_V1.md`

Current real status:

`PARTIAL_SOURCE_BOUND / MACHINE_SCHEDULE_VALIDATED / FORMAL_SCOPE_INCOMPLETE`

The schedule is multi-axis and separates board/IPO/taxonomy/transaction-cost/financing/short-hedge/program-trading changes. Formal preflight requires exact version, deterministic schedule hash, PIT-valid schedule and `scope_complete=true`.

The repository's current actual schedule intentionally has `formal_evaluation_scope_complete=false`, so it cannot unlock formal evaluation.

## 3. Downgrade and change control

Version:

`MODULE_DOWNGRADE_CHANGE_CONTROL_V1`

Runtime states are separate from evidence grade/module lifecycle:

`ENABLED / SHADOW / OFF / QUARANTINED`

Integrity breaches such as confirmed look-ahead, frozen-hash drift, semantic source mismatch, provenance/hash mismatch, forbidden missing-data imputation or impossible execution assumptions may trigger fail-closed quarantine without inventing a predictive-performance threshold.

No generic performance downgrade threshold, wall-clock cooldown or data-availability percentage has been invented. Those remain module-specific preregistration requirements.

Frozen production rule changes require explicit authorized human approval. Shadow/Learning cannot silently alter thresholds, weights, states, source precedence, action maps or risk limits.

## 4. Manual override attribution

Version:

`MANUAL_OVERRIDE_LEDGER_V1`

Implemented:

- deterministic pre-decision override record hash;
- deterministic ledger hash;
- duplicate-ID rejection;
- model-output identity preserved;
- override action cannot silently replace model action;
- future/outcome fields forbidden in the pre-decision record;
- formal primary model metric must use unoverridden outputs;
- manifest records override count and ledger hash even when count is zero.

Formal reporting must keep `MODEL_ONLY` and `AS_OPERATED` separable. Human intervention cannot be counted as model correctness.

## 5. Comparator and null distribution

Primary comparator remains:

`BASELINE_1 = MOMENTUM_VOL_REGIME_V1`

Secondary zero-parameter sanity comparator is now explicitly versioned:

`BASELINE_0_NO_REGIME_OVERLAY`

It is a constant-neutral/no-regime-overlay reference and cannot rescue a failure versus BASELINE_1.

Supplementary permutation null:

`BLOCK_PERMUTATION_NULL_V1`

Frozen computational contract:

- outcome block length: 3 sessions, inherited from the primary 3-session horizon;
- paired complex/baseline score path kept aligned;
- outcome blocks shuffled without replacement;
- one-sided Monte-Carlo p-value uses +1 correction;
- default repetitions: 5000;
- deterministic seed: 20261016.

These are inference/reproducibility settings, not trading thresholds or calibrated probabilities.

## 6. Formal preflight additions

Formal preflight now requires, in addition to the existing evidence/PIT/power/classifier contracts:

- `zero_parameter_comparator_version = BASELINE_0_NO_REGIME_OVERLAY`;
- `permutation_null_version = BLOCK_PERMUTATION_NULL_V1`;
- non-empty permutation implementation/provenance hash;
- permutation block length = 3;
- permutation replications = 5000;
- permutation seed = 20261016;
- `change_control_version = MODULE_DOWNGRADE_CHANGE_CONTROL_V1`;
- `manual_override_policy_version = MANUAL_OVERRIDE_LEDGER_V1`;
- primary metric explicitly uses unoverridden model outputs;
- valid manual-override count/hash provenance.

Unit-test fixture values for minimum effect/sample, evaluation-set hashes, comparator hashes or permutation hashes are contract fixtures only and are not project thresholds/evidence.

## 7. Fresh verification evidence

Latest code-level verification before this checkpoint:

- RED preflight comparator/permutation run: `38867354329`, exactly five new provenance checks failed against the old preflight as expected;
- GREEN run: `38867540890`;
- GREEN job: `116863732107`;
- full workflow command: `python -m unittest discover -s research/market_regime_fragility_v0 -p "test_*.py" -v`;
- log result: `Ran 115 tests` / `OK`.

Earlier relevant GREEN checkpoints in this same branch include:

- A-share tradability / Universe PIT integrated: `38861832872`, 76 tests OK;
- T+1/RS semantic correction: `38862271997`, 76 tests OK;
- market-structure schedule/preflight integration: `38865290037`, 86 tests OK;
- manual override executable ledger: `38866477410`, 95 tests OK;
- block-permutation implementation: `38867104379`, 109 tests OK;
- explicit BASELINE0/BASELINE1 identities: `38867258173`, success.

These runs verify executable contracts, not predictive value.

## 8. Remaining objective blockers

No formal promotion/economic evaluation is authorized because the following remain unresolved:

1. `PORTFOLIO_HARD_RISK_GUARD_V1` numeric mandate is not frozen.
2. Risk-score -> action/exposure map is not frozen.
3. `minimum_effect_delta_tau` remains unjustified/unfrozen at project level.
4. `minimum_sample_required` remains unfrozen at project level.
5. Current actual market-structure schedule remains partial, not formal-scope complete.
6. Historical row-level Universe/ST/tradestatus/RAW/liquidity carriers checked today are not currently retrievable from expired GitHub Actions artifacts; source/audit identity alone is insufficient for row replay.
7. Decision-date board/venue/listing-delist and immutable price-limit row integration remain incomplete.
8. Side-specific executable-liquidity/capacity history remains unresolved.
9. Mutable adjusted-price/corporate-action and vendor-field archive completeness remains unproven.
10. Raw numeric PIT observations -> Atomic Evidence Ledger categorical extractor remains unfrozen/unimplemented end-to-end.
11. `HEDGE / CAPITAL ROTATION` remains an unimplemented data layer.

## 9. Direction lock

Until a blocker receives genuinely new admissible evidence:

- do not open a new formal unused evaluation set;
- do not rerun expired artifact searches without a new carrier lead;
- do not tune thresholds on consumed windows;
- do not invent hard-risk numbers, performance downgrade boundaries or cooldown durations;
- do not promote research layers into Core10/Core13;
- keep `XH_REGIME_GATE_V0` shadow-only;
- keep standalone MA5 exit rejected for promotion;
- keep production Core unchanged.

Next autonomous work should prioritize immutable row-source recovery only when a new carrier appears, otherwise continue non-numeric hard-risk/action-map contract preparation and PIT archive provenance work that does not require fabricated parameters.
