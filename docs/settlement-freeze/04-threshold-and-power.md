# Minimum gain, power, and inference unit

**Status: PROPOSAL_NOT_FROZEN — owner decision due 2026-10-28.**

## Recommendation

- **Minimum worthwhile gain:** +1.00 percentage point in top-three minus Core10 mean price return, for each horizon separately.
- **Decision rule per horizon:** the observed mean gain must be at least +1.00 pp and its one-sided confidence bound must be above zero. If either condition fails, label the horizon inconclusive or not meeting the minimum; do not change the rule after viewing outcomes.
- **Multiplicity:** treat 5D and 20D as two co-primary horizon tests and use one-sided (alpha=0.025) for each, controlling the family-wise error at 0.05 by Bonferroni.
- **Power:** target 80% power under a standardized effect (d=0.5). For planning, this means a +1.00 pp mean gain with a 2.00 pp standard deviation of independent block gains. Under a one-sample t model, this requires about 34 independent blocks per horizon (approximately 80.8% power); target 38 admissible blocks per horizon to allow roughly 10% unusable blocks.

The standard-deviation assumption is a planning convention, not an estimate from the current cohorts. If it is not defensible before results are inspected, the owner should freeze a different variance source or explicitly accept that the study is not demonstrably powered. Do not estimate or tune this assumption from the three current cohorts.

## Inference unit

The unit is a non-overlapping calendar block of cohort starts for the horizon being tested, not an individual stock row. Separate 5D and 20D inference. For 5D, blocks must not overlap their five-session outcome windows; for 20D, they must not overlap their twenty-session windows. The current three cohorts do not meet the proposed sample target and cannot support a powered conclusion.

## Owner decision

Approve or amend the minimum gain, per-horizon rule, multiplicity, power target, variance assumption, admissible-block count, and block definition before outcome values are reviewed. Record the final values and timestamp in issue #28.
