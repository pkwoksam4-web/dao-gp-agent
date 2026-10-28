# Settlement freeze packet — 2026-10-28 owner decision

**Status: PROPOSAL_NOT_FROZEN.** These drafts contain no candidate cohort close values, rank IC, or cohort performance calculations. A passing CI run is not a research result or authorization.

## Decisions for the owner

1. [Outcome price sources and fallback](01-price-sources.md)
2. [Corporate-action rule](02-corporate-actions.md)
3. [Evaluation baseline](03-evaluation-baseline.md)
4. [Minimum gain, power, and inference unit](04-threshold-and-power.md)
5. [One-time historical lookback re-pull and reconciliation specification](05-lookback-rerun.md)

The first four documents define the outcome policy. The fifth is an implementation specification only; it does not authorize database access or writes.

## Access and evidence status — 2026-10-28

- Longbridge historical-by-date access returned zero quota and no bar. The owner-side account tier, month-to-date usage, and reset date remain **NOT_VERIFIED**.
- A post-close, read-only latest-daily-bar probe returned one current-date bar for each of 13 Core13 symbols. The response hashes are kept only in a local `REHEARSAL_NOT_EVIDENCE` manifest; the rehearsal was not committed to this public repository and did not write to Neon. Provider terms remain **NOT_VERIFIED**.
- Tushare `daily` permission is **NOT_DONE / BLOCKED_ACCESS** because the executing agent has no authorized connector or credential. No overlap comparison was performed; this is not a denial from Tushare.
- Observer gate 4 (`same_day_ingest_chain`) remains `NOT_CHECKED`. A latest-bar probe does not satisfy the production manifest and ingest chain.
- The Neon inventory was read-only. No backup/export, DDL, data write, role creation, credential operation, or ACL change was performed. The owner must back up the correct branch before SQL Editor role work.
- The `longbridge-connector` count of 110 covers 2026-09-04–2026-09-18; 100 covers 2026-09-07–2026-09-18. The ten-row difference is the excluded 2026-09-04 session, not a data change.

## Freeze record

On approval, record the exact decision timestamp in Asia/Shanghai, each approved value, and the merged commit SHA in issue #28. Hash the merged decision files with SHA-256 and record that digest there. Any item not approved stays `NOT_FROZEN`; do not inspect candidate outcomes to choose among alternatives.

The source, corporate-action rule, baseline, costs, statistical assumptions, and power target remain proposals until the owner records the freeze.
