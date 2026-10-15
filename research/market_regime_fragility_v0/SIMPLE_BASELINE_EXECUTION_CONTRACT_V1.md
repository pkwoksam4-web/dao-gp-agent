# SIMPLE BASELINE EXECUTION CONTRACT V1

Status: GOVERNANCE_PREREG
Production use: PROHIBITED
Baseline: `MOMENTUM_VOL_REGIME_V1`

## 1. Purpose

Make `BASELINE_1` exactly reproducible before any unused comparison window is opened.

This document fixes implementation semantics only. It does not claim the baseline is optimal.

## 2. Input contract

Primary series: CSI 1000 completed daily close prices.

Requirements:

- chronological order, oldest to newest;
- completed A-share trading sessions only;
- no forward-filled missing sessions;
- every close must be finite and strictly positive;
- no future data may be used at decision date `t`;
- invalid or insufficient input returns `SIMPLE_UNAVAILABLE`; no imputation.

Minimum history for one valid latest observation: `272` completed closes.

Reason: one latest `MOM20` plus 252 trailing `RV20` observations, where the earliest of those 252 `RV20` values itself requires 20 daily returns.

## 3. Return definition

Daily simple return:

`r_t = close_t / close_{t-1} - 1`

20-session momentum:

`MOM20_t = close_t / close_{t-20} - 1`

## 4. Realized-volatility definition

For each completed date `t`:

- take the latest 20 daily simple returns;
- calculate the sample standard deviation (`n-1` denominator);
- annualize by multiplying by `sqrt(252)`.

Therefore:

`RV20_t = sample_stdev(r_{t-19} ... r_t) * sqrt(252)`

The annualization factor does not change the state comparison because both current volatility and the historical median use the same scale, but it is fixed here for reproducibility.

## 5. Historical volatility reference

`RV20_MED252_t` is the median of the latest 252 completed `RV20` observations, inclusive of `RV20_t`.

No expanding-window substitute, percentile substitute, EWMA, winsorization, volatility floor, or clipping is allowed in V1.

## 6. State mapping

Exactly:

- `SIMPLE_RISK_ON` if `MOM20_t > 0` AND `RV20_t <= RV20_MED252_t`;
- `SIMPLE_RISK_OFF` if `MOM20_t < 0` AND `RV20_t > RV20_MED252_t`;
- `SIMPLE_NEUTRAL` otherwise;
- `SIMPLE_UNAVAILABLE` for insufficient / invalid input.

Boundary behavior is intentional. In particular, `RV20_t == RV20_MED252_t` can qualify for `SIMPLE_RISK_ON` but not `SIMPLE_RISK_OFF`.

## 7. Evaluation-only score mapping

- `SIMPLE_RISK_ON -> 0`
- `SIMPLE_NEUTRAL -> 1`
- `SIMPLE_RISK_OFF -> 2`
- `SIMPLE_UNAVAILABLE -> null`

`BASELINE_0 = NO_REGIME_OVERLAY` is represented for evaluation bookkeeping as constant neutral reference score `1`; this does not imply a trading action.

No baseline state maps to score `3`; score `3` is reserved for severe-risk states in the complex research architecture.

## 8. Output contract

The executable returns at least:

- `state`
- `risk_evidence_score`
- `reason`
- `mom20`
- `rv20`
- `rv20_med252`

No probability field is permitted.

## 9. Version freeze

Any later change to:

- lookback lengths;
- return definition;
- volatility estimator;
- annualization;
- median window;
- state inequalities;
- missing-data treatment;
- score mapping;

requires a new baseline version. It cannot silently overwrite V1 after an unused evaluation set is opened.
