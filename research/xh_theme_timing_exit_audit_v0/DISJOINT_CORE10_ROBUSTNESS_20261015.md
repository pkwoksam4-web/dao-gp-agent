# Disjoint Core10 Robustness Audit — 2026-10-15

Status: **RESEARCH_ONLY / NOT_FROZEN / NOT_PRODUCTION / NOT_FORMAL_OOS**

This document is a follow-up to `EXIT_AUDIT_20261015.md`. It tests the already-defined `MA5_BREAK_EXIT_CANDIDATE_V0` **unchanged** on four disjoint historical windows that all precede the original 2026-09-18..2026-09-24 development/evaluation window.

## Rule held fixed

```text
After entry, at each daily close:
  compute trailing 5-session simple moving average of close using only data available through that close;
  if close < MA5:
      signal EXIT after close;
      execute at next trading-session open;
  otherwise continue holding;
  if no executable exit occurs before window end, exit at window-end close.
```

No MA length, threshold, execution timing, stop-loss, take-profit, confirmation day, or regime filter was changed after seeing results.

## Data carrier

Primary carrier for this audit: Neon production `market_bars`, provider=`longbridge`, period=`day`.

Universe: the same 10 Core10 symbols used in the earlier mechanical stress test. This is a **mechanical exit stress test**, not a valid entry strategy. Every name is hypothetically entered at each window's first-session open solely to test exit behavior.

## Disjoint windows

- W1: 2026-08-17 open -> 2026-08-21 close
- W2: 2026-08-24 open -> 2026-08-28 close
- W3: 2026-08-31 open -> 2026-09-04 close
- W4: 2026-09-07 open -> 2026-09-11 close

Each window contains five trading sessions and precedes the original 2026-09-18..2026-09-24 audit window.

## Results

| Window | N | Fixed-hold avg | MA5-rule avg | Improvement | Positive fixed | Positive MA5 |
|---|---:|---:|---:|---:|---:|---:|
| W1 | 10 | -4.109% | -2.472% | **+1.637 pp** | 2/10 | 5/10 |
| W2 | 10 | -0.061% | -5.344% | **-5.282 pp** | 4/10 | 0/10 |
| W3 | 10 | -5.403% | -1.200% | **+4.203 pp** | 1/10 | 3/10 |
| W4 | 10 | +3.777% | +1.132% | **-2.645 pp** | 7/10 | 7/10 |
| **ALL** | **40** | **-1.449%** | **-1.971%** | **-0.522 pp** | **14/40** | **15/40** |

## Key finding

The rule is **not stable across disjoint windows**.

It materially helps in W1 and W3, both broad-loss windows, but materially hurts in W2 and W4. Across all 40 symbol-window observations, the unchanged MA5 exit rule reduces average return by about **0.52 percentage point**, even though the count of positive outcomes rises only marginally from 14 to 15.

Therefore the favorable result observed in the original 2026-09-18..2026-09-24 window does **not** generalize mechanically to these earlier windows.

## Failure anatomy

### W2 — large whipsaw / recovery miss

The rule exits many names immediately after a close below MA5 and then misses rapid recovery later in the same five-session window.

Examples:

- 亨通光电 600487: fixed **+10.45%** vs MA5 **-6.43%**; delta **-16.88 pp**
- 中天科技 600522: fixed **+4.85%** vs MA5 **-4.85%**; delta **-9.69 pp**
- 风华高科 000636: fixed **+1.35%** vs MA5 **-7.17%**; delta **-8.52 pp**
- 通富微电 002156: fixed **+1.06%** vs MA5 **-4.88%**; delta **-5.94 pp**

This shows that a single close below MA5 can be too sensitive during rebound/repair regimes.

### W4 — strong-trend premature exits

The rule also exits several eventual winners too early during a rising five-session window.

Examples:

- 风华高科 000636: fixed **+14.50%** vs MA5 **+0.20%**; delta **-14.29 pp**
- 太极实业 600667: fixed **+11.05%** vs MA5 **+2.56%**; delta **-8.49 pp**
- 中天科技 600522: fixed **+7.45%** vs MA5 **+2.24%**; delta **-5.20 pp**
- 顺络电子 002138: fixed **+7.17%** vs MA5 **+2.92%**; delta **-4.25 pp**

This shows that MA5 deterioration cannot be treated as a universal exit instruction independent of theme/lifecycle state.

### W1/W3 — useful loss containment

The rule did help during broad-loss windows, with examples such as:

- W1 风华高科: -11.87% fixed -> +1.56% MA5
- W1 大唐发电: -6.93% -> +0.31%
- W3 太极实业: -8.79% -> +2.44%
- W3 通富微电: -7.41% -> -2.12%
- W3 中天科技: -7.55% -> -2.74%

So the rule may contain information about **deterioration state**, but it is not a stand-alone universal exit rule.

## Updated conclusion

The previous conclusion is downgraded.

```text
MA5_BREAK_EXIT_CANDIDATE_V0 = RESEARCH_ONLY
RULE_STATUS = NOT_FROZEN
STANDALONE_EXIT_RULE = NOT_SUPPORTED
UNIVERSAL_APPLICABILITY = REJECTED_BY_CURRENT_RETROSPECTIVE_STRESS
REGIME_CONDITIONAL_SIGNAL = PLAUSIBLE_BUT_UNPROVEN
PROMOTION_STATUS = NOT_ALLOWED
```

Supported now:
- a 5-day-line deterioration signal may help identify some broad-loss / deterioration episodes;
- exit behavior is strongly regime-dependent;
- Theme/Lifecycle state must remain upstream of any tactical MA5 exit signal;
- entry quality cannot be repaired by a generic moving-average exit.

Not supported:
- universal `close < MA5 -> exit`;
- production stop-loss use;
- any specific replacement such as MA3/MA7, two-day confirmation, percentage buffer, ATR filter, or regime threshold.

## Governance decision

Do **not** tune the rule on these windows. Do not search alternative MA lengths or add confirmation days based on the observed failures.

The correct next step is diagnostic, not optimization: test whether the original qualitative architecture — `Theme Thesis -> Theme Lifecycle -> Tactical State` — can explain when the same MA5 deterioration is informative versus when it is a whipsaw. Any such lifecycle-conditioned rule must be preregistered before evaluating additional windows.
