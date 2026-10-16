# MINIMUM EFFECT JUSTIFICATION STATUS V1

Status: BLOCKED_OBJECTIVELY_UNJUSTIFIED
Applies to: `PRIMARY_3D_DOWNSIDE_CONCORDANCE_V1`
Primary estimand: `delta_tau = tau_complex - tau_baseline_1`
Production use: PROHIBITED

## Decision

`minimum_effect_delta_tau = NOT_FROZEN`

`minimum_sample_required = NOT_FROZEN`

No numeric value is authorized at this checkpoint.

## Why the gate remains blocked

The project currently has qualitative decision semantics such as:

- WATCH -> reduce chase tolerance;
- low-severity fragility -> restrict some new high-beta risk;
- high-severity / active de-risking -> restrict new high-beta attack risk more strongly;
- REPAIR -> selectively reopen eligibility.

However, it does **not** yet have a frozen numeric downstream action policy that maps each risk state or `RISK_EVIDENCE_SCORE` to a fixed portfolio exposure change.

Without that fixed action mapping, there is no objective way to translate an incremental Kendall `delta_tau` into an economically meaningful amount of tail-risk saved versus false-alarm opportunity cost.

Therefore selecting a value such as `0.02`, `0.05`, `0.10`, or any other number would be arbitrary.

## Prohibited shortcuts

The following are explicitly prohibited:

1. derive the minimum effect from the already-consumed historical shock / fragility windows;
2. use the intended unused evaluation set to choose the effect size after outcomes are visible;
3. adopt synthetic unit-test fixture values as project thresholds;
4. choose the smallest effect that gives a convenient sample size;
5. infer economic value from statistical significance alone;
6. choose an action mapping after seeing which mapping makes the complex model look best.

## What would make a numeric effect defensible

A future version may freeze `minimum_effect_delta_tau` only after one of these independent routes is completed before the unused set is opened:

### Route A — decision-utility calibration

Freeze, independently of unused outcomes:

- a deterministic mapping from each ordinal risk score to allowed exposure / attack-budget change;
- a common downstream action policy applied identically to complex model and baseline;
- tail-risk-loss utility and false-alarm opportunity-cost accounting;
- A-share execution feasibility assumptions sufficient to evaluate the action mapping.

Then use development-only or synthetic scenarios to identify the smallest `delta_tau` improvement that produces a material net decision benefit.

### Route B — external benchmark

Provide an externally defensible, pre-existing benchmark for incremental rank-concordance improvement in a comparable market-risk classification problem. The benchmark must be independent of this project's intended unused outcomes and its provenance must be recorded.

If neither route is available, the gate stays blocked.

## Current implication

The project may continue to:

- improve implementation parity;
- make categorical state resolution executable;
- improve provenance and fail-closed behavior;
- collect prospective shadow data without performance-based rule changes.

The project may **not**:

- declare a formal promotion test sufficiently powered;
- open an unused holdout for promotion evaluation;
- promote the complex regime layer beyond the governance gate.

This blocked state is intentional evidence discipline, not missing bookkeeping.
