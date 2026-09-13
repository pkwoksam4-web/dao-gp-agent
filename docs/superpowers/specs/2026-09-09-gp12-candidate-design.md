# GP12 reconstruction candidate

Status: implementation of a reviewable proposal authorized by the user's request to quickly fill the missing strategy assets. Adoption as the original GP V1.1, model freezing, and OOS execution are not authorized by this document.

## Root cause and boundary

The audited V4.82 market data gates pass, but original scorer bytes, authoritative parameters and complete factor definitions are absent. The v3.9 and v3.10 evidence ZIPs contain collectors and calendar/ST audit inputs only. Repeating negative asset searches cannot reconstruct a mathematical strategy.

Build `GP12_REBUILD_CANDIDATE_V1` as a separately identified proposal. Preserve the existing `GP_V11` recovery result, original evidence and OOS gates. Never describe proposed factor names or weights as recovered/user-approved. No candidate file is supplied to `model_freeze_recovery_v482.py` as an authoritative original asset.

## Three deliverables

1. `scripts/gp12_candidate_v1.py`: deterministic feature calculation, 12-factor scoring, ranking, research allocation/exit policy, past-only empirical probability mapping, and package-review CLI.
2. `data/GP12_CANDIDATE_PARAMETERS_V1.json`: explicit proposed weights, score thresholds, Top-N, risk and turnover policy.
3. `data/GP12_CANDIDATE_FACTORS_V1.json`: exact raw formulas, windows, normalization, aggregation, input units and missing-data behavior.

The candidate retains the previously reported 12 categories and weight clue as a proposal. All exact formulas, thresholds and execution details are newly authored choices. These choices must be adopted explicitly before freezing a new strategy version.

## Inputs and temporal contract

Scoring accepts one 121-market-date history ending at the daily snapshot, with stock/market/sector adjusted closes, daily amount in CNY, turnover as a ratio, main net flow in CNY, and market/sector breadth ratios. Calendar dates must be strictly increasing, contain exactly 121 entries, align one-to-one to rows, and end on the snapshot date. No filling across suspensions. Data must carry timezone-aware availability times no later than the snapshot. Intraday confirmation consumes five closed 15-minute and five closed 60-minute bars with individual close/availability times; both timeframes remain separate from the daily history.

The candidate is restricted to the existing Formal end `2026-04-17`. No OOS rows or outcome fields enter a scoring snapshot. Missing/unknown ST, tradability, flow, turnover, breadth, sector data or intraday data causes explicit rejection. The current validated daily panel alone does not prove these extra input families are present.

## Behavior and limits

Every factor maps a documented signed raw value to 0..100 by clipping to [-1,1] and applying 50*(1+x). Weighted sum uses the proposed weight vector summing to 100. Structure, inertia and execution layer means are separately reported. Scores are not probabilities. Probability lookup uses only completed, point-in-time labelled Formal samples, fixed score deciles and add-one smoothing, and returns unavailable when a decile has fewer than 30 observations. No calibration is claimed to have run on real data.

Top-N selection uses score descending and symbol ascending to break ties; excludes ST, non-tradable, upper-limit or non-positive 20-day momentum candidates and stocks below the frozen 80,000,000 CNY 20-market-day median amount rule. Research weights use a 10% per-name and 20% per-sector cap, with 1% capital risk per name and an 8% adverse-move threshold. Proposed exit review occurs at 3 market sessions, an 8% adverse move, or score below 45. These are proposed research plans, not actual order fills. Daily signals act no earlier than the next market session; a backtest must explicitly validate fill availability and A-share trading constraints.

## Verification

Use hand-computed flat and exponential histories, sign and scale invariance, missing/nonfinite/type/range errors, duplicated/misaligned calendar, timestamps after the snapshot, and rejection of OOS exposure. Validate ranking/sector caps and exact probability counts independently. A package review produces hashes for all three files, `historical_strategy_recovered=false`, `model_freeze_allowed=false`, `oos_metrics_allowed=false`, and a clear adoption blocker. Existing 47 recovery/admission regressions must keep passing. CI runs deterministic fixtures only and downloads no OOS data.
