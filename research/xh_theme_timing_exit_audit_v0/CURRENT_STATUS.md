# Current Status — XH Theme/Timing Exit Research

As of 2026-10-15.

This file is the authoritative status pointer for this research directory.

## Current state

```text
MA5_BREAK_EXIT_CANDIDATE_V0
  STATUS = RESEARCH_ONLY
  STANDALONE_RULE_STATUS = REJECTED_FOR_PROMOTION
  FEATURE_STATUS = RETAIN_RESEARCH_ONLY
  RULE_STATUS = NOT_FROZEN
  PRODUCTION_USE = PROHIBITED
  FORMAL_OOS = NO
  THRESHOLD_TUNING_ON_USED_WINDOWS = PROHIBITED
```

## Why the status changed

The first 2026-09-18..2026-09-24 audit was favorable. That result was then challenged with four earlier disjoint five-session windows while keeping the rule unchanged.

Mechanical Core10 stress across 40 symbol-window observations:

- fixed-hold average: -1.449%
- MA5-rule average: -1.971%
- delta: -0.522 percentage point
- positive outcomes: 14/40 -> 15/40

More relevant Core10 base-selected test across 12 selected positions:

- fixed-hold average: about -0.033%
- MA5-rule average: about -0.797%
- delta: about -0.764 percentage point
- positive outcomes: 6/12 -> 6/12

Therefore `close < MA5 -> exit next open` is not robust enough as a universal executable exit rule.

## Supersession order

Read research evidence in this order:

1. `EXIT_AUDIT_20261015.md` — initial favorable single-window audit; historical record only.
2. `DISJOINT_CORE10_ROBUSTNESS_20261015.md` — four earlier disjoint-window stress tests; supersedes the initial promotion interpretation.
3. `BASE_SELECTED_EXIT_OVERLAY_20261015.md` — existing Core10 base-selected positions; confirms the standalone rule does not improve the selected sample.
4. `CURRENT_STATUS.md` — authoritative current status.

## Governance

Do not:
- promote MA5 exit into production or the formal model;
- search MA3/MA7 or other MA lengths on the used windows;
- add two-day confirmation, percentage buffers, ATR filters, stop-losses, or take-profit thresholds by fitting these outcomes;
- reinterpret the first favorable window as proof of robustness.

Allowed next work:
- preserve `回调五日线` as author-grounded source evidence;
- treat MA5 relationship only as a descriptive tactical-state feature;
- independently preregister a Theme Lifecycle deterioration state before testing new untouched windows;
- continue prospective Shadow collection without changing `XH_REGIME_GATE_V0`.
