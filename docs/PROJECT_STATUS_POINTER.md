# Agent Brain status pointer

`status_checked_at: 2026-10-28 18:31 Asia/Shanghai`

## Live and observer status

- Last verified prospective LIVE PIT date: **2026-10-09**. Main has no same-day LIVE manifest after that date.
- 2026-10-26: [status issue #37](https://github.com/pkwoksam4-web/dao-gp-agent/issues/37), run [40347410059](https://github.com/pkwoksam4-web/dao-gp-agent/actions/runs/40347410059), main SHA `bb43e5e9cb7a3727c4a0bf56494d534c2b63aecf`. Result `NON_LIVE`; authorization `FAIL_NOT_AUTHORIZED`, manifest `MISSING`, database and ingest `NOT_CHECKED`. The run started at 23:14:46 Asia/Shanghai, about 6h59 after the 16:15 target.
- 2026-10-27: [status issue #39](https://github.com/pkwoksam4-web/dao-gp-agent/issues/39), run [40522491522](https://github.com/pkwoksam4-web/dao-gp-agent/actions/runs/40522491522), same main SHA. Result `NON_LIVE`; authorization `FAIL_NOT_AUTHORIZED`, manifest `MISSING`, database and ingest `NOT_CHECKED`. The run started at 22:35:01 Asia/Shanghai, about 6h20 after target.
- The schedule is `15 8 * * 1-5` UTC (target about 16:15 Asia/Shanghai); GitHub may delay it. For both delayed runs, `created_at` equals `run_started_at`; the observer job was created 5 seconds later and started 5 seconds after that. The delay occurred before the run record existed. **INFERRED:** there is no evidence of substantial runner queue time; available run metadata cannot distinguish GitHub schedule dispatch delay from another pre-run scheduling delay.
- As of 2026-10-28 18:31 Asia/Shanghai, no 2026-10-28 observer run or status issue was visible. Keep today's status pending; this is not a final missed-day classification.
- Owner confirmation in issue #29 that the 10/26 and 10/27 reports match the manual checks is **NOT_DONE**. The five-session acceptance count has not started.
- Phase 1 uses `contents: read` and `issues: write`; weekday holidays are resolved against the frozen exchange calendar as `SKIPPED_NON_SESSION`. Database and authoritative ingest remain `NOT_CHECKED`, so Phase 1 cannot report overall `PASS`.

## Data and provenance

- For the current 31-session window 2026-09-07–2026-10-27, 403 Core13 keys are expected; 247 rows exist for 19 sessions through 2026-10-09, and 156 keys are missing for 12 sessions, 2026-10-12–2026-10-27. Of the 247 stored rows, 120 lack a raw hash and all 247 lack `HISTORICAL_LOOKBACK`.
- The separate `longbridge-connector` inventory has 110 rows for 2026-09-04–2026-09-18, versus 100 for 2026-09-07–2026-09-18. The difference is exactly the 10 symbols on 2026-09-04, which is outside the latter window. These records lack source/hash/retrieval/tag provenance and are not extra coverage.
- A post-close, read-only Longbridge latest-daily probe on 2026-10-28 returned one current-date bar for each of 13 symbols. The hash-only local record is `REHEARSAL_NOT_EVIDENCE`; no provider values, payload, or hashes were committed, and no database ingest or outcome calculation occurred. Historical-by-date access previously returned zero quota.
- The owner's Longbridge account tier, monthly usage, and reset date are **NOT_VERIFIED**. Tushare `daily` access and the 13-symbol overlap comparison are **NOT_DONE / BLOCKED_ACCESS** because no authorized connector or credential is available to the executing agent. The published [Long Bridge Securities LLC terms](https://longbridge.com/us/en/support/articles/14864594652431) require exchange/provider-term compliance; applicability to the owner's account entity is not verified. The [Tushare data service agreement](https://tushare.pro/document/1?doc_id=405) limits use to personal, non-transferable, non-commercial individual viewing. No public-repository redistribution permission was established; no provider values or hashes are published.
- The current Neon inventory was read-only: `pit_writer` and `pit_reader` were absent. No backup/export, DDL, role creation, database write, credential action, or ACL change was performed. PR #36 proposes a manual migration; existing bars' persistence time remains unknown until the owner backs up and applies it. No backfill is allowed.

## Open pull requests

- PR #35 is merged. It was reviewed at exact head `7707357f9d223e62440879cce85ff5fc43512e51` and merged to main as `bb43e5e9cb7a3727c4a0bf56494d534c2b63aecf`.
- Draft PR #32 head: `bc90731d4d0a119816b4ac5d3b078f5cc7ec8993`. Settlement consumes reviewed no-database manifests and stores per-symbol target prices/returns only; hash-bound evaluation is separate. Contract CI [40671893017](https://github.com/pkwoksam4-web/dao-gp-agent/actions/runs/40671893017) and calendar CI [40671892997](https://github.com/pkwoksam4-web/dao-gp-agent/actions/runs/40671892997) passed.
- Draft PR #36 head: `784abdbb464fbe34067de9fc665a6b1a42d0e962`. Runtime cutoff uses database-stamped `persisted_at`; old or late rows fail closed. Provenance CI [40671996809](https://github.com/pkwoksam4-web/dao-gp-agent/actions/runs/40671996809) and calendar CI [40671996837](https://github.com/pkwoksam4-web/dao-gp-agent/actions/runs/40671996837) passed. Its net diff excludes this status pointer.
- Draft PR #38 head: `d4bc154c0eb35593d970dff4921b271ecbdf1ee8`. The primary-metric, cost, and power documents remain proposals. Calendar CI [40672287617](https://github.com/pkwoksam4-web/dao-gp-agent/actions/runs/40672287617) passed.

## Authorization and restart gate

`PIT_WRITE_AUTHORIZATION=NOT_AUTHORIZED`; every production writer workflow remains hard-disabled with `if: false`. No LIVE collector, database write, settlement, or evaluation was run. A successful CI run is not a data result or authorization.

The restart gate is not met. Owner actions still outstanding include: back up/export the verified Neon branch; create and verify the least-privilege roles in SQL Editor; check Longbridge quota and Tushare access; approve the vendor-independent freeze; record the observer manual confirmation; and create/verify the three owner-side tags. Do not publish a restoration date until the source and provenance blockers are resolved.
