# dao-gp-agent / Agent大脑

Persistent, auditable public-equity research system focused on point-in-time evidence, multi-agent research, forecast settlement, model governance, provenance, replay, quality gates, and cloud runtime verification.

## Current reproducible release

**Investment Intelligence V2.70** — 2026-09-20

- 193/193 tests PASS
- 185 PostgreSQL tables in the static schema
- Real Neon PostgreSQL + pgvector verified
- Real object-storage SHA256 round-trip verified
- Hosted Neon Function canary verified
- Strict infrastructure gate: **DEVELOPING** because current-release recovery snapshot evidence is not yet available

See `releases/v2.70/` for the release evidence snapshot.

## Safety / governance

The system has no brokerage execution path. Candidate models and agent weights are never auto-promoted. Point-in-time provenance, evidence qualification, release gates, and explicit truth-state separation remain mandatory.
