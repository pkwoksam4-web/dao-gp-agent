# 倒2 Next Execution Order

## P0 — Preserve the verified baseline
Do not restart from V4.76.
Do not use main as the source of truth.
Use this branch and the V4.82 GP12 readiness chain as the active baseline.

## P1 — Close the nine remaining blockers
Priority should favor shared data families that unlock multiple blocked factors.

Current blockers:
- LABEL_PROVENANCE_UNBOUND
- MAIN_NET_FLOW_UNBOUND
- MARKET_BENCHMARK_UNBOUND
- MARKET_BREADTH_UNBOUND
- SECTOR_BREADTH_UNBOUND
- SECTOR_MEMBERSHIP_PIT_UNBOUND
- SECTOR_SERIES_UNBOUND
- STATUS_SEMANTICS_INCOMPLETE
- TURNOVER_RATIO_UNBOUND

For every closure:
1. Materialize real source evidence.
2. Verify PIT availability.
3. Record artifact identity/hash.
4. Cross-check against an independent route when material.
5. Update a downstream checkpoint only.
6. Do not mutate frozen evidence retroactively.

## P2 — Recover Multi-Agent V2.0 source snapshot
The architecture and recorded 73/73 test state are inherited, but the source snapshot must be recovered before claiming reproducibility.

Required components:
- Research Data Lake
- PIT Feature Store
- Knowledge Graph
- Unified Query
- Context Manifest hash
- DataPlatform Auditor
- EOD hash-chain

## P3 — Build V2.1
- Context Compiler
- Retrieval Policy
- Historical Replay Engine

The goal is deterministic point-in-time context reconstruction for every Agent and every historical decision.

## P4 — Strategy approval / recovery gate
Only after all required real inputs are bound:
- either recover the historical GP strategy assets exactly,
- or formally approve a new strategy candidate as a new strategy.

Do not blur these two paths.

## P5 — Model Freeze
Only after strategy identity, factors, parameters, labels, input lineage and PIT contracts are all closed.

## P6 — OOS
Formal OOS is the final stage.
No performance claim before the OOS admission gate opens.
