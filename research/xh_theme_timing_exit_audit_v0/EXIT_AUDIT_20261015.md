# XH Theme/Timing Exit Audit V0 — 2026-10-15

Status: **RESEARCH_ONLY / NOT_FROZEN / NOT_PRODUCTION / NOT_FORMAL_OOS**

## Objective

Test whether an author-grounded tactical-location idea around the **5-day line** can improve exit discipline after an entry has already been selected by the current hierarchical model:

`Market Regime -> Theme Thesis -> Theme Lifecycle -> Tactical Timing -> Funding/Stock Quality -> Odds/Risk`

This audit does **not** change or replace `XH_REGIME_GATE_V0`, and does not modify the formal stock-selection model.

## Evidence boundary

Historical decision window used for the current audit: 2026-09-10..2026-09-17.
Evaluation window: 2026-09-18 open through 2026-09-24 close.

Execution convention:
- signal is only known after the daily close;
- exit is executed at the **next trading-session open**;
- no same-day hindsight execution;
- if no exit signal occurs, hold through the fixed 2026-09-24 close.

Data carriers used:
- Eastmoney exact daily OHLCV API responses for the cross-sector sample;
- Neon production `market_bars` (Longbridge daily carrier) for Core10 cross-check.

## Candidate exit rule

Name: `MA5_BREAK_EXIT_CANDIDATE_V0`

Descriptive rule:

```text
After entry, at each daily close:
  compute trailing 5-session simple moving average of close.
  if close < MA5:
      mark EXIT signal after close
      execute exit at next session open
  else:
      continue holding
```

Important attribution boundary:
- `回调五日线` is author-side Xiaohan evidence.
- Treating a **close below MA5 as an exit trigger** is a **MODEL INFERENCE**, not an author quote.
- No production threshold is frozen from this audit.

## Selected-position audit

Previously selected/conditional positions included in this exit test:

| Stock | Fixed hold return | MA5-rule return | Exit signal |
|---|---:|---:|---|
| 立昂微 605358 | +4.50% | +4.50% | none |
| 比亚迪 002594 | +0.40% | +0.32% | 2026-09-18 close -> 2026-09-21 open |
| 恒瑞医药 600276 | +3.08% | +3.08% | none |
| 伊利股份 600887 | +1.36% | +1.36% | none |
| 中际旭创 300308 | -1.56% | +0.94% | 2026-09-23 close -> 2026-09-24 open |
| 亨通光电 600487 | -3.74% | -0.29% | 2026-09-23 close -> 2026-09-24 open |
| 顺络电子 002138 | +0.75% | +0.75% | none |

Summary:
- fixed-hold mean: **+0.683%**
- MA5-rule mean: **+1.521%**
- positive outcomes: **5/7 -> 6/7**
- mean improvement: about **+0.84 percentage point**

The improvement is concentrated in preventing late-period giveback in 中际旭创 and 亨通光电. 比亚迪 is a small false-positive cost: +0.40% fixed becomes +0.32% under the MA5 rule.

## Core10 mechanical stress test

For all 10 Core10 names, if one mechanically enters every name at 2026-09-18 open regardless of the entry model, then compares fixed hold vs the same MA5 exit rule:

- fixed-hold average return: **-2.162%**
- MA5-rule average return: **+0.014%**
- positive outcomes: **3/10 -> 6/10**
- average improvement: **+2.176 percentage points**

Examples:
- 风华高科: -3.38% -> +0.78%
- 亨通光电: -3.74% -> -0.29%
- 中天科技: -5.69% -> -3.25%
- 太极实业: -8.36% -> -5.10%
- 三安光电: -4.08% -> -1.38%
- 大唐发电: -2.72% -> +1.27%

This is a stress test only; it is **not** a valid strategy because the entry model would not buy all ten names.

## Cross-sector stress test

Across 12 mechanically entered cross-sector names with exact Eastmoney OHLCV:

- fixed-hold average: about **-1.57%**
- MA5-rule average: about **-0.22%**
- positive outcomes: **5/12 -> 7/12**

Again, this is not a tradable strategy because AVOID/WATCH names were intentionally included as stress cases.

## Important failure case

招商轮船 shows why the exit layer cannot rescue a bad entry:

- fixed hold: **-3.15%**
- MA5 exit: **-3.75%**

The stock broke down with a gap before the close-based exit could execute. This supports the hierarchy:

`Entry Gate first -> Exit State Machine second`

The exit layer must not be used to justify chasing an already crowded/accelerated theme.

## Current conclusion

Evidence from this single historical window supports keeping a 5-day-line deterioration signal as an **exit research candidate**.

Current status:

```text
MA5_BREAK_EXIT_CANDIDATE_V0 = RESEARCH_ONLY
RULE_STATUS = NOT_FROZEN
PROMOTION_STATUS = NOT_ALLOWED
FORMAL_OOS = NO
```

What is supported:
- late giveback risk exists even when the initial stock selection was directionally useful;
- an MA5-based deterioration state can reduce giveback in this window;
- entry quality remains more important than exit rescue;
- Theme/Lifecycle/Timing should apply to exits as well as entries.

What is not supported yet:
- long-run win rate;
- optimal holding period;
- optimal MA definition;
- production stop-loss or take-profit threshold;
- universal applicability across sectors;
- promotion into the formal model.

## Next research step

Do not tune thresholds on this window. The next work item is to run the already-written `MA5_BREAK_EXIT_CANDIDATE_V0` unchanged over additional disjoint historical windows and report descriptive stability only. Any result from those windows remains retrospective robustness evidence, not formal prospective OOS.
