# Agent Brain status pointer

`status_checked_at: 2026-10-27 15:04 (Asia/Shanghai)`

## Current state

- Last verified prospective LIVE PIT date: **2026-10-09**. Later dates have no verified same-day LIVE manifest.
- 2026-10-12, 10-13, 10-14, 10-19, 10-21, and 10-22 are recorded as NON_LIVE in issue #25; 10-16 is PRECHECK_FAIL / NON_LIVE in issue #23; 10-20 is NON_LIVE in issue #24; 10-23 is NON_LIVE in issue #34. These records do not claim a collector ran or failed unless a run is evidenced.
- 2026-10-24 and 10-25 were weekends.
- PR #35 was reviewed at exact head 7707357f9d223e62440879cce85ff5fc43512e51 and merged as bb43e5e9cb7a3727c4a0bf56494d534c2b63aecf.
- 2026-10-26: [status issue #37](https://github.com/pkwoksam4-web/dao-gp-agent/issues/37) records `NON_LIVE` from scheduled run [40347410059](https://github.com/pkwoksam4-web/dao-gp-agent/actions/runs/40347410059), main SHA `bb43e5e9cb7a3727c4a0bf56494d534c2b63aecf`. It started at 23:14:46 CST, about 6h59m after the approximate 16:15 schedule; mark `DELAYED_SAME_DAY`. Authorization is `FAIL_NOT_AUTHORIZED`, manifest is `MISSING`, and database/ingest remain `NOT_CHECKED`. This is the first scheduled trigger observed; manual comparison is pending and five-session acceptance is not passed.
- 2026-10-27 as of 16:42 CST: the scheduled workflow target was about 16:15, but the read-only Actions run list still showed only the 2026-10-26 run; no 2026-10-27 status issue was visible. This is at least 27 minutes of observed delay, not a final missed-day classification. Track scheduled-to-start and scheduled-to-publish delay for each run; cron time is not a writer cutoff.

## Phase 1 observer — observe-only

PR #35 checks authorization plus expiry, the exact-date manifest path/commit/hash, and the expected 31-session window from the frozen calendar. Database and authoritative ingest remain NOT_CHECKED, so overall PASS is impossible. It has no writer dependency and does not authorize a collector.

## Full writer restart gates — not yet met

1. **Authorization and safety evidence:** recover the original raw rule_id, error_message, and blocked_action; verify explicit authorization and expiry; use a dedicated least-privilege role.
2. **Immutable evidence path:** bind the exact manifest path, immutable commit, workflow/run reference, and SHA-256.
3. **31-session runtime lookback:** verify each Core13 bar's source, hash, retrieval timestamp, and HISTORICAL_LOOKBACK provenance; missing sessions or provenance fail closed.
4. **Same-day PIT/ingest chain:** require the exact-date manifest, preflight dependency, and authoritative 13/13 bar/feature ingest evidence.

Keep writers hard-disabled through the five-session observation and all separate recovery gates.

## Restart gate

The calendar continuity gate was reviewed at head `189e177098170ee97fa9428f547449f4a6d7f952` and merged to `main` as `4c2eca6063670d73a8ea1a4534b15f70c7f40ec2`. `calendar-contracts` passed on the reviewed head (run 39760992567); its workflow has an unfiltered `pull_request` trigger.

Do not run the collector until the original authorization evidence is available and all four preflight gates pass in order. The writer workflows remain hard-disabled. PR #35 adds a Phase 1 observe-only publisher for authorization/expiry, the immutable manifest, and the frozen 31-session calendar; database presence and authoritative ingest remain `NOT_CHECKED`, so this is not a complete four-gate job and cannot authorize a writer. Its frozen 2026 calendar SHA-256 is `4211957f7916adf07da0b9005e90dbdeb5aba25facb9d5637e47483f2048bd87`; the source note is `docs/CN_EXCHANGE_CALENDAR_2026_SOURCE.md`. Any date year without a frozen calendar/hash reports `BLOCKED_CALENDAR_COVERAGE`. Keep writers disabled through the five-session observation and until the separate writer dependency is reviewed; see [issue #29](https://github.com/pkwoksam4-web/dao-gp-agent/issues/29).

All writer workflows target the main-only `pit-production` environment and read only `PIT_WRITER_DATABASE_URL` at the database step. The environment has no writer secret, `PIT_WRITE_AUTHORIZATION=NOT_AUTHORIZED`, and the repository-level owner credential is not exposed to these jobs. No production write, collector run, Shadow request, or settlement is authorized.

A Neon role setup attempt found the role-creation API did not produce a verifiably least-privilege role; both temporary roles were removed and their grants revoked. No writer/reader credential now exists. The public database role currently has TEMP privilege; it was not changed globally. See [issue #26](https://github.com/pkwoksam4-web/dao-gp-agent/issues/26).

## Other open contracts

- Shadow request and settlement remain in [draft PR #32](https://github.com/pkwoksam4-web/dao-gp-agent/pull/32), current head `065e68fe8a2acb44827fa84be77f95566738c52b`. It covers latest-event state per horizon, 20D-first/5D-retry, and idempotent appends. The migration fails before table creation if either role is missing and is owner-run manually, never by Actions. Contract CI run [40276842752](https://github.com/pkwoksam4-web/dao-gp-agent/actions/runs/40276842752) and calendar CI run [40276842634](https://github.com/pkwoksam4-web/dao-gp-agent/actions/runs/40276842634) passed on that head. No migration, database write, or settlement was run.
- Runtime lookback provenance is in [draft PR #36](https://github.com/pkwoksam4-web/dao-gp-agent/pull/36), whose status pointer is refreshed in this PR. It reads each bar's source, hash, and retrieval time, requires `HISTORICAL_LOOKBACK` on prior bars, and records per-bar attestation. It fails closed until stored historical metadata has the tag. The previously validated code head was `d6d448054a5080ae341b3374ccc5d2d296e4e45f`; its runtime and calendar CI runs passed. This documentation commit will trigger checks again. No writer workflow was enabled.
- Late outcome capture remains separate from LIVE. Issue #28 freezes sources, company-action handling, baseline, and numeric thresholds by 2026-10-28. Do not calculate rank IC or cohort aggregates before that freeze. The 2026-11-02, 11-05, and 11-06 raw candidates use the no-database PR-backed evidence path after the freeze.
- The 2026-10-22 price-path rehearsal is `NOT_DONE` as of 2026-10-27 15:04 CST. Preserve the one-time-branch and `tmp/non_evidence_rehearsal/2026-10-22/` isolation in issue #28; do not write to evidence/ingest paths, open or merge a PR, or calculate results. The price source remains subject to the 2026-10-28 freeze.
- Owner-authorized read-only inventory on 2026-10-27 queried the default `production` branch `br-raspy-breeze-b5clzass`; Neon automatically made it ready on access after inactivity archiving. No manual restore was invoked. The database contains `market_bars` and `sources`; only `investment_intel_owner` exists, with no `pit_writer` or `pit_reader`. No backup/export, DDL, database write, credential action, or ACL change was performed. The owner must export/backup before SQL Editor role work.
- Read-only provenance inventory: 2026-09-28–10-09 has 65 Longbridge `candlesticks` rows for 13 symbols × 5 sessions, with source ID/hash/retrieved_at present and `HISTORICAL_LOOKBACK` missing on all 65. From 2026-09-04–10-09, the `longbridge` provider has 260 rows; 130 lack raw hash (2026-09-04–09-22), and all 260 lack the historical tag. An additional 110 `longbridge-connector` rows across 10 symbols (2026-09-04–09-18) lack source ID, hash, retrieved_at, and tag; these may overlap keys and are not extra coverage. No data values were output.
- The owner-side tag targets and fetch command remain in [issue #26](https://github.com/pkwoksam4-web/dao-gp-agent/issues/26#issuecomment-6361184363). Read-only GitHub ref lookups on 2026-10-27 returned 404 for all three tags: A `6f41355e153fa56b93652d7ebb687d41f36c9f63`, D `2a7056ffd61885046e34dc1494bc668143d96793`, calendar `4c2eca6063670d73a8ea1a4534b15f70c7f40ec2`. Tags remain `NOT_DONE`; annotated creation and peeled-tag comparison are owner-side.
- Re-enable LIVE only after the five-session observer acceptance in issue #29, dedicated-role verification, PR #32 settlement migration/permissions, runtime lookback wiring, and a reviewed preflight dependency. The 2026-11-02 estimate is provisional and moves if any dependency slips.
- The control-plane decision record remains issue #26; daily status evidence belongs in its date-specific issue.

A successful CI run is not a research result or production authorization.
