# GP12 Candidate Benchmark Integration Design

## Goal

Bind the already validated candidate-only benchmark `CSI All Share / 000985` into the GP12 reconstruction-candidate package review without changing the existing factor or parameter contracts and without making any GP V1.1 historical-recovery claim.

## Hard constraints

- Benchmark identity is `CSI All Share / 中证全指 / 000985`, Eastmoney `secid=1.000985`.
- Binding status remains `CANDIDATE_ONLY_UNAPPROVED` with origin `NEW_RECONSTRUCTION_CANDIDATE`.
- Formal validation window remains `2020-06-01` through `2026-04-17` inclusive.
- The benchmark evidence must show exact frozen-calendar coverage: 1426 rows, same first/last session, no missing/extra/duplicate dates.
- PIT semantics remain session-close no-lookahead: a session D close is usable only at or after D 15:00 Asia/Shanghai.
- `historical_provider_publication_timestamp_proven` remains false.
- `gp_v11_benchmark_recovered` and `historical_recovery_claim_allowed` must remain false.
- Existing hashes must remain unchanged:
  - parameters: `22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204`
  - factors: `b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e`
- Do not modify `data/GP12_CANDIDATE_PARAMETERS_V1.json` or `data/GP12_CANDIDATE_FACTORS_V1.json`.
- The benchmark's own daily-close series is benchmark evidence only. It is not automatically admitted as the factor contract's `market_adjusted_close` feature family, because the frozen factor definition explicitly names that family. No semantic substitution is allowed without a new factor definition/hash.

## Integration contract

`gp12_candidate_v1.review_package(...)` gains a required benchmark-validation evidence input for the integrated path. It validates the evidence artifact produced by `gp12_candidate_benchmark_v1.py` and fails closed on missing, malformed, blocked, drifted, or historically overclaimed evidence.

A valid review reports:

- `candidate_benchmark_validated=true`
- `candidate_benchmark_blocker_closed=true`
- `benchmark_feature_binding_allowed=false`
- `market_adjusted_close_substitution_allowed=false`
- `historical_benchmark_recovered=false`
- `historical_strategy_recovered=false`
- `real_feature_inputs_validated=false`
- `model_freeze_allowed=false`
- `oos_metrics_allowed=false`

The package remains `UNAPPROVED`; `NEW_STRATEGY_ADOPTION_REQUIRED` remains an overall blocker even when the benchmark sub-blocker closes.

## Failure behavior

The package review must fail closed and add a specific benchmark blocker if any of the following is true:

- evidence is missing or invalid JSON;
- artifact/status/strategy identity does not match;
- benchmark is not 000985 / CSI All Share / secid 1.000985;
- factors or parameters hashes drift;
- calendar coverage is not exactly the frozen 1426 sessions or bounds differ;
- PIT policy validation is false;
- source identity validation is false;
- candidate benchmark blocker is not closed;
- validation evidence contains any blocker;
- evidence claims the GP V1.1 benchmark was recovered or allows a historical-recovery claim.

## Workflow

The candidate workflow first runs the benchmark contract/full-window validator, then passes its JSON evidence into the package review. The final workflow assertion verifies benchmark closure and candidate-only semantics while retaining the adoption/feature-input restrictions.
