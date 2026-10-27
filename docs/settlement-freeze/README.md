# Settlement freeze packet — 2026-10-28 owner decision

**Status: PROPOSAL_NOT_FROZEN.** These drafts are for owner review on 2026-10-28 before any candidate outcome results are inspected. They contain no candidate close values, rank IC, or cohort performance calculations. A passing CI run is not a research result or authorization.

## Decisions for the owner

1. [Outcome price sources and fallback](01-price-sources.md)
2. [Corporate-action rule](02-corporate-actions.md)
3. [Evaluation baseline](03-evaluation-baseline.md)
4. [Minimum gain, power, and inference unit](04-threshold-and-power.md)
5. [One-time historical lookback re-pull and reconciliation specification](05-lookback-rerun.md)

The first four documents define the outcome policy. The fifth is an implementation specification only; it does not authorize database access or writes.

## New access findings — 2026-10-27

A single Longbridge latest-daily-bar probe for one symbol succeeded. The separate historical-by-date rehearsal request returned an explicit zero-quota error and no bar. The personal account tier, usage, and reset date are **NOT_VERIFIED** pending owner-side Developer Center inspection. Tushare `daily` permission is **NOT_TESTED**; its unadjusted-close path remains a fallback proposal only, subject to a one-symbol access test and exact 13-symbol overlap validation.

The owner-authorized Neon inventory was read-only. It identified the default `production` branch and historical source metadata; Neon automatically activated the branch during access. No backup/export, DDL, data write, role creation, credential operation, or ACL change was performed. The owner must complete backup/export before any SQL Editor role work.

The repository is public. No raw provider response or close value is included in this PR. Provider terms for public redistribution remain **NOT_VERIFIED**.

## Freeze record

On approval, record the exact decision timestamp in Asia/Shanghai, each approved value, and the merged commit SHA in issue #28. Hash the merged decision files with SHA-256 and record that digest there. Any item not approved stays `NOT_FROZEN`; do not inspect candidate outcomes to choose among alternatives.

The source, thresholds, statistical assumptions, and economic cost model remain proposals until the owner records the freeze.