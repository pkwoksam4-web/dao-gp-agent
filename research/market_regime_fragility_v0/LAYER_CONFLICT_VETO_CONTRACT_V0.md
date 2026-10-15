# LAYER CONFLICT / VETO CONTRACT V0

Status: GOVERNANCE_PREREG
Production use: PROHIBITED
Numeric hysteresis: NOT_FROZEN
Purpose: prevent contradictory layer states from being resolved ad hoc after outcomes are known

## 1. Core principle

Upper layers may restrict **eligibility / risk budget / execution permission**. They do not rewrite lower-layer evidence to make the narrative consistent.

Contradictory states are allowed to coexist in the ledger.

Example:

- `THEME = CONFIRMED`
- `MARKET = EXTERNAL_SHOCK`

is valid. The theme remains confirmed; the market-risk layer can still restrict new exposure.

## 2. Priority order for decision constraints

Highest priority first:

1. `MODEL_INDEPENDENT_HARD_RISK_GUARD` — required before production; numeric limits not yet frozen.
2. `DATA_VALIDITY / PIT_AVAILABILITY` — unavailable or stale evidence cannot be converted into a safe state.
3. `EVENT / SHOCK SOURCE + LOCAL TRANSMISSION`
4. `MARKET REGIME / INTERNAL FRAGILITY`
5. `REGIME ROUTER`
6. `THEME THESIS + THEME LIFECYCLE + DISPERSION`
7. `CATALYST + RELATIVE STRENGTH`
8. `FUNDING / CHIP + TACTICAL TIMING`
9. `STOCK SELECTION / EVIDENCE SCORE / PAYOFF`
10. `EXECUTION FEASIBILITY`

Execution feasibility is checked last in the logical chain but can still block an otherwise valid action because an unfillable order is not an executable decision.

## 3. Narrow veto semantics

A veto must specify exactly what it blocks.

### Market-risk veto

`ACTIVE_DE_RISKING` may veto **new high-beta attack exposure**.

`PENDING_TRANSMISSION` with a verified ongoing/escalating external source may veto **new high-beta attack exposure before local repricing**.

Neither state, by itself, means:

- liquidate every existing holding;
- sell at any price;
- ignore T+1 / limit-down / suspension constraints;
- invalidate a long-term theme thesis.

### Theme / lifecycle veto

`LIFECYCLE = OVERHEATED` may veto `CHASE_OK` but does not automatically invalidate the theme.

A strong RS or catalyst signal may keep the security eligible for observation / pullback entry, but cannot silently convert an overheated state into a chase state.

### Stock-specific catalyst exception

A strong company-specific catalyst may keep a stock eligible when sector breadth is weak, but it cannot override a market-level hard restriction on new attack risk.

This preserves the distinction:

`sector weak + stock-specific catalyst strong`

without turning catalyst into a universal override.

## 4. Repair semantics

`REPAIR` or `REPAIRING` means risk can be selectively reopened for evaluation.

It does not automatically:

- restore full risk budget;
- erase an ongoing shock source;
- convert all themes to risk-on;
- override hard portfolio limits.

## 5. Data-unavailable rule

For any layer with required data:

`UNAVAILABLE != NORMAL`

If a required input is unavailable or stale, the layer must emit an explicit unavailable state / missing-data flag.

No downstream component may infer a low-risk state from absence of evidence.

This is especially binding for `HEDGE / CAPITAL ROTATION`, which is currently an `UNIMPLEMENTED_DATA_LAYER`.

## 6. Formal-evaluation cadence and churn

For the first formal baseline comparison:

- one canonical market state is resolved per completed A-share trading session;
- state changes are evaluated at daily completed-session timestamps only;
- no intraday state switching is counted in the primary formal comparison;
- every day-to-day state change is counted as `STATE_FLIP`.

No arbitrary minimum-duration rule is frozen in V0.

Reason: imposing a 2-day / 3-day hold rule now would add another unvalidated parameter. Instead, state churn is a preregistered complexity penalty. If the complex model flips materially more often than the simple baseline without measurable decision benefit, it fails promotion.

A later hysteresis rule requires a new version and unused evaluation set.

## 7. Conflict examples

### A. Theme confirmed + external shock

Result:

- keep `THEME_CONFIRMED` in the evidence ledger;
- restrict new high-beta exposure if the market-risk veto is active;
- do not rewrite the theme state to OFF merely to match the market state.

### B. Strong RS + overheated lifecycle

Result:

- candidate remains observable;
- `CHASE_OK` is prohibited while the overheat condition remains resolved;
- pullback / repair timing may later re-open eligibility.

### C. Weak theme breadth + strong company catalyst

Result:

- stock may remain eligible as an idiosyncratic candidate;
- theme-level conviction is not upgraded from that one stock;
- position budget remains subject to market / portfolio constraints.

### D. Strong stock score + data unavailable upstream

Result:

- unavailable required risk data is reported explicitly;
- no claim that the full architecture approved the trade is permitted.

## 8. What remains intentionally unfrozen

- numeric minimum state duration;
- intraday hysteresis thresholds;
- exact definition of `high-beta` for veto purposes;
- exact portfolio budget reduction associated with each state;
- numeric hard-risk limits.

These are production blockers, not invitations for ad-hoc live tuning.
