# One-time historical lookback re-pull and reconciliation

**Status: SPECIFICATION_ONLY / NOT_DONE.** This document does not authorize database writes, a collector run, settlement, or role creation.

## Read-only inventory completed

On 2026-10-27, under the owner's read-only authorization, the default Neon `production` branch (`br-raspy-breeze-b5clzass`) was queried for PIT tables. Neon automatically made the branch ready when accessed after inactivity archiving; no manual restore operation was invoked. The database contains `market_bars` and `sources`. The role list contains only `investment_intel_owner`; `pit_writer` and `pit_reader` do not exist. No DDL, data write, backup/export, credential action, or ACL change was performed. The owner must complete backup/export before SQL Editor role work.

## Count windows and the 110-versus-100 reconciliation

The counts refer to different inclusive date windows:

| Provider and window | Rows | Coverage | Provenance notes |
| --- | ---: | --- | --- |
| `longbridge`, 2026-09-04–2026-10-09 | 260 | 13 symbols × 20 sessions | 130 lack raw hash (2026-09-04–2026-09-22); all 260 lack `HISTORICAL_LOOKBACK`; source IDs and `retrieved_at` are present |
| `longbridge`, current 31-session window 2026-09-07–2026-10-27 | 247 | 13 symbols × 19 available sessions | 120 lack raw hash; all 247 lack `HISTORICAL_LOOKBACK`; 12 sessions (156 symbol/session keys) are absent after 2026-10-09 |
| `longbridge-connector`, 2026-09-04–2026-09-18 | 110 | 10 symbols × 11 sessions | All lack source row, raw hash, `retrieved_at`, and `HISTORICAL_LOOKBACK` |
| `longbridge-connector`, 2026-09-07–2026-09-18 | 100 | 10 symbols × 10 sessions | Same provenance gaps; this is the part inside the later 31-session window |

The 110-versus-100 difference is exactly the ten `longbridge-connector` rows from 2026-09-04, which is outside the 2026-09-07–2026-10-27 31-session window. The date-grouped read-only query confirms 10 rows for 10 symbols on each listed session. Do not count these legacy rows as additional coverage: they may overlap existing symbol/session keys and lack admissible provenance.

For 2026-09-28–2026-10-09 specifically, 65 rows cover 13 symbols across five sessions. All have source ID, raw hash, and retrieval time; all lack `HISTORICAL_LOOKBACK`. The stored source URI identifies the `candlesticks` dataset but does not preserve the exact SDK operation or complete request parameters. Do not fabricate missing provenance from current rows.

The 247 observed plus 156 missing keys reconcile to 403 expected keys for the current 31-session Core13 window. No price values were output by the inventory query.

## Expected window and re-pull plan

For a later owner-authorized runtime window, reconcile every expected `(symbol, trade_date)` against the frozen calendar. Report row presence, source ID, raw and canonical hashes, timezone-aware `retrieved_at`, database `persisted_at`, and the required `HISTORICAL_LOOKBACK` tag for every prior bar. Existing rows without `persisted_at` remain unknown and fail closed; do not replace their value with the migration time.

Report duplicate keys, hash mismatches, invalid timestamps, unexpected source/mode, and dates outside the calendar. Summarize each missing/invalid field by count and inclusive date range. For the current window, the missing dates 2026-10-12–2026-10-27 are not prospective samples and must not be backfilled or relabeled as `LIVE_PIT`.

A separate re-pull specification must bind the approved source, exact calendar hash, symbol/date list, request parameters, and immutable run ID. Any future re-pull is read-only: preserve provider responses and manifest hashes; classify each key as `MATCH`, `MISSING_ROW`, `VALUE_MISMATCH`, `MISSING_PROVENANCE`, or `BLOCKED_ACCESS`; manually review every mismatch; do not overwrite rows or invent retrieval metadata. Any append requires a separate reviewed PR and written owner authorization in issue #26.

## Exit artifact

The future task must include the frozen calendar/source references, expected and observed row counts, field-level missing counts/date ranges, raw evidence and manifest hashes, per-key classifications, mismatch review, and confirmation that no write or settlement occurred.
