# Base-Selected Exit Overlay Audit — 2026-10-15

Status: **RESEARCH_ONLY / NOT_FROZEN / NOT_PRODUCTION / NOT_FORMAL_OOS**

## Purpose

The earlier all-name Core10 stress test mechanically entered every Core10 name. This follow-up asks a stricter question: does the unchanged `MA5_BREAK_EXIT_CANDIDATE_V0` help when applied only to names that would have been selected by the existing Core10 base ranking?

This is still retrospective and still subject to Core10 universe hindsight because the final Core10 universe was defined later. It is therefore not formal OOS evidence.

## Entry selection

For each pre-entry signal date, recompute the existing Core10 base ranking from Longbridge daily bars using the known frozen feature family:

- `return_5d`
- `return_20d`
- `return_30d`
- `realized_vol_20d`

Base score is the negative equal sum of cross-sectional percentile ranks; highest three scores are selected.

Signal dates and evaluation windows:

- W1 signal 2026-08-14 close; enter 2026-08-17 open; evaluate through 2026-08-21 close
- W2 signal 2026-08-21 close; enter 2026-08-24 open; evaluate through 2026-08-28 close
- W3 signal 2026-08-28 close; enter 2026-08-31 open; evaluate through 2026-09-04 close
- W4 signal 2026-09-04 close; enter 2026-09-07 open; evaluate through 2026-09-11 close

Exit rule remains unchanged:

```text
After entry, at each daily close:
  if close < trailing 5-session SMA(close):
      signal EXIT after close
      execute at next trading-session open
  else:
      continue holding
If no executable signal before window end, exit at window-end close.
```

## Selected positions and results

### W1

| Rank | Symbol | Fixed | MA5 |
|---:|---|---:|---:|
| 1 | 600703.SH | +0.95% | +0.29% |
| 2 | 605358.SH | -1.74% | +2.50% |
| 3 | 600522.SH | -6.07% | -8.85% |

Average: fixed **-2.287%**, MA5 **-2.020%**, delta **+0.267 pp**.

### W2

| Rank | Symbol | Fixed | MA5 |
|---:|---|---:|---:|
| 1 | 601991.SH | -1.34% | -2.01% |
| 2 | 600522.SH | +4.85% | -4.85% |
| 3 | 605358.SH | -2.92% | -3.41% |

Average: fixed **+0.197%**, MA5 **-3.423%**, delta **-3.620 pp**.

### W3

| Rank | Symbol | Fixed | MA5 |
|---:|---|---:|---:|
| 1 | 601991.SH | -3.96% | +0.69% |
| 2 | 600703.SH | +2.72% | +2.17% |
| 3 | 600392.SH | -3.47% | -0.84% |

Average: fixed **-1.570%**, MA5 **+0.673%**, delta **+2.243 pp**.

### W4

| Rank | Symbol | Fixed | MA5 |
|---:|---|---:|---:|
| 1 | 002156.SZ | +0.21% | +2.19% |
| 2 | 601991.SH | +3.21% | -0.36% |
| 3 | 002138.SZ | +7.17% | +2.92% |

Average: fixed **+3.530%**, MA5 **+1.583%**, delta **-1.947 pp**.

## Aggregate across 12 selected positions

- fixed-hold average: about **-0.033%**
- MA5-rule average: about **-0.797%**
- mean delta: about **-0.764 percentage point**
- positive outcomes: **6/12 fixed vs 6/12 MA5**

Therefore the unchanged MA5 exit overlay does **not** improve the existing Core10 base-selected sample across these four pre-development windows.

## Interpretation

The first 2026-09-18..2026-09-24 audit looked favorable, but that favorable result does not persist when the same rule is carried backward unchanged.

The failure is not limited to deliberately bad entries from the all-name stress test. It remains visible even after restricting the sample to positions selected by the existing Core10 base rank.

The rule can still reduce giveback in some windows (especially W3), but in other windows it exits eventual winners too early (especially W2 and W4).

## Status update

```text
MA5_BREAK_EXIT_CANDIDATE_V0:
  STANDALONE_RULE_STATUS = REJECTED_FOR_PROMOTION
  FEATURE_STATUS = RETAIN_RESEARCH_ONLY
  PRODUCTION_USE = PROHIBITED
  THRESHOLD_TUNING = PROHIBITED_ON_USED_WINDOWS
```

This does **not** mean the five-day-line concept contains no information. It means the binary universal instruction `close < MA5 -> exit next open` is not robust enough.

No MA3/MA7 search, confirmation-day search, ATR filter, percentage buffer, or optimized stop was run.

## Frozen-gate diagnostic

As a non-optimizing diagnostic, the already-frozen `XH_REGIME_GATE_V0` state was reconstructed at the four signal dates. It does **not** cleanly explain the MA5 successes/failures:

- W1 gate ENABLE; MA5 helps
- W2 gate DISABLE; MA5 hurts
- W3 gate DISABLE; MA5 helps
- W4 gate DISABLE; MA5 hurts

So the current frozen breadth/average-return gate is not sufficient as a conditioning variable for the MA5 exit signal.

## Next step

Do not fit a replacement exit rule on these data. The next valid research task is to preregister a richer, author-grounded **Theme Lifecycle deterioration state** independently of these exit outcomes, then test that state on a new untouched historical window. Until then, MA5 is only a descriptive state feature, not an executable exit rule.
