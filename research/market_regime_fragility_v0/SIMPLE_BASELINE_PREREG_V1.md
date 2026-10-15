# SIMPLE BASELINE PREREG V1

Status: GOVERNANCE_PREREG
Purpose: require the complex regime / fragility architecture to prove incremental value over simple alternatives
Production use: PROHIBITED

## 1. Baselines

### BASELINE_0 — NO_REGIME_OVERLAY

Definition:

- stock-selection core remains unchanged;
- no market-regime veto, fragility state, shock state or router is applied;
- serves as the null reference for whether any overlay adds value at all.

### BASELINE_1 — MOMENTUM_VOL_REGIME_V1

A deliberately simple, PIT-computable two-factor regime classifier using CSI 1000 daily data only.

Inputs at decision date `t`:

- `MOM20_t = close_t / close_{t-20} - 1`
- `RV20_t = realized volatility of daily returns over the latest 20 completed sessions`
- `RV20_MED252_t = median of RV20 values over the trailing 252 completed sessions, using data available at t only`

No parameter may be retuned after evaluation starts.

State mapping:

- `SIMPLE_RISK_ON`: `MOM20_t > 0` AND `RV20_t <= RV20_MED252_t`
- `SIMPLE_RISK_OFF`: `MOM20_t < 0` AND `RV20_t > RV20_MED252_t`
- `SIMPLE_NEUTRAL`: all other combinations

Notes:

- 20-session momentum / volatility and a trailing 252-session median are fixed ex-ante conventions for the baseline, not optimized claims.
- this baseline intentionally ignores breadth, themes, news, derivatives, catalysts and event semantics;
- missing or insufficient history => `SIMPLE_UNAVAILABLE`, never imputed from future data.

## 2. Why this baseline exists

The research architecture has many states and explanatory variables. Complexity is only justified if it improves decision quality relative to a transparent rule that is cheap, reproducible and hard to overfit.

The complex model must beat both:

1. doing nothing (`BASELINE_0`);
2. the simple two-factor regime (`BASELINE_1`).

## 3. Evaluation unit

Primary sampling unit:

- one decision timestamp per completed A-share trading session for frequent regime / fragility evaluation;
- shock episodes are additionally grouped into non-overlapping event episodes so one multi-day shock cannot be counted as many independent successes.

Episode-independence logic must be locked before any formal unused evaluation set is opened.

## 4. Outcomes

The risk layer is evaluated against future downside / repair behavior of CSI 1000 because the current fragility hypothesis concerns broad / median-stock risk.

Record, without choosing the best horizon after the fact:

- forward 1D return;
- forward 3D return;
- forward 5D return;
- worst close-to-close drawdown within the 3D horizon;
- worst close-to-close drawdown within the 5D horizon.

Primary horizon for the first formal comparison: `3D`.

1D and 5D are secondary diagnostics unless a new preregistered version changes this before seeing outcomes.

## 5. Model output normalization for comparison

No probability is assumed.

The complex model and simple baseline must each emit an ordinal `RISK_EVIDENCE_SCORE`, not a calibrated probability.

For comparison only:

- `0 = risk-on / normal acceptance`
- `1 = caution / neutral`
- `2 = restricted risk / fragility`
- `3 = severe risk / active de-risking`

Mapping from each model's native states to this score must be locked before the formal evaluation window.

This score is an ordering device only. It must never be described as a probability of decline.

## 6. Primary endpoint

Primary endpoint:

`3D downside concordance`

Question:

> Does a higher preregistered `RISK_EVIDENCE_SCORE` correspond to worse forward 3D downside outcomes more consistently than `BASELINE_1`?

Use an ordinal concordance / rank-based statistic fixed before evaluation. Report the effect size and confidence interval; do not rely on hit rate alone.

The exact inference implementation must be committed before opening the unused evaluation set.

## 7. Required secondary accounting

Regardless of the primary result, report:

- `TAIL_RISK_SAVE`: risk episodes correctly identified early enough to reduce exposure under an identical downstream action policy;
- `FALSE_ALARM_COST`: positive forward performance forgone or unnecessary restriction caused by high-risk flags;
- `MILD_WARNING`: cases where the model was directionally useful but severity was overstated / understated;
- `REPAIR_CAPTURE`: cases where the model reopened risk after prior stress without excessive delay;
- state turnover / flip count;
- data-unavailable rate.

The same accounting definitions must be used for BASELINE_1 and the complex model.

## 8. Failure conditions

The complex regime layer fails promotion if, on the preregistered unused evaluation set, any of the following holds:

1. primary endpoint does not beat `BASELINE_1` under the locked test;
2. any apparent improvement disappears after required multiple-testing correction;
3. incremental tail-risk benefit is offset by materially worse false-alarm cost under the same action mapping;
4. state churn / implementation complexity rises without measurable decision benefit;
5. performance depends on unavailable-at-the-time data;
6. results require post-hoc exclusion of adverse episodes;
7. missing-data frequency prevents reliable real-time use.

Secondary metrics cannot override failure of the primary endpoint.

## 9. Sample-size rule

No arbitrary minimum event count is frozen here.

Before formal promotion testing, the project must commit:

- minimum effect worth detecting versus BASELINE_1;
- desired power;
- significance level;
- dependence / clustering treatment for multi-day episodes;
- resulting minimum sample / episode requirement.

Until that calculation is committed, promotion beyond `RESEARCH_ONLY` is prohibited.

## 10. Multiple testing

- one primary comparison: complex model vs BASELINE_1 on the locked 3D endpoint;
- BASELINE_0 is a secondary null reference;
- additional horizons / subgroups / states are exploratory unless preregistered as separate primary hypotheses;
- if more than one primary hypothesis is introduced in a later version, use the governance document's Holm family-wise correction.

## 11. Execution separation

This prereg first tests whether the regime layer contains incremental information.

It does **not** yet claim economic tradability. A later execution layer must apply A-share constraints (T+1, limit-up/down, suspensions, liquidity, capacity, fees, slippage, financing availability) identically to all compared models before any production PnL claim.

## 12. Promotion interpretation

Passing this baseline comparison is necessary, not sufficient.

A pass means only:

`the added regime architecture shows incremental decision information versus a simple momentum+volatility classifier on a preregistered unused set.`

It does not by itself authorize production use, numeric position sizing, or calibrated probability language.