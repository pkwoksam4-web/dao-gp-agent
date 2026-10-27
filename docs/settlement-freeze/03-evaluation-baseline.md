# Evaluation baseline

**Status: PROPOSAL_NOT_FROZEN — owner decision due 2026-10-28.**

## Primary metric

Use the frozen evaluation universe and the ranking recorded at each cohort anchor. The default proposal is the frozen Core10 universe, with equal weights for the highest-ranked three names and the lowest-ranked three names.

For each constituent and horizon (H), calculate price return from the same anchor close to the target unadjusted close:

`r_i(H) = target_unadjusted_close_i / anchor_unadjusted_close_i - 1`

The gross head-to-tail spread in percentage points is:

`gross_gain(H) = 100 × (mean(top3 r_i(H)) − mean(bottom3 r_i(H)))`

The comparison baseline is the bottom-three basket at the same anchor and horizon; zero spread is the no-relative-edge baseline. Apply the frozen corporate-action block rule to both baskets. A missing or blocked close in either basket blocks that cohort/horizon; do not change the denominator.

Report the cost-adjusted version separately:

`net_gain(H) = gross_gain(H) − incremental implementation cost(H)`

The incremental cost must use the owner-frozen rebalance rule, portfolio turnover, commissions, taxes, and slippage assumptions. A gross spread alone does not meet a net economic hurdle.

## Horizon roles

- **5D is the sole primary validation horizon.**
- **20D is descriptive only** under this proposal. Do not use it for a confirmatory claim or combine its result with 5D. This avoids a second primary test and a horizon-multiplicity adjustment.

The inference unit for 5D is a non-overlapping block of five exchange sessions, not an individual stock row. Do not pool blocks with overlapping outcome windows.

## Reporting boundary

This is a metric definition only. Before the owner freeze, do not calculate rank IC, cohort gains, or any aggregate result. Record the final universe, rank cutoffs, return definition, baseline, cost treatment, and horizon roles in issue #28 before inspecting candidate outcome values.

## Owner decision

Approve or amend the frozen universe, top/bottom group sizes, equal-weight rule, no-edge baseline, corporate-action handling, and gross-to-net cost model before outcome values are reviewed.