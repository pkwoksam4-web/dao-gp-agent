# Minimum gain, power, and inference unit

**Status: PROPOSAL_NOT_FROZEN — owner decision due 2026-10-28.**

## Primary horizon and gain

- **5D is the only primary validation horizon.**
- **20D is descriptive only**; it has no confirmatory p-value or pass/fail claim in this plan.
- The proposed metric is the 5D top-three minus bottom-three mean unadjusted price return spread from the frozen evaluation universe, with net gain reported after the pre-frozen turnover and cost model.
- The existing **+1.00 percentage point** threshold is not yet justified by a cost or turnover calculation. Keep it **NOT_FROZEN** until the owner freezes the rebalance policy, expected portfolio turnover, commission/tax/slippage inputs, and desired net economic margin. Define `net_gain = gross_gain − incremental implementation cost`; then derive the minimum gross hurdle from the declared net hurdle plus that cost. Do not label +1.00 pp economically meaningful without this derivation.

## Power and block count

The prior target of 34 blocks implies a single-block standard deviation of about 2.1 pp under the rough planning relation `n ≈ (2.8 × σ / δ)^2` for `δ = 1.00 pp`. That variance was not estimated from an independent baseline, so 34 is **not a validated sample target**.

Sensitivity only, using the same rough relation and `δ = 1.00 pp`:

| Assumed SD of independent 5D block gains (`σ`) | Approximate blocks |
| --- | ---: |
| 2.1 pp | 35 |
| 3.0 pp | 71 |
| 5.0 pp | 196 |

The required `σ` is the standard deviation across independent five-session block-level head-to-tail gains (or another explicitly frozen estimator of that same statistic), not the cross-sectional volatility of individual stock prices. A 3–5 pp stock-level dispersion would not by itself establish `σ = 3–5 pp`. Estimate or set `σ` from a pre-specified independent baseline that does not use the strategy's own outcome results. The baseline period, calculation, target `δ`, significance level, and power must be frozen before candidate cohort outcomes are inspected. Until then, the study is **not demonstrably powered** and the final sample target is **NOT_FROZEN**.

For scale, roughly 50 non-overlapping 5D blocks accrue per year. A 71–196 block target would take approximately 1.4–3.9 years from the first resumed LIVE sample; 34 blocks would take about 8 months. Missing prospective samples are not backfilled. Recalculate this calendar estimate only after the final admissible-block rule is frozen.

## Inference unit and decision rule

One unit is a non-overlapping block of five exchange sessions. Blocks must not overlap outcome windows. Use a one-sided 95% confidence interval for the sole 5D primary metric unless the owner freezes another test and error rate. A confirmatory claim requires the lower confidence bound for the mean net gain to exceed zero and the point estimate to meet the frozen net economic threshold. With 20D descriptive only, no cross-horizon multiplicity adjustment is needed.

## Owner decision

Approve or amend the net economic threshold and cost derivation, independent variance source and estimator, baseline period, alpha/power target, admissible-block rule, and 5D/20D roles before inspecting outcome values. Record the final values and timestamp in issue #28.