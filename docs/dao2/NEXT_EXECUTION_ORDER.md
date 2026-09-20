# 倒2 Next Execution Order

## P0 — Preserve the verified V4.82 baseline
Do not restart from V4.76. Do not use main as the source of truth.

## P1A — Close MAIN_NET_FLOW_UNBOUND by exact residual recovery
This is now the first priority because amount_turnover is already PIT-verified and F11 lacks only main_net_flow.

Current main-net-flow state:
- Formal expected rows: 1,011,607
- Resolved rows: 1,011,591
- Unresolved rows: 16
- Required semantics: exact Tushare moneyflow large + extra-large active buy/sell buckets
- Generic “main flow” substitutes are not admissible

For the 16 residual keys:
1. recover exact semantic values or admissible exact-zero proof;
2. bind source identity and availability;
3. cross-check where material;
4. update a downstream checkpoint;
5. keep F11 blocked until all 16 are resolved.

## P1B — Remaining seven blockers after main-net-flow work
- LABEL_PROVENANCE_UNBOUND
- MARKET_BENCHMARK_UNBOUND
- MARKET_BREADTH_UNBOUND
- SECTOR_BREADTH_UNBOUND
- SECTOR_MEMBERSHIP_PIT_UNBOUND
- SECTOR_SERIES_UNBOUND
- STATUS_SEMANTICS_INCOMPLETE

Prefer shared data chains: market benchmark + market breadth can unlock F1/F2 and contribute to F3; sector series + PIT membership + sector breadth jointly unlock F3/F4/F5.

## P2 — Recover Multi-Agent V2.0 source snapshot
Recover the recorded 73/73 implementation for Research Data Lake, PIT Feature Store, Knowledge Graph, Unified Query, Context Manifest, Auditor and EOD hash-chain.

## P3 — V2.1
Build Context Compiler, Retrieval Policy and Historical Replay Engine.

## P4 — Strategy approval/recovery
Either recover historical GP assets exactly or formally approve the new candidate as a new strategy. Never blur these paths.

## P5 — Model Freeze
Only after strategy identity, parameters, labels, all required real inputs, lineage and PIT contracts are closed.

## P6 — OOS
No performance claim before the OOS admission gate opens.
