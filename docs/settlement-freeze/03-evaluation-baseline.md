# Outcome evaluation baseline

**Status: PROPOSAL_NOT_FROZEN — owner decision due 2026-10-28.**

## Recommendation

Evaluate the ranked top three names against the full frozen Core10 universe, separately at 5 and 20 exchange sessions. The top three are selected by the ranking recorded at the cohort anchor; the benchmark is the equal-weight Core10 portfolio from the same anchor. Use the same exact anchor close, target session, and approved unadjusted-close policy for both.

For horizon (H), calculate each constituent's price return as:

`r_i(H) = target_unadjusted_close_i / anchor_unadjusted_close_i - 1`

Then calculate the equal-weight portfolio return for the selected top three and for all ten Core10 names. The cohort-level outcome is their difference in percentage points:

`gain(H) = 100 × (mean(top3 r_i(H)) − mean(Core10 r_i(H)))`

A missing or blocked close for any Core10 constituent blocks that cohort/horizon rather than changing the denominator. Report 5D and 20D estimates separately; do not pool the horizons. This is a price-return comparison and does not represent dividend-reinvested total return.

## Reporting boundary

This metric is a proposal for the primary evaluation baseline. Rank IC may be considered only after the full decision is frozen and under a separately stated analysis plan. Before the owner freeze, do not calculate rank IC, cohort-level outcomes, or any aggregate result.

## Owner decision

Approve or amend the benchmark universe, top-three portfolio, return definition, denominator, horizon separation, and treatment of blocked constituents before inspecting results. Record the final decision and timestamp in issue #28.
