# 倒2 Migration Baseline

As of: 2026-09-20

This branch is the durable handoff point from the old “倒/GP” project into “倒2”.
It is intentionally based on commit `175de3c17c0c792ee8dcaed39bf544af41184236`, not on `main`.

## Quant baseline
- Version: V4.82
- Formal window: 2020-06-01 through 2026-04-17
- Official open dates: 1426
- Frozen universe: 847
- Formal symbols: 844
- N/A symbols: 3
- Signed RAW trade rows: 1,011,607
- Frozen liquidity threshold: CNY 80,000,000
- Formal readiness: PASS
- Model freeze: CLOSED
- OOS metrics: CLOSED

## GP12 status
Strategy ID: `GP12_REBUILD_CANDIDATE_V1`

This is a newly authored reconstruction candidate. It is NOT recovered historical GP V1.1.

Validated feature families:
- market_calendar
- intraday_15m
- intraday_60m
- stock_adjusted_close

Ready factors:
- F6
- F7
- F8
- F9
- F10
- F12

Blocked factors:
- F1
- F2
- F3
- F4
- F5
- F11

Remaining hard blockers:
1. LABEL_PROVENANCE_UNBOUND
2. MAIN_NET_FLOW_UNBOUND
3. MARKET_BENCHMARK_UNBOUND
4. MARKET_BREADTH_UNBOUND
5. SECTOR_BREADTH_UNBOUND
6. SECTOR_MEMBERSHIP_PIT_UNBOUND
7. SECTOR_SERIES_UNBOUND
8. STATUS_SEMANTICS_INCOMPLETE
9. TURNOVER_RATIO_UNBOUND

Safety flags remain:
- candidate_scoring_ready=false
- real_feature_inputs_validated=false
- candidate_adoption_status=UNAPPROVED
- candidate_freeze_ready=false
- model_freeze_allowed=false
- oos_metrics_allowed=false

## Verified downstream closures
- Formal847 15m/60m coverage verified through fixed 1-minute source plus exact BaoStock fallback for 000638.SZ on 2026-04-13.
- Stock adjusted-close PIT audit: 844 PASS / 0 FAIL.
- 2,732 nominal events.
- 270 standard overrides + 11 special overrides.
- Maximum constant-scale difference 4.874600172237731 bp under 5 bp threshold.
- Special previous-close audit 11/11 PASS.

## Operating rule
Fail closed. No forward fill. No silent proxy substitution. CI success is not data/model success.
A completion claim requires forward reasoning plus reverse verification.
