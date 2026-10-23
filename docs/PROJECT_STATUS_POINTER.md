# Agent Brain status pointer

`status_checked_at: 2026-10-23 pre-cutoff (Asia/Shanghai)`

## Current state

- Last verified LIVE PIT date: **2026-10-09**.
- The retrospective status index is [issue #25](https://github.com/pkwoksam4-web/dao-gp-agent/issues/25); it distinguishes retrospective records from contemporaneous records.
- 2026-10-12, 10-13, 10-14, 10-19, and 10-21: `NON_LIVE` in issue #25 because no same-day LIVE manifest is verified on `main`; this does not assert that a collector ran or failed.
- 2026-10-16: `PRECHECK_FAIL / NON_LIVE`, contemporaneous record in [issue #23](https://github.com/pkwoksam4-web/dao-gp-agent/issues/23).
- 2026-10-20: `NON_LIVE`, contemporaneous record in [issue #24](https://github.com/pkwoksam4-web/dao-gp-agent/issues/24).
- 2026-10-22: `NON_LIVE`, recorded after the cutoff in issue #25; reason: `授权门禁待负责人决定`.
- 2026-10-23: before 16:10 CST, status is `PRECHECK_PENDING`; do not record a final day status early.
- 2026-10-10/11 and 10-17/18 were weekends.

## 16:10 preflight gates — evaluate in order

1. **Authorization and safety evidence:** retrieve the raw `rule_id`, `error_message`, and `blocked_action`, and verify the explicitly permitted writer. If this gate fails, record `NON_LIVE` and stop.
2. **Immutable evidence path:** verify versioned/immutable location, commit identity, workflow/run reference, and hash capture.
3. **31-session lookback:** prove every Core13 symbol has every required exchange session, with no missing predecessor or interior session.
4. **Same-day PIT chain readiness:** verify the exact-date manifest and the frozen PIT/ingest/observation contract and authorized collector entry.

At the 2026-10-22 post-cutoff check, Gate 1 failed and later gates were not evaluated. For 2026-10-23, the cutoff check has not happened yet.

## Restart gate

The calendar continuity gate was reviewed at head `189e177098170ee97fa9428f547449f4a6d7f952` and merged to `main` as `4c2eca6063670d73a8ea1a4534b15f70c7f40ec2`. `calendar-contracts` passed on the reviewed head (run 39760992567); its workflow has an unfiltered `pull_request` trigger.

Do not run the collector until the original authorization evidence is available and all four preflight gates pass in order. The writer workflows remain hard-disabled. There is not yet an executable four-gate preflight job or a required writer dependency; [issue #29](https://github.com/pkwoksam4-web/dao-gp-agent/issues/29) tracks the read-only publisher and restart dependency.

All writer workflows target the main-only `pit-production` environment and read only `PIT_WRITER_DATABASE_URL` at the database step. The environment has no writer secret, `PIT_WRITE_AUTHORIZATION=NOT_AUTHORIZED`, and the repository-level owner credential is not exposed to these jobs. No production write, collector run, Shadow request, or settlement is authorized.

A Neon role setup attempt found the role-creation API did not produce a verifiably least-privilege role; both temporary roles were removed and their grants revoked. No writer/reader credential now exists. The public database role currently has TEMP privilege; it was not changed globally. See [issue #26](https://github.com/pkwoksam4-web/dao-gp-agent/issues/26).

## Other open contracts

- Shadow request evidence and settlement changes are isolated in draft [PR #32](https://github.com/pkwoksam4-web/dao-gp-agent/pull/32). It has six settlement-only paths and passing contract CI. Append-only settlement records and idempotent retries remain unresolved and block merge. PR #31 is closed unmerged as superseded.
- Historical lookback bars may be added only before a future run's decision cutoff, with source, retrieval time, immutable hash, and `HISTORICAL_LOOKBACK` provenance. Missing prospective samples are never backfilled. The current before/equal/after cutoff tests cover a helper only; runtime query binding remains a follow-up.
- Late outcome capture remains unimplemented. Source pair and corporate-action handling still need to be frozen in issue #28 before settlement.
- The control-plane decision record is in issue #26. Daily outcome records belong in issues; update this pointer only when control state changes.

A successful CI run is not a research result or production authorization.
