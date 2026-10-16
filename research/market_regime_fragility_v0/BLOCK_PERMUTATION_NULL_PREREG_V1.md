# BLOCK PERMUTATION NULL PREREG V1

Status: GOVERNANCE_FROZEN / IMPLEMENTED_RESEARCH_CONTRACT
Version: `BLOCK_PERMUTATION_NULL_V1`
Production use: PROHIBITED
Formal OOS authorization: NO

## 1. Purpose

Provide a credible zero distribution for the primary `delta_tau` statistic without assuming daily rows are independent.

Primary statistic remains:

`delta_tau = tau_complex - tau_BASELINE_1`

with `tau-b` calculated against 3-session downside severity under `PRIMARY_3D_DOWNSIDE_CONCORDANCE_V1`.

The permutation test is supplementary inference. It does not replace the locked paired circular-block bootstrap confidence interval and does not change the primary endpoint.

## 2. Null hypothesis

The permutation null is:

> the contemporaneous ordering of model/baseline scores contains no time-aligned information about the future 3-session downside-severity path beyond what would arise when outcome time blocks are reassigned relative to the score path.

The complex and baseline score series remain paired with each other. Only the future-return/downside outcome timeline is block-permuted relative to those paired score rows.

This preserves the comparison between two models on exactly the same score dates while breaking their original time alignment with future outcomes.

## 3. Block length

Frozen block length:

`3 sessions`

Reason: inherited directly from the already-frozen primary outcome horizon and overlap structure. It is not selected from observed permutation significance or complex-model performance.

Changing the primary horizon requires a new inference/null version rather than silently changing the permutation block length.

## 4. Block construction

For `n` ordered evaluation rows:

1. partition outcome row indices into consecutive non-overlapping blocks of length 3;
2. permit only the final block to be shorter when `n % 3 != 0`;
3. randomly permute the order of whole blocks;
4. preserve row order within each original block;
5. flatten the permuted blocks to exactly `n` indices;
6. keep score rows in original order;
7. calculate null `delta_tau` using the permuted future-return timeline.

Every permutation is without replacement: each original outcome row appears exactly once per replicate.

## 5. Directional p-value

Observed direction remains:

`delta_tau > 0`

For `R` permutation replicates:

`p_perm = (1 + count(delta_tau_null >= delta_tau_observed)) / (R + 1)`

The +1 correction is frozen to avoid a zero Monte-Carlo p-value.

The permutation p-value is not a calibrated trading probability.

## 6. Computational defaults

Default replicates:

`5000`

Default deterministic seed:

`20261016`

These are computational reproducibility settings, not economic thresholds. Unit tests may use fewer replicates for speed but must never treat fixture p-values as research evidence.

## 7. Edge conditions

Fail closed when:

- score/outcome lengths differ;
- fewer than 2 observations are supplied;
- scores violate the frozen ordinal `0..3` contract;
- returns are non-finite;
- requested replication count is below the implementation minimum;
- block length differs from the frozen primary 3-session horizon.

The implementation exposes the exact block length, replicate count and seed in its result.

## 8. Executable binding

Implementation:

`block_permutation_null_v1.py`

Tests:

`test_block_permutation_null_v1.py`

TDD evidence:

- RED run `38867036663`: test contract was present before the implementation module and failed on the missing module as expected;
- GREEN run `38867104379`: implementation plus the then-current research suite passed, with `Ran 109 tests` and `OK`.

Formal-preflight binding evidence:

- RED run `38867354329`: the five newly required comparator/permutation provenance checks failed against the prior preflight implementation while existing functionality remained green;
- GREEN run `38867540890`: the complete research suite passed with `Ran 115 tests` and `OK` after the preflight consumed comparator identity, permutation version/hash, block length, replications and seed.

These tests verify the executable contract only. Fixture scores/returns, fixture hashes and fixture p-values are not research evidence and cannot support promotion.

## 9. Interpretation

A favorable permutation result only addresses whether observed `delta_tau` is unusual under this block-shuffled time-alignment null.

It does **not** by itself establish:

- economic portfolio value;
- robustness to transaction costs;
- valid PIT inputs;
- independence from shared price/volume source groups;
- production eligibility;
- formal OOS status.

All existing preflight, execution, PIT, power, ablation and hard-risk gates remain binding.

## 10. No historical re-selection

The permutation design is frozen before any new unused formal set is opened. Consumed historical windows may be used only for implementation diagnostics, never to select the block length, direction, p-value definition or replication count for formal promotion.
