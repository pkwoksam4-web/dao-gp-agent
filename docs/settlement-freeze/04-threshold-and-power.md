# Minimum gain, power, and inference unit

**Status: PROPOSAL_NOT_FROZEN — owner decision due 2026-10-28.** No candidate target prices, cohort returns, or model outcomes were used to choose these proposals.

## Primary metric and threshold

- **5D is the only primary validation horizon.**
- **20D is descriptive only** and has no confirmatory p-value or pass/fail claim.
- The implementable candidate metric is the 5D long-only top-three portfolio's net excess return over the equal-weight Core10 pool, as defined in `03-evaluation-baseline.md`.
- The existing **+1.00 percentage point** threshold is **NOT_FROZEN**. Freeze the desired minimum net excess, execution rule, capital, and commission, stamp-duty, transfer-fee, and slippage schedule first. Derive the corresponding gross hurdle from the difference between portfolio costs; do not substitute an abstract cost allowance.

## Candidate alpha, power, and sample-size method

A directional improvement test is proposed: one-sided (alpha=0.05), target power (1-eta=0.80), with independent non-overlapping five-session blocks. The normal-approximation planning formula is:

`n = ceil(((z_(1-alpha) + z_(power)) × σ / δ_net)^2)`

For the proposed alpha and power, the multiplier is approximately 2.486. This is only a planning approximation; the final decision rule and small-sample inference method remain subject to owner approval.

Illustrative sensitivity if, solely for scale, `δ_net = 1.00 pp`:

| Assumed SD of independent block net excess (`σ`) | Approximate blocks |
| ---: | ---: |
| 2.1 pp | 28 |
| 3.0 pp | 56 |
| 5.0 pp | 155 |

These are mathematical sensitivities, not a frozen sample target. The earlier 34-block figure came from the different factor 2.8 (two-sided 5% alpha with 80% power); it is not consistent with the one-sided proposal above and was not powered from an independent estimate.

## Variance source and admissible blocks

Estimate `σ` only from a pre-specified strategy-neutral calibration baseline, using the same block-level net-excess statistic and the same frozen fee/execution rules. The calibration must not use the model's own rankings or any candidate cohort outcomes. Freeze the baseline dates, data source, calculation, and hash before inspecting candidate target prices. If no valid independent baseline is available, mark `σ` and the power claim `NOT_FROZEN`; do not borrow a stock-level 5D dispersion estimate as if it were the block-level statistic.

One inference unit is a non-overlapping five-session block. Blocks may not share outcome sessions. Missing prospective samples are not backfilled. At roughly 50 admissible blocks per year, the illustrative 28/56/155-block counts correspond to about 0.6/1.1/3.1 years from the first eligible LIVE sample, before missed sessions.

## Candidate decision rule

For the sole 5D primary metric, a confirmatory claim would require the lower bound of the owner-frozen one-sided 95% confidence interval for mean net excess to exceed zero and the point estimate to meet the frozen net economic threshold. Freeze the exact interval/test method, alpha, power, sigma source, block rule, and threshold before any candidate outcomes are opened. No 20D inferential claim is planned, so no cross-horizon multiplicity adjustment is proposed.

## Owner decision

Approve or amend the net hurdle and fee derivation, one-sided alpha and power, inference method, independent variance source and period, admissible-block rule, and 5D/20D roles. Record the exact values and freeze time in issue #28.
