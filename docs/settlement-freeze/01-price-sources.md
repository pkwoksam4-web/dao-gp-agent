# Outcome price sources and fallback

**Status: PROPOSAL_NOT_FROZEN — owner decision due 2026-10-28.**

## Current evidence and access status

- **Stored path for 2026-09-28 through 2026-10-09:** a read-only query of the default Neon `production` branch found 65 `market_bars` rows across 13 symbols and 5 frozen exchange sessions. Their source URIs are `longbridge://candlesticks/{symbol}`, with some records also carrying `?period=day`. Source ID, raw hash, and retrieval time are present for these 65 rows; all 65 lack the `HISTORICAL_LOOKBACK` tag. The source metadata records dataset `candlesticks`, but does not preserve the exact SDK method or full request parameters. **INFERRED:** the capture used Longbridge's candlesticks route; the persisted record does not prove whether the original request used the generic latest-bars call or a historical-by-date call.
- **Single latest-bar test:** on 2026-10-27, one read-only `candlesticks` request for `600392.SH`, daily, count 1, unadjusted, returned one latest bar for the current session. This demonstrates access for one symbol through the generic route only. It does not establish 13-symbol capture access, historical range access, or collector gate 4.
- **Historical-by-date access:** the 2026-10-22 rehearsal request returned Longbridge error 301607 with a quota of 0; it returned no bar. The reason is unresolved: monthly quota consumption versus the account's tier/entitlement. Longbridge documentation describes a 100–3,000 unique-symbol monthly quota by account tier that resets monthly. The personal tier, used quota, and reset date still require an owner-side Developer Center check.
- **Tushare fallback:** its official `daily` documentation describes unadjusted daily OHLCV; the documented minimum permission is 120 points. **NOT_TESTED:** no authorized Tushare API session/connector was available for a one-symbol permission probe. The earlier `sw_daily` denial does not establish `daily` access.
- **Collector gate 4:** the observer's `same_day_ingest_chain` remains `NOT_CHECKED`; no daily collector was run. A single latest-bar response does not satisfy the authoritative same-day manifest/ingest evidence. The Longbridge limitation may affect a future producer if it needs date-range history, but its effect on the live-day collector is not verified.

## Proposed source selection and fallback

1. Keep Longbridge `candlesticks` as a **conditional candidate**, pending owner verification of tier/quota/reset and a successful authorized test for all required symbols and target sessions.
2. Keep Tushare Pro `daily` as a **fallback candidate only**. Before adoption, first test one symbol read-only. Then compare every unadjusted close for all 13 symbols over the overlapping 2026-09-03 through 2026-10-09 sessions against stored bars or original manifests. Require exact equality after decimal quantization to CNY 0.01. Record each difference separately; do not adopt Tushare unless every required value agrees and access is authorized.
3. If neither source is qualified, keep capture `BLOCKED_ACCESS` and the source decision `NOT_FROZEN`. Do not switch vendors after inspecting target outcomes, use a proxy/VPN, use derived closes, or substitute a different field.

The purpose of cross-checking is to detect supplier errors; it does not require a claim that the vendors have independent upstream feeds.

## Raw evidence and public-repository handling

The repository is public. Do not commit provider response bodies or raw price values to it until the applicable Longbridge/Tushare data-use and redistribution terms have been checked. That terms review is **NOT_DONE**. Until then, any public manifest must be limited to necessary non-price metadata and hashes, and only if the applicable terms permit even those fields. Keep raw response files outside the public repository in an approved private evidence location. No provider raw payload or close value is included in this proposal.

For each authorized capture, record vendor and endpoint, request parameters, symbol, exchange, target date, close field, currency, adjustment mode, timezone-aware `retrieved_at`, raw-response SHA-256, and canonical-bar SHA-256. Do not store access tokens or credentials in the manifest.

## Owner decision

Before any candidate outcome-price capture, approve the accessible source, fallback rule, exact close field, comparison requirement, data-use terms, and permitted evidence location. Record the final decision and timestamp in issue #28.