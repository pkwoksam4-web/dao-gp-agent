# MARKET STRUCTURE REGIME CONTRACT V1

Status: GOVERNANCE_FROZEN / SCHEDULE_NOT_YET_SOURCE_BOUND
Production use: PROHIBITED
Formal OOS: NO
Purpose: prevent structural rule changes from being treated as one homogeneous A-share data-generating process

## 1. Principle

A-share market microstructure and transaction rules change over time. Features such as turnover, limit-up/limit-down counts, breadth, liquidity, financing activity and executable slippage do not necessarily have identical meaning across materially different rule environments.

Historical replication across incomparable rule regimes must not be described as independent robustness evidence without regime-stratified reporting.

## 2. Required regime schedule

Before formal historical evaluation, bind a source-backed, versioned `market_structure_regime_schedule_version` covering every material rule family used by the model or execution simulation.

The schedule must identify effective timestamps and authoritative sources for at least the relevant subset of:

- board / venue price-limit regimes;
- special-treatment price-limit rules;
- IPO / new-listing trading rules;
- suspension / resumption rules affecting tradability;
- margin-financing / securities-lending eligibility or material rule changes;
- transaction-cost / tax schedules;
- other material market-structure changes that alter interpretation of model inputs or fill assumptions.

This contract intentionally does not hard-code dates, percentages or fee values until authoritative evidence is bound.

## 3. Row-level regime identity

Every formal evaluation row must carry the regime identity applicable at its decision and execution timestamp.

The regime identity must be derived from the versioned schedule, not retrospectively assigned from outcome behavior.

Missing applicable regime identity fails closed for economic evaluation.

## 4. Comparable-window rule

E2/E3 reporting must distinguish:

- within-regime replication;
- cross-regime replication where feature semantics and execution assumptions remain demonstrably comparable;
- structurally incomparable windows.

A result replicated only after pooling incompatible regimes cannot be the sole basis for a robustness or promotion claim.

Where appropriate, report primary metrics, false-alarm cost, tail-risk benefit, turnover and execution-block rates separately by regime.

## 5. Feature interpretation

A feature whose economic meaning depends materially on market rules must declare that dependency.

Examples include:

- limit-up / limit-down counts;
- turnover and apparent liquidity;
- breadth when non-trading / locked securities are prevalent;
- financing / securities-lending variables;
- executable fill rates;
- transaction-cost-sensitive signals.

No historical normalization may erase the underlying rule change and then claim full semantic continuity without validation.

## 6. Execution consistency

The same regime-specific execution rules must be applied to the complex model and all baselines.

A model may not receive current trading rules while its comparator receives historical rules, or vice versa.

If an exact historical rule cannot be source-bound, the affected economic comparison remains blocked rather than using today's rule as a default.

## 7. Governance of schedule changes

Adding or correcting a regime boundary is a data/execution contract change.

If changed after evaluation outcomes were reviewed:

- version the schedule;
- identify affected rows/windows;
- invalidate any formal claim that depended on the superseded schedule until rerun under the new preregistered contract;
- do not cherry-pick only favorable windows after the correction.

## 8. Current blocker

`market_structure_regime_schedule_version` is required by formal preflight, but the authoritative historical schedule is not yet source-bound.

Therefore historical economic evaluation that depends on regime-sensitive execution or feature semantics remains blocked until that schedule is built from authoritative sources.

This is a governance blocker, not evidence that past research conclusions are false; it limits the strength of claims that can be made from pooled historical windows.
