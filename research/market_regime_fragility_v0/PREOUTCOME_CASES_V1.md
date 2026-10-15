# INTERNAL FRAGILITY V0 — PRE-OUTCOME CASE LABELS V1

Status: RESEARCH_ONLY
Thresholds: NOT_FROZEN
Production use: PROHIBITED

This file records candidate states **before** forward-return retrieval for the dates below. Labels must not be changed solely because later returns are favorable or unfavorable.

## Case A — 2026-04-15

Contemporaneous evidence available at the close:

- Shanghai Composite approximately flat, while ChiNext fell about 1.2% after an intraday record/high opening reversal.
- 1,841 advancers versus 3,541 decliners; broad participation was materially weaker than the headline Shanghai index.
- Turnover was about CNY 2.43tn, slightly higher than the prior session rather than a liquidity-collapse day.
- Large/high-turnover technology leaders were mostly weak; public same-day reporting described profit-taking and high-level technology pressure.
- Small/mid-cap stocks were broadly weak while defensive medicine/banks received rotation flows.
- No independently verified external shock is required for the state assignment.

Pre-outcome state:

`INTERNAL_FRAGILITY_CONFIRMED`

Reasoning:

Breadth divergence was accompanied by leadership deterioration, small/mid-cap weakness, and active rotation out of higher-beta leaders. This is stronger than a breadth-only WATCH state under the preregistered field set.

## Case B — 2026-09-09

Contemporaneous evidence available at the close:

- Shanghai Composite +0.28%, Shenzhen +0.15%, ChiNext -0.14%; headline indices were mixed/near flat.
- More than 3,600 stocks declined.
- Micro-cap / speculative participation weakened; several prior high-level momentum names hit limit-down and the continuation rate fell below 30%.
- High-priced / recent technology listings and previously strong hardware names showed deterioration or failed intraday continuation.
- Turnover contracted to about CNY 1.86tn, indicating a low-liquidity / stock-selection environment rather than active broad distribution.
- Leadership rotated toward agriculture, shipping, coal, fertilizer and selected consumption names; the market lacked broad multi-theme participation.

Pre-outcome state:

`INTERNAL_FRAGILITY_CONFIRMED`

Reasoning:

Breadth weakness, leadership deterioration and micro/small-cap stress aligned. Contracting turnover lowers expected severity versus an active-distribution case, but under the current categorical semantics it still satisfies multi-evidence fragility rather than breadth-only WATCH.

## Locked interpretation before outcomes

- A favorable forward path for either case will count as `FALSE_ALARM_COST`; the label will not be retrospectively downgraded.
- A shallow/transient decline will count as `MILD_WARNING`, not a tail-risk success.
- A persistent or severe decline will count as supportive evidence for `CONFIRMED`.
- These dates become consumed research windows immediately after outcome retrieval and cannot be reused as formal OOS.
