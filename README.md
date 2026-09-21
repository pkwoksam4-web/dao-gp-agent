# dao-gp-agent / Agent大脑

Persistent, auditable public-equity research system focused on point-in-time evidence, multi-agent research, forecast settlement, model governance, provenance, replay, quality gates, and cloud runtime verification.

## Current reproducible release

**Investment Intelligence V2.70** — 2026-09-20

- 193/193 tests PASS
- 185 PostgreSQL tables in the V2.70 static schema
- Real Neon PostgreSQL + pgvector verified
- Real object-storage SHA256 round-trip verified
- Hosted Neon Function canary verified
- V2.70 current-release isolated recovery was verified at the time of that release

See `releases/v2.70/` for the immutable V2.70 release evidence.

## Live cloud state

The production cloud control plane is allowed to evolve ahead of the last packaged source release. **Do not infer a newer reproducible software release from live database tables or branch names.**

Latest recorded live evidence: `releases/live/2026-09-21/REAL_DATA_EVIDENCE.json`.

As of that evidence:

- Neon production is real and active; the live control plane has 202 public tables.
- Canonical watchlist `WAT-core10-final-v1` has 9,990 completed Longbridge daily bars in production (999 per symbol), with unfinished 2026-09-21 session data excluded from EOD samples.
- 9,690 historical PIT feature rows are available; 9,640 have 5D labels and 9,490 have 20D labels.
- Longbridge generic `candlesticks(count=1000)` is verified; older offset/date-range history remains blocked by entitlement error 301607.
- A 20D mean-reversion ranking candidate is **SHADOW_ONLY / UNAPPROVED**. It improves holdout cross-sectional ranking versus the momentum baseline, but its probability calibration does not beat a simple train-prior probabilistic baseline.
- The latest cloud truth remains **runtime verified / current-release recovery pending** because the Free-plan snapshot quota prevents creating a new snapshot for the live schema without rotating existing recovery evidence.

The reproducible source release and live cloud truth are intentionally tracked as separate version lines.

## Safety / governance

The system has no brokerage execution path. Candidate models and agent weights are never auto-promoted. Point-in-time provenance, evidence qualification, release gates, and explicit truth-state separation remain mandatory.
