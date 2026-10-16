# PRIMARY INFERENCE PREREG V1

Status: GOVERNANCE_PREREG
Inference version: `PRIMARY_3D_DOWNSIDE_CONCORDANCE_V1`
Production use: PROHIBITED

## 1. Primary question

Does the complex regime / fragility architecture rank future 3-session downside severity better than the locked simple baseline `MOMENTUM_VOL_REGIME_V1` on a genuinely unused, preregistered evaluation set?

The inference target is incremental information, not trading PnL and not calibrated probability.

## 2. Primary horizon and outcome

Primary horizon: `3 completed A-share trading sessions`.

For each eligible decision timestamp `t`:

`forward_return_3d = close_{t+3} / close_t - 1`

Primary downside-severity outcome:

`downside_severity_3d = -forward_return_3d`

Higher downside severity therefore means worse subsequent performance.

1D and 5D outcomes remain secondary diagnostics and cannot replace the primary endpoint after outcomes are observed.

## 3. Model inputs to the inference layer

At each timestamp both models must emit the preregistered ordinal `RISK_EVIDENCE_SCORE` on the same PIT information set.

Allowed score values: `0, 1, 2, 3`.

Rows with an unavailable score for either compared model are not silently converted to NORMAL. Their exclusion count and unavailable rate must be reported.

The exact missing-data comparison policy must be identical across compared models and locked in the evaluation-set manifest before opening the set.

## 4. Primary statistic

For each model compute tie-aware Kendall `tau-b` between:

- model `RISK_EVIDENCE_SCORE`, and
- `downside_severity_3d`.

Higher positive `tau-b` means higher risk evidence tends to align with worse future 3-session outcomes.

Primary incremental estimand:

`delta_tau = tau_complex - tau_baseline_1`

Primary directional hypothesis:

`H1: delta_tau > 0`

`BASELINE_0 = NO_REGIME_OVERLAY` remains a secondary null reference and does not replace the primary complex-vs-BASELINE_1 comparison.

## 5. Tie / degenerate convention

If an input series has no comparable ordering information and the Kendall denominator is zero, its `tau-b` is represented as `0.0` for this harness.

This means "no ordinal information"; it must not be described as evidence of no market risk.

## 6. Dependence and uncertainty

Daily 3-session forward returns mechanically overlap. The primary uncertainty method is therefore a paired circular block bootstrap.

Locked primary settings:

- block length: `3 sessions`, equal to the primary forward horizon;
- bootstrap resamples the complex score, baseline score and future outcome together by identical indices;
- default replications: `5000`;
- deterministic seed: `20261016`;
- two-sided confidence interval level: `95%` for `delta_tau`;
- primary directional test: one-sided `delta_tau > 0` with `alpha = 0.05`.

The block length is a preregistered dependence treatment for the mechanical 3-session overlap, not an optimized market parameter.

If later evidence shows this uncertainty method is materially inadequate, it requires a new inference version before any new unused set is opened. The current unused set may not be used to choose a replacement method.

## 7. Promotion interpretation

For promotion eligibility the complex model must, at minimum:

1. have positive observed `delta_tau`;
2. satisfy the locked primary comparison test against BASELINE_1;
3. report the bootstrap confidence interval;
4. satisfy the separately frozen sample-size / power requirement;
5. report false-alarm cost, tail-risk save, repair capture, churn and data-unavailable rate;
6. remain valid under all governance and execution preconditions.

Passing this statistic is necessary, not sufficient, for promotion.

## 8. Anti-rescue rules

The primary result may not be rescued by:

- selecting 1D or 5D after seeing 3D failure;
- dropping adverse episodes not excluded ex ante;
- changing state mappings after seeing outcomes;
- changing the bootstrap method after seeing outcomes;
- replacing BASELINE_1 with an easier comparator;
- citing descriptive case studies as formal OOS evidence.

Any such change creates a new research version and requires a new unused evaluation set.
