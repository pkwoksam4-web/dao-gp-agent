# INTERNAL FRAGILITY V0 — SEVERITY / PERSISTENCE PREREG V1

Status: RESEARCH_ONLY
Thresholds: NOT_FROZEN
Production use: PROHIBITED

## Why this layer is being added

The preregistered 2026-04-15 case produced a material false alarm despite multiple same-day deterioration channels. The preregistered 2026-09-09 case produced only a transient/mild drawdown. Therefore the research must distinguish **fragility presence** from **fragility severity** without fitting a new one-day numeric threshold.

## Same-day severity dimensions

Record these dimensions at the signal close. No numeric cutoffs are frozen.

### A. Liquidity / turnover stress

Categorize descriptively:
- healthy expansion;
- low-liquidity drift;
- rotation with stable liquidity;
- active distribution / de-risking.

Important: high turnover by itself is not stress; the interpretation depends on price/breadth direction and leadership behavior.

### B. Leadership damage

Categorize:
- healthy continuation;
- mixed dispersion;
- failed continuation / breakout failure;
- broad leadership unwind.

### C. Median / small-cap damage

Categorize:
- participation healthy;
- mild underperformance;
- broad weakness;
- disorderly selloff.

### D. Cross-asset / derivative stress

Categorize only from verified evidence:
- absent/unverified;
- caution;
- material stress;
- shock.

No evidence must never be converted to `zero stress`.

### E. Rotation quality

Categorize:
- healthy broad rotation;
- narrow but orderly rotation;
- defensive-only rotation;
- no credible receiving side / cash-like de-risking.

## Candidate severity output

Do not replace the existing state labels. Add a separate research field:

- `SEVERITY_LOW`
- `SEVERITY_MEDIUM`
- `SEVERITY_HIGH`
- `SEVERITY_UNVERIFIED`

No deterministic mapping is frozen yet.

## Persistence as a state transition, not a close-time predictor

Persistence cannot be known at the original close. It must be evaluated sequentially using only newly available data:

- `REPAIRING`: breadth/leadership acceptance improves and stress channels recede;
- `PERSISTENT`: deterioration remains or expands as new sessions arrive;
- `ESCALATING`: new external/derivative/liquidity stress is added;
- `UNRESOLVED`: evidence remains mixed.

This prevents using future outcomes to relabel the original signal.

## Decision research principle

Fragility presence and severity affect **risk budget**, not a mechanical stock sell rule.

- Low severity: mainly lower chase tolerance.
- Medium severity: restrict new high-beta risk and require stronger RS/catalyst confirmation.
- High severity / active de-risking: capital preservation dominates; only exceptional RS survivors remain eligible.
- Repairing: re-open risk selectively rather than restoring full budget immediately.

No position percentages are frozen.

## Next-window protocol

For every new unused historical window:

1. record the evidence fields from `PREREG_FIELDS_V1.md`;
2. assign fragility state;
3. assign severity from this file;
4. lock the record in Git before retrieving forward outcomes;
5. retrieve +1D / +3D / +5D CSI1000 outcomes;
6. log false-alarm cost versus tail-risk-save diagnostics;
7. never relabel the original state solely because of the outcome.
