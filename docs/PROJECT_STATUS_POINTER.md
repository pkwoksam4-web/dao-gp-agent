# Agent Brain status pointer

`status_checked_at: 2026-10-26 13:38 (Asia/Shanghai)`

## Current state

- Last verified prospective LIVE PIT date: **2026-10-09**. Later dates have no verified same-day LIVE manifest.
- 2026-10-12, 10-13, 10-14, 10-19, 10-21, and 10-22 are recorded as NON_LIVE in issue #25; 10-16 is PRECHECK_FAIL / NON_LIVE in issue #23; 10-20 is NON_LIVE in issue #24; 10-23 is NON_LIVE in issue #34. These records do not claim a collector ran or failed unless a run is evidenced.
- 2026-10-24 and 10-25 were weekends.
- PR #35 was reviewed at exact head 7707357f9d223e62440879cce85ff5fc43512e51 and merged as bb43e5e9cb7a3727c4a0bf56494d534c2b63aecf.
- For 2026-10-26, the observer is scheduled for about 16:15 Asia/Shanghai. At 13:38 no scheduled run or daily issue is present. Do not record a final daily status before the run and evidence exist.

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

- Shadow request and settlement are in draft PR #32, head 292444fcfc6f5f54adcbe20c2c7f91fc2c9a18ea. Append-only settlement events and hash-keyed idempotent retries are implemented; the owner-run migration is included. CI passed. The PR remains draft: the migration and grants are not applied or verified, and no settlement was run.
- Runtime lookback provenance is in draft PR #36, head e0879d7e785b737082d668536c6a31391872e104. It reads each bar's source, hash, and retrieved_at, requires the historical HISTORICAL_LOOKBACK tag, and records per-bar attestation. It fails closed until stored historical metadata has the tag. No writer workflow was enabled.
- Late outcome capture remains separate from LIVE. Issue #28 freezes sources, company-action handling, baseline, and numeric thresholds by 2026-10-28. Do not calculate rank IC or cohort aggregates before that freeze. The 2026-11-02, 11-05, and 11-06 raw candidates use the no-database PR-backed evidence path after the freeze.
- The 2026-10-22 price-path rehearsal has not been run. If performed after the freeze, keep it on one disposable branch under tmp/non_evidence_rehearsal/2026-10-22/; do not open or merge a PR and do not write to evidence or ingest paths.
- The dedicated Neon writer/reader roles are still absent. The previously inspected production branch was archived; role creation and readback must happen in SQL Editor on the active production branch. No global ACL was changed.
- The corrected A/D/#27 tag targets and fetch command are recorded in issue #26, including gp/dao2-a-main-net-flow. Tags have not been created or remotely verified; that requires local annotated-tag creation and peeled-tag comparison.
- Re-enable LIVE only after the five-session observer acceptance in issue #29, dedicated-role verification, PR #32 settlement migration/permissions, runtime lookback wiring, and a reviewed preflight dependency. The 2026-11-02 estimate is provisional and moves if any dependency slips.
- The control-plane decision record remains issue #26; daily status evidence belongs in its date-specific issue.

A successful CI run is not a research result or production authorization.
