# Corporate-action outcome rule

**Status: PROPOSAL_NOT_FROZEN — owner decision due 2026-10-28.**

## Recommendation

Use the unadjusted raw close from the approved source pair. If a price-affecting corporate action has an ex-date in the interval `(anchor_date, target_date]`, mark the entire cohort/horizon candidate `BLOCKED_CORPORATE_ACTION`. Keep the original evidence and disclose the blocked count in any later report. Do not calculate a return for that cohort/horizon using a changed denominator.

Screen for cash dividends, bonus/share distributions, splits or consolidations, rights issues, and other issuer or exchange actions that change the share or price basis. Use official exchange notices and issuer announcements (including the official CNINFO disclosure record where applicable). Record the notice title, issuer, publication date, ex-date, action type, and URL in the evidence manifest. If an official notice is missing, ambiguous, or conflicting, block pending owner review.

Do not use adjusted close, synthetic/derived close, manual back-adjustment, or an alternative supplier field to repair an affected outcome. This rule preserves the raw target close while preventing a known price-basis discontinuity from being treated as an ordinary return.

## Scope

The rule applies to each 5D and 20D target independently. An action after one target but before the other blocks only the affected horizon. An action on the anchor date is outside the interval because the anchor close is already observed on that date.

## Owner decision

Approve or amend the action list, official evidence hierarchy, interval, and block behavior before outcome values are reviewed. Record the final rule and timestamp in issue #28.
