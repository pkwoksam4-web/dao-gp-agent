# MARKET REGIME / FRAGILITY V0

Status: RESEARCH_ONLY
Production use: PROHIBITED
Thresholds: NOT_FROZEN
Formal OOS: NO

## Purpose

Test whether the 2026-10-15 model changes improve risk-state recognition without overfitting one shock window.

Research layers under test:

1. EVENT / EXTERNAL SHOCK GATE
2. INTERNAL FRAGILITY
3. MARKET REGIME ROUTER
4. HEDGE / CAPITAL ROTATION FOOTPRINT
5. THEME BREADTH + DISPERSION
6. RELATIVE STRENGTH-FIRST routing under stress
7. SHOCK ABSORPTION / REPAIR before exit decisions

No production-core weights are changed by this research.

## Frozen research principles

- Shock detection may freeze NEW high-beta risk, but does not mechanically force an open-price liquidation.
- Theme strength does not imply good entry timing.
- Theme breadth is contemporaneous confirmation, not a next-day shock predictor.
- External shock evidence can override a previously strong local theme state.
- Internal fragility is a candidate state, not a binary sell signal.
- No numerical thresholds are frozen from the historical windows below.

## Historical diagnostic windows already consumed

### 2026-08-14 to 2026-08-24 — external shock / rotation

Observed structure:
- 08/17 local technology breadth was strong.
- 08/18 local futures evidence alone did not show a clear crash warning.
- Overnight external stress into 08/19 (US technology / semiconductor weakness, rates / commodity / geopolitical pressure) materially changed the state.
- 08/19 A-share technology sold off broadly with higher turnover.
- Post-shock relative-strength / low-beta rotation into banks, coal and other defensive assets was materially better than continuing to hold broad high-beta technology.

Diagnostic conclusion:
- EVENT / EXTERNAL SHOCK layer: SUPPORTED.
- Domestic hedge footprint alone: INSUFFICIENT.
- Stress router: SUPPORTED.

### 2026-06-05 to 2026-06-15 — shock absorption counterexample

Observed structure:
- A large US semiconductor shock preceded the 06/08 A-share gap-down.
- A forced open liquidation would have crystallized the gap loss.
- Several technology names repaired materially during the same session.
- Post-shock repair quality was highly dispersed: semiconductor equipment materially outperformed broad AI hardware in the following days.

Diagnostic conclusion:
- `SHOCK -> SELL AT OPEN` = REJECTED.
- `SHOCK -> FREEZE_NEW_RISK -> OBSERVE_ABSORPTION -> REASSESS` = RETAIN.
- Micro-theme dispersion after shock: SUPPORTED.

### 2026-06-25 to 2026-06-26 — internal fragility positive case

Observed structure on 06/25:
- Major growth indices rose strongly.
- Total turnover was very high.
- More than 4,200 stocks nevertheless declined.
- Leadership was concentrated in semiconductor / AI hardware weights and a limited set of strong themes.
- Crowding / realization risk was already visible in public same-day market commentary.

Outcome:
- 06/26 broad market and high-beta growth sold off sharply.

Diagnostic conclusion:
- Internal breadth / index divergence contains useful risk information.
- A strong index is not sufficient evidence of a healthy risk-on regime.

## Control / false-positive checks

### 2026-04-13 — breadth weakness without immediate breakdown

Same-day evidence:
- Major indices were mixed / slightly positive.
- More than 3,500 stocks declined.
- Turnover contracted.
- AI hardware and batteries remained selectively strong.

Following session:
- Shanghai Composite rose materially on 04/14 rather than breaking down.

Interpretation:
- Breadth weakness alone would have generated a false alarm.
- `INTERNAL_FRAGILITY` cannot be a one-factor breadth trigger.

### 2026-09-03 — breadth weakness followed by mild decline and fast repair

Same-day evidence:
- Major indices closed around flat.
- More than 3,500 stocks declined.
- Turnover remained below 2 trillion and contracted again.
- High-level speculative names were already under pressure.

Following path:
- 09/04 indices weakened modestly.
- 09/07 growth index repaired strongly.

Interpretation:
- Fragility evidence was real, but severity was lower than the 06/25 case.
- The model needs a severity / persistence state, not a binary fragility flag.

### 2026-05-26 — breadth divergence with leadership deterioration

Same-day evidence:
- More than 4,000 stocks declined.
- Small / micro-cap pressure intensified.
- High-level momentum names failed and loss-making effects increased.
- Index-level damage was initially contained by technology weights.

Following session:
- 05/27 Shanghai Composite fell materially and market breadth deteriorated further.

Interpretation:
- Breadth divergence is more informative when combined with leadership deterioration and small-cap stress.

## Current structural conclusion

Internal fragility should be treated as a multi-evidence state, conceptually:

`Breadth divergence`
+ `leadership concentration / crowding`
+ `leadership deterioration or failed continuation`
+ `small-cap / median-stock weakness`
+ `turnover / liquidity-state context`
+ optional `external / derivative stress`

No weights or hard thresholds are frozen.

## Current state machine candidate

- NORMAL_RISK_ON
- NORMAL
- INTERNAL_FRAGILITY_WATCH
- INTERNAL_FRAGILITY_CONFIRMED
- EXTERNAL_SHOCK
- ACTIVE_DE_RISKING
- REPAIR

These labels are research semantics only.

## Next validation requirements

1. Add additional normal-market controls specifically selected to challenge the fragility hypothesis.
2. Use disjoint dates not used to invent thresholds.
3. Measure 1D / 3D / 5D index and representative high-beta outcomes from the signal close.
4. Track false alarms separately from tail-risk saves.
5. Do not convert this research into production until a preregistered rule and a genuinely unused validation window exist.
