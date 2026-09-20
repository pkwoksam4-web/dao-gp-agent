# 倒2 Migration Baseline

As of: 2026-09-20

This branch is the durable handoff from the old 倒/GP project into 倒2. The active baseline is V4.82; do not restart from V4.76 and do not treat main as the source of truth.

## Quant baseline
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

## Validated GP12 feature families
- amount_turnover
- intraday_15m
- intraday_60m
- market_calendar
- stock_adjusted_close

Ready factors: F6, F7, F8, F9, F10, F12.
Blocked factors: F1, F2, F3, F4, F5, F11.
F11 now lacks only main_net_flow.

## Remaining hard blockers: 8
1. LABEL_PROVENANCE_UNBOUND
2. MAIN_NET_FLOW_UNBOUND
3. MARKET_BENCHMARK_UNBOUND
4. MARKET_BREADTH_UNBOUND
5. SECTOR_BREADTH_UNBOUND
6. SECTOR_MEMBERSHIP_PIT_UNBOUND
7. SECTOR_SERIES_UNBOUND
8. STATUS_SEMANTICS_INCOMPLETE

## Newly inherited verified closure: amount_turnover
- BaoStock full Formal panel run: 34937058721
- Artifact: 10383758045
- 844 symbols / 1,011,607 turnover rows
- missing=0, extra=0, duplicate=0, bad_turnover=0, unresolved_symbol=0
- source semantics verified
- turnover_ratio_pit_verified=true
- downstream readiness run: 34938907264
- readiness artifact: 10383992824
- TURNOVER_RATIO_UNBOUND is closed
- candidate/model/OOS gates remain closed

## Main-net-flow residual state
The family is NOT closed yet, but it is no longer a broad source-discovery problem:
- expected rows: 1,011,607
- resolved: 1,011,591
- unresolved: 16
- resolved fraction: 0.9999841835811734
- remaining task: recover exact Tushare-semantic values for 16 symbol-date keys
- no generic main-flow proxy is admissible

## Safety
GP12_REBUILD_CANDIDATE_V1 remains UNAPPROVED.
Historical GP V1.1 is not recovered.
candidate_scoring_ready=false
model_freeze_allowed=false
oos_metrics_allowed=false

Fail closed. No forward fill. No silent proxy substitution. CI success is not data/model success. Completion claims require forward reasoning plus reverse verification.
