# One-time historical lookback re-pull and reconciliation

**Status: SPECIFICATION_ONLY / NOT_DONE.** This document does not authorize database writes, a collector run, settlement, or role creation.

## Read-only inventory completed

On 2026-10-27, under the owner's read-only authorization, the default Neon `production` branch (`br-raspy-breeze-b5clzass`) was queried for the PIT tables. The branch had been archived by inactivity and Neon automatically made it ready when the database was accessed; no manual restore operation was invoked. The database contains `market_bars` and `sources`. The role list contains only `investment_intel_owner`; `pit_writer` and `pit_reader` do not exist. No DDL, database write, backup/export, credential action, or ACL change was performed. The owner must take the backup/export before creating or validating the dedicated roles in SQL Editor.

For the Core13 daily bars:

| Stored provider/date range | Rows and symbols | Missing provenance |
| --- | --- | --- |
| `longbridge`, 2026-09-04–2026-10-09 | 260 rows; 13 symbols; 20 distinct sessions | 130 rows lack raw hash (2026-09-04–2026-09-18); all 260 lack `HISTORICAL_LOOKBACK`; source IDs and `retrieved_at` are present |
| `longbridge-connector`, 2026-09-04–2026-09-18 | 110 rows; 10 symbols | all 110 lack source ID/source row, raw hash, `retrieved_at`, and `HISTORICAL_LOOKBACK` |

The legacy `longbridge-connector` rows may overlap the same symbol/session keys as the main `longbridge` rows; do not count them as additional coverage without a key-by-key reconciliation. Across the 370 stored rows above, 240 lack raw hash, 110 lack source/retrieval time, and all 370 lack the lookback tag.

For 2026-09-28–2026-10-09 specifically, 65 rows cover 13 symbols across five sessions. All have source ID, raw hash, and retrieval time; all lack `HISTORICAL_LOOKBACK`. The stored source URI identifies the `candlesticks` dataset but does not preserve the exact SDK operation or all request parameters. The missing provenance must not be fabricated from current rows.

## Expected window and re-pull plan

The frozen 2026 calendar gives 31 sessions from 2026-09-04 through 2026-10-26, or 403 expected Core13 bar keys. The observer recorded no prospective LIVE samples after 2026-10-09 and 11 missing sessions from 2026-10-12 through 2026-10-26. Do not backfill those prospective samples or relabel derived/current bars as raw historical evidence.

For a later owner-authorized runtime window, reconcile every expected `(symbol, trade_date)` against the frozen calendar. Report row presence, source ID, raw and canonical hashes, timezone-aware `retrieved_at`, and the required `HISTORICAL_LOOKBACK` tag for every prior bar. Also report duplicate keys, hash mismatches, invalid timestamps, unexpected source/mode, and dates outside the calendar. Summarize each missing/invalid field by count and inclusive date range.

A separate re-pull specification must bind the approved source, exact calendar hash, symbol/date list, request parameters, and immutable run ID. Any future re-pull is read-only: preserve provider responses and manifest hashes; classify each key as `MATCH`, `MISSING_ROW`, `VALUE_MISMATCH`, `MISSING_PROVENANCE`, or `BLOCKED_ACCESS`; manually review every mismatch; do not overwrite rows or invent retrieval metadata. Any append requires a separate reviewed PR and written owner authorization in issue #26.

## Exit artifact

The future task must include the frozen calendar/source references, expected and observed row counts, field-level missing counts/date ranges, raw evidence and manifest hashes, per-key classifications, mismatch review, and confirmation that no write or settlement occurred.