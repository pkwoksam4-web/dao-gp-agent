# Agent Brain status pointer

`status_checked_at: 2026-10-22 11:21 Asia/Shanghai`

## Current state

- Last verified LIVE PIT date: **2026-10-09**.
- The retrospective status index is [issue #25](https://github.com/pkwoksam4-web/dao-gp-agent/issues/25); it explicitly distinguishes post-hoc records from contemporaneous records.
- 2026-10-12, 10-13, 10-14, 10-19, and 10-21: `NON_LIVE` in issue #25 because no same-day LIVE manifest is present on `main`. This does not assert that a collector ran or failed.
- 2026-10-16: `PRECHECK_FAIL / NON_LIVE`, contemporaneous record in [issue #23](https://github.com/pkwoksam4-web/dao-gp-agent/issues/23).
- 2026-10-20: `NON_LIVE`, contemporaneous record in [issue #24](https://github.com/pkwoksam4-web/dao-gp-agent/issues/24).
- 2026-10-22: `PRECHECK_PENDING` at this pointer's timestamp; the 16:10 CST preflight has not happened. Do not assign a final status before it.
- 2026-10-10/11 and 10-17/18 were weekends.

## Restart gate

Do not run the collector until the calendar-keyed 31-session continuity gate is merged to `main`, the original safety/authorization evidence is available, and all preflight gates pass. The gate is currently on open PR [#21](https://github.com/pkwoksam4-web/dao-gp-agent/pull/21); the current control-plane note is in open draft [#14](https://github.com/pkwoksam4-web/dao-gp-agent/pull/14). See [issue #26](https://github.com/pkwoksam4-web/dao-gp-agent/issues/26) for the minimum persistence-permission decision request.

Missing-day samples are never backfilled. Historical lookback bars may be added only before a future run's decision cutoff, with source, retrieval time, immutable hash, and `HISTORICAL_LOOKBACK` provenance. A retrospective status or successful CI is not a research result or production authorization.
