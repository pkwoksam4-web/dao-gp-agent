# POWER / SAMPLE PLAN V1

Status: GOVERNANCE_PREREG_INCOMPLETE
Power-plan version: `POWER_SAMPLE_PLAN_V1`
Production use: PROHIBITED
Formal evaluation eligibility: BLOCKED until the minimum meaningful effect and resulting minimum sample are frozen.

## 1. Primary estimand

The primary effect is the incremental 3-session downside concordance versus the locked simple baseline:

`delta_tau = tau_complex - tau_baseline_1`

where each `tau` is the tie-aware Kendall `tau-b` between the model's ordinal `RISK_EVIDENCE_SCORE` and future 3-session downside severity.

No PnL, hit-rate or selected-event statistic may substitute for `delta_tau` in the first formal promotion test.

## 2. Locked inference conventions

- Primary horizon: `3 sessions`.
- Primary directional alpha: `0.05`.
- Target power for planning: `0.80`.
- Dependence treatment for the primary test: paired circular block bootstrap with block length `3`.
- One primary hypothesis in this family. Additional horizons are secondary unless a future version preregisters otherwise.

These are design conventions, not market thresholds.

## 3. Minimum meaningful effect

`minimum_effect_delta_tau = NOT_FROZEN`

A numeric minimum effect is deliberately not inferred from the already-consumed historical shock / fragility windows. Doing so would convert the development sample into a target-setting sample and would bias the required sample size toward the model already observed.

The minimum meaningful effect must be justified before any unused evaluation set is opened from one of the following ex-ante sources:

1. a decision-utility analysis linking a change in ordinal concordance to a meaningful reduction in tail-risk / false-alarm decision errors under a fixed downstream action policy; or
2. an externally defensible benchmark for incremental rank-concordance value that is independent of the intended unused set.

If neither route can justify a value, the project remains blocked rather than inventing one.

## 4. Sample-size method

Once `minimum_effect_delta_tau` is frozen, required sample size will be estimated by Monte Carlo power simulation under the exact V1 comparison procedure.

The simulation must:

- use the same score alphabet `{0,1,2,3}`;
- preserve or conservatively approximate the observed score-frequency / tie structure from development-only data;
- preserve 3-session dependence using the same block structure as the primary inference contract;
- generate paired complex and baseline scores against a common downside outcome so the relevant quantity is `delta_tau`, not two unrelated correlations;
- search increasing sample sizes until estimated rejection probability reaches the frozen target power;
- use only consumed development data or synthetic assumptions documented before the unused set is opened;
- never estimate power assumptions from the unused evaluation outcomes.

The exact simulator implementation and random seed must be versioned before a numeric `minimum_sample_required` is accepted.

## 5. Current sample requirement

`minimum_sample_required = NOT_FROZEN`

Therefore:

- `RESEARCH_ONLY -> SHADOW_ONLY` may continue under descriptive / prospective collection rules already approved;
- `SHADOW_ONLY -> CANDIDATE` is blocked;
- no formal unused-set comparison may be declared promotion-eligible by the evaluation preflight.

A test fixture may use synthetic numeric values to verify the preflight mechanism; those fixture numbers are not project thresholds.

## 6. Episode dependence

Daily observations are the operational decision timestamps, but shock events can span multiple sessions. Formal reporting must therefore include both:

- daily timestamp count; and
- grouped non-overlapping event-episode count for stress episodes.

A multi-day shock may not be presented as several independent event successes.

The exact episode-grouping rule must be frozen before episode-level secondary inference is used for promotion.

## 7. Multiple testing discipline

The first formal version has one primary hypothesis:

`delta_tau > 0` at 3 sessions versus BASELINE_1.

Therefore no multiplicity correction is required for that single primary comparison. If later versions introduce multiple primary hypotheses, they must preregister the family and use Holm family-wise correction as required by `MODULE_PROMOTION_GOVERNANCE_V1.md`.

Secondary diagnostics cannot rescue primary failure.

## 8. Fail-closed rule

The formal evaluation preflight must reject an evaluation manifest when any of the following is absent or unfrozen:

- power-plan version;
- primary alpha;
- target power;
- numeric positive minimum meaningful `delta_tau`;
- numeric minimum sample requirement;
- baseline / score-mapping / inference versions;
- classifier hash;
- genuinely unused evaluation-set identity and hash.

This rule prevents opening an unused set first and deciding afterward how much evidence was "enough".
