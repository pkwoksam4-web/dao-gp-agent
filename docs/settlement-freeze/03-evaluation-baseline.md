# Evaluation baseline

**Status: PROPOSAL_NOT_FROZEN — owner decision due 2026-10-28.** No candidate target closes or cohort returns have been inspected for this proposal.

## Primary metric

Use the frozen Core10 ranking universe and the rank recorded at each cohort anchor. For each constituent and horizon (H), define the unadjusted price return:

`r_i(H) = target_unadjusted_close_i / anchor_unadjusted_close_i - 1`

The primary portfolio is long-only: hold equal weights in the highest-ranked three names. The baseline is an equal-weight portfolio of all ten Core10 names at the same anchor and target dates. This is implementable without shorting individual stocks.

`gross_excess(H) = 100 × (mean(top3 r_i(H)) − mean(all10 r_i(H)))`

Require all ten frozen-universe outcomes. A missing or corporate-action-blocked name blocks that cohort/horizon; do not change weights or denominator. The corporate-action rule is specified separately.

## Execution and transaction-cost model

Proposed execution rule: invest equal weights at the anchor close, hold through the target, then liquidate at the target close. The owner must freeze the starting capital because minimum commissions depend on order size.

For each portfolio (P), compute:

`net_return(P) = weighted_gross_return(P) − total_cost(P) / starting_capital`

The frozen fee table must contain:

| Input | Application |
| --- | --- |
| Commission rate and minimum per order | Buy and sell orders |
| Sell stamp-duty rate | Sell notional only |
| Transfer-fee rate by exchange | Buy and sell notionals |
| Slippage in basis points per side | Buy and sell notionals |
| Starting capital | Converts minimum charges to return cost |

For a position with initial notional (Cw_i) and target notional (Cw_i(1+r_i)), charge commission on each side as `max(minimum_commission, notional × commission_rate)`; charge stamp duty on target notional; charge transfer fee and slippage on the frozen applicable notionals. Apply the same capital and frozen assumptions to the top-three portfolio and equal-weight pool.

`net_excess(H) = 100 × (net_return(top3) − net_return(equal_weight_pool))`

If the desired minimum net excess is (delta_{net}), the corresponding gross hurdle is `δ_net + 100 × (cost(top3) − cost(equal_weight_pool))`. The existing **+1.00 percentage point** value has no approved net-margin or fee derivation and remains **NOT_FROZEN**. Do not insert assumed brokerage rates or claim that +1.00 pp is economically meaningful until the owner freezes the fee table and execution rule.

## Horizon and inference unit

- **5D is the sole primary validation horizon.**
- **20D is descriptive only**; it does not produce a confirmatory claim or pass/fail result.
- The 5D inference unit is a non-overlapping block of five exchange sessions, not a symbol row. Do not pool overlapping outcome windows.

## Reporting boundary

Before freeze, do not calculate rank IC, cohort returns, portfolio excess, or any aggregate result. Freeze the universe, top-three rule, equal-weight baseline, return convention, execution rule, cost inputs, and horizon roles in issue #28 before opening candidate target-price evidence.

## Owner decision

Approve or amend the long-only portfolio, baseline, execution assumption, cost table, and the derivation of any net economic threshold before outcome values are reviewed.
