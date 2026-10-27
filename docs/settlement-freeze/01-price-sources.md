# Outcome price source pair

**Status: PROPOSAL_NOT_FROZEN — owner decision due 2026-10-28.**

## Recommendation

- **Candidate primary (conditional; not currently access-qualified):** Longbridge historical daily candlestick endpoint, with adjustment mode explicitly set to `NoAdjust`.
- **Candidate independent cross-check (not access-tested):** Tushare Pro `daily` endpoint, which documents its daily close as unadjusted.

Official endpoint documentation: [Longbridge historical candlesticks](https://open.longbridge.com/docs/quote/pull/history-candlestick) and [Tushare A-share daily data](https://tushare.pro/document/1?doc_id=27).

This is a vendor-level source pair. The available documentation does not establish that the vendors use independent upstream feeds; do not describe it as upstream-independent unless that is verified separately. Verify account permission, quota, coverage for every symbol/date, and each source's unadjusted field before approval.

A read-only Longbridge history-candlestick request for the 2026-10-22 rehearsal was denied on 2026-10-27 with an explicit history quota limit of zero; no bar or close was returned. Longbridge is therefore not currently qualified for this account. Tushare access was not tested. The rehearsal is `BLOCKED_ACCESS`; do not retry through a proxy, VPN, or alternate field. The owner must freeze an accessible, authorized source pair before any outcome-price capture.

## Capture and agreement rule

For every exact target session, retrieve only after the session close. Preserve each vendor response as received and record, per source: vendor and endpoint, request parameters, symbol, exchange, target trade date, field name, currency, adjustment mode, timezone-aware `retrieved_at`, raw response SHA-256, and canonical bar SHA-256.

For China A-share closes, compare the two unadjusted closes at the quoted CNY 0.01 tick. Require exact equality after decimal quantization to two places. A missing response, missing symbol/date, unknown adjustment mode, currency mismatch, or unequal close makes that candidate `BLOCKED_SOURCE_DISAGREEMENT`; retain both raw responses and do not choose a winner or substitute another vendor after seeing values.

If access is denied or an HTTP 451/access restriction is returned, stop and record the block. Do not use a proxy, VPN, derived close, or another vendor's field as a replacement.

## Owner decision

Approve or amend the source pair, access qualification, exact comparison rule, and evidence fields before any result-price capture. Record the final decision and timestamp in issue #28.
