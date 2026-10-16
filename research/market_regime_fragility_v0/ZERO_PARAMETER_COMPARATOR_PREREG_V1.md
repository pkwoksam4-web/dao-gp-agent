# ZERO-PARAMETER COMPARATOR PREREG V1

Status: GOVERNANCE_FROZEN / STATISTICAL_REFERENCE_ONLY
Version: `ZERO_PARAMETER_COMPARATOR_PREREG_V1`
Production use: PROHIBITED
Formal OOS authorization: NO

## 1. Comparator identity

`BASELINE_0_NO_REGIME_OVERLAY`

This is the near-zero-parameter comparator requested in addition to `MOMENTUM_VOL_REGIME_V1`.

Its rule is deliberately minimal:

> Do not alter the underlying base strategy's exposure because of the market-regime / fragility overlay.

For the ordinal risk-evidence evaluation harness, this is represented as the constant neutral score already used by the code:

`risk_evidence_score = 1`

No threshold, lookback, volatility target, state boundary or fitted weight is added.

## 2. What it measures

As a statistical reference, `BASELINE_0` asks whether a decision-active risk model contains ordinal downside-ordering information relative to **no regime discrimination at all**.

Because the score is constant, its Kendall tau-b under the frozen inference convention is `0.0`.

This reference is weaker than `BASELINE_1 = MOMENTUM_VOL_REGIME_V1`; the complex model must not be promoted merely for beating `BASELINE_0` while failing the locked `BASELINE_1` primary comparison.

## 3. Economic comparator boundary

`BASELINE_0` is not yet a fully specified PnL/exposure backtest because the project has not frozen the risk-score -> action/exposure map or the numeric portfolio-risk mandate.

When that action map is eventually frozen, the economic interpretation must remain:

- underlying base strategy exposure/action unchanged by the regime overlay;
- identical PIT universe, tradability, transaction-cost and execution assumptions as the complex model;
- no ex-post choice of a favorable fixed exposure level.

The base strategy's own exposure is inherited from the separately frozen base-strategy contract; this comparator does not introduce a new optimized exposure parameter.

## 4. Hierarchy of comparisons

Formal evaluation hierarchy remains:

1. primary: complex model versus `BASELINE_1 = MOMENTUM_VOL_REGIME_V1`;
2. secondary sanity reference: complex model versus `BASELINE_0_NO_REGIME_OVERLAY`;
3. ablations: complex model with candidate modules/states removed or collapsed.

A failure against `BASELINE_1` cannot be rescued by a favorable result against `BASELINE_0`.

## 5. No parameter fitting

No historical window may be used to tune `BASELINE_0` because there is nothing to tune.

Any future addition such as volatility scaling, target volatility, drawdown throttle or exposure cap creates a different comparator version and requires preregistration before the unused evaluation set opens.
