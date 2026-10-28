# Outcome price sources and fallback

**Status: PROPOSAL_NOT_FROZEN — owner decision due 2026-10-28.**

## Current evidence and access status

- **Stored Neon path:** a read-only query of the default `production` branch found 65 `market_bars` rows for 13 symbols across the five frozen sessions from 2026-09-28 through 2026-10-09. Source ID, raw hash, and retrieval time are present; all 65 lack the `HISTORICAL_LOOKBACK` tag. The source URI identifies the `candlesticks` dataset but does not prove the exact SDK method or complete request parameters.
- **Latest daily-bar access:** one read-only Longbridge `candlesticks` probe for `600392.SH` succeeded on 2026-10-27. On 2026-10-28 after 16:30 Asia/Shanghai, a one-time read-only probe for all 13 Core13 symbols (`period=day`, `count=1`, unadjusted) returned one bar per symbol. Under the repository's UTC-to-China-date conversion, all 13 timestamps map to 2026-10-28. This establishes access to the latest daily-bar route for these 13 symbols on that date; it does not establish historical-range access or collector gate 4. The hash-only local record is marked `REHEARSAL_NOT_EVIDENCE`; no raw price, provider response, or hash was committed to the public repository, and nothing was ingested into Neon.
- **Historical-by-date access:** the 2026-10-22 Longbridge request returned error 301607 with quota 0 and no bar. The reason remains unresolved: monthly quota consumption versus account-tier entitlement. The owner's Developer Center check of tier, month-to-date usage, and reset date is **NOT_DONE**.
- **Tushare fallback:** the [official API guide](https://tushare.pro/document/2?doc_id=108) lists `daily` as all-history daily data with a 120-point minimum. This is a permission threshold, not evidence of this account's access. The one-symbol probe is **NOT_DONE / BLOCKED_ACCESS** because no authorized connector or credential is available to the executing agent; this is not evidence that Tushare denied access. The earlier `sw_daily` denial does not establish `daily` access.
- **Collector gate 4:** `same_day_ingest_chain` remains `NOT_CHECKED`. No authoritative manifest/ingest chain was run. A latest-bar read does not satisfy this gate, and the Longbridge quota's effect on a future same-day collector remains unverified.
- **Public-repository rights check (2026-10-28):** Long Bridge Securities LLC's published [Terms of Service](https://longbridge.com/us/en/support/articles/14864594652431) require compliance with exchange and third-party data-provider terms and do not grant a general public-redistribution right. Applicability to the owner's specific Longbridge account entity is not verified. Tushare's published [Data Service Agreement](https://tushare.pro/document/1?doc_id=405) describes a personal, non-transferable, non-commercial license for individual viewing. No permission to redistribute provider data through this public repository was established. Account-specific agreements and any separate written permission remain unchecked. Treat public raw values and hashes as **NOT_AUTHORIZED** unless the owner confirms permission.

## Proposed source selection and fallback

1. Keep Longbridge `candlesticks` as a conditional candidate. Before adoption, the owner must verify tier/quota/reset and the capture path must be authorized for the required target dates.
2. Keep Tushare Pro `daily` as a fallback candidate only. First perform an authorized one-symbol access test. If access succeeds, compare every unadjusted close for all 13 symbols over overlapping 2026-09-03 through 2026-10-09 sessions against admissible stored bars or original manifests. Require exact equality after quantization to CNY 0.01; list every difference separately. No overlap comparison has been performed.
3. If neither source is qualified, keep capture `BLOCKED_ACCESS` and the source decision `NOT_FROZEN`. Do not use a proxy/VPN, derived close, substitute field, or a new source chosen after inspecting target outcomes.

Cross-checking is intended to detect supplier errors; it does not require a claim that suppliers have independent upstream feeds.

## Manifest and repository handling

For each authorized capture, record vendor and endpoint, request parameters, symbol, exchange, target date, close field, currency, adjustment mode, timezone-aware `retrieved_at`, raw-response SHA-256, and canonical-bar SHA-256. Do not store access tokens or credentials.

Keep raw responses outside the public repository in an approved private evidence location until vendor terms are verified. Do not publish even hash-only manifests unless the applicable terms permit them. Any future public evidence PR must be reviewed and merged by the owner; CI success is not data approval.

## Owner decision

Before candidate outcome-price capture, approve the provider and fallback, exact close field, overlap requirement, terms, and evidence location. Record the final decision and timestamp in issue #28. Until then, do not capture or inspect cohort target closes.
