# Investment Intelligence V2.70

Release date: 2026-09-20

## Reproducible build

- Regression: **193/193 PASS**
- Static PostgreSQL schema: **185 unique tables**
- Manifest entries: **200**
- ZIP SHA256: `c49568d32b72a27f07048f43cd8b26c0330db9bcae76ba68dbbcb80cdcc55422`
- MANIFEST.sha256 SHA256: `9e4cf4fec4c0c6b87cd4d5c36ddf317ebdec636ba343d4b2044af067b8d3d700`

## Real infrastructure evidence

- Neon PostgreSQL 17 + pgvector 0.8.0: PASS
- Production DB append-only write/read smoke: PASS
- Private object storage target: PASS
- Real object write/read SHA256 round-trip: PASS
- Hosted Neon Function `intelcanary`, deployment 3, Node.js 24: VERIFIED
- 15-minute health probe: observed
- Database + unpooled DB + object-storage bindings: observed
- Current-release managed recovery: **PASS** — 185 public tables and pgvector 0.8.0 restored from the current-release snapshot

The strict infrastructure gate is **INFRASTRUCTURE_VERIFIED**.

## Shadow baseline

- Core watchlist: **1 / 10 symbols**
- Market bars: **0**
- Forecast items: **0**
- 5D accrual: **EMPTY**
- 20D accrual: **EMPTY**
- Cohort acquisition: **NO_OBSERVATIONS**
- Evidence readiness: **DEVELOPING**

No live Shadow forecast or settlement is claimed yet. The next gate requires real provider data and observed 5D/20D settlement.

## Truth guards

No automatic model promotion, portfolio mutation, brokerage execution, production deployment, or rollback is implied by this release.
