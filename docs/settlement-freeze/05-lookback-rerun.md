# One-time historical lookback re-pull and reconciliation

**Status: SPECIFICATION_ONLY / NOT_DONE.** This document does not authorize branch restoration, database writes, a collector run, or settlement.

## Purpose and expected coverage

For a future authorized runtime window, reconcile every required Core13 symbol/session bar against the frozen exchange calendar. A 31-session window for 13 symbols contains 403 expected bar keys. Build the exact date list from the frozen calendar for the requested run; do not infer sessions from weekdays. The observer's 2026-10-26 window was 2026-09-04 through 2026-10-26, but that does not establish which historical rows are present or complete.

The requested read-only inventory remains `NOT_DONE`: as of the 2026-10-27 Neon check, all nine listed branches were archived and the eligible PIT-data branch had not been identified. Do not restore an archived branch or query a guessed branch. The owner must identify the branch and complete the separately specified backup/export step before any inventory access.

## Inventory report

For each expected `(symbol, trade_date)`, report whether the row exists and whether it has:

- a stable source identifier;
- raw response SHA-256 and canonical bar SHA-256;
- timezone-aware `retrieved_at`;
- `HISTORICAL_LOOKBACK` provenance for a prior bar (and the required current-bar mode for the runtime date).

Summarize missing rows and each missing/invalid field by count and inclusive date range. Also report duplicate keys, hash mismatches, invalid timestamps, unexpected source/mode, and dates outside the frozen calendar. Do not infer or fill missing metadata from current database values.

## Re-pull and reconciliation procedure

1. Bind the task to an approved source, exact calendar hash, symbol list, date list, source parameters, and a new immutable run ID.
2. Retrieve only the missing or invalid source evidence using authorized read-only access. Save provider responses and a manifest in a reviewed candidate artifact; record retrieval timestamps and both raw-response and canonical-bar hashes.
3. Compare each candidate bar to the stored key and value without changing the stored row. Classify each as `MATCH`, `MISSING_ROW`, `VALUE_MISMATCH`, `MISSING_PROVENANCE`, or `BLOCKED_ACCESS`. Preserve all originals and mismatches.
4. Require manual review of every mismatch and a signed-off difference report. Do not silently select a source, overwrite a row, relabel a prospective bar, or claim that a re-pull proves historical ingestion occurred at the time.
5. Any later append of missing historical bars requires a separate reviewed PR, all restart prerequisites, and written owner authorization in issue #26. The task itself is read-only and this specification contains no SQL to execute.

If an endpoint is unavailable or returns HTTP 451, stop and record `BLOCKED_ACCESS`. Do not use a proxy, VPN, alternate field, or fabricated retrieval metadata. Until source, hash, retrieval time, and provenance are actually joined by the runtime, fail closed.

## Exit artifact

The future task must produce: frozen calendar/source references; exact expected and observed row counts; missing/invalid-field counts and date ranges; raw evidence and manifest hashes; per-key reconciliation classifications; mismatch review; and an explicit statement that no database write or settlement occurred.
