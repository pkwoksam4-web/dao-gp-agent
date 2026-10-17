# 倒2 Segmented Execution V1

The project is split into six independently testable modules.

## A — Main Net Flow
Owns MAIN_NET_FLOW only. Current residual: 16 exact Tushare-semantic symbol-date keys.
Exit condition: all 16 resolved with admissible exact evidence; F11's final missing dependency closes.

## B — Market Package
Owns MARKET_BENCHMARK and MARKET_BREADTH.
Exit condition: PIT-valid benchmark and market breadth bindings are complete.

## C — Sector PIT
Owns SECTOR_SERIES, SECTOR_MEMBERSHIP_PIT and SECTOR_BREADTH.
Exit condition: historical sector series, point-in-time membership, and sector breadth are jointly reproducible.

## D — Label / Status
Owns LABEL_PROVENANCE and STATUS_SEMANTICS.
Exit condition: labels and tradability/status semantics have explicit provenance and PIT rules.

## E — GP12 Acceptance
Consumes only PASS/FROZEN checkpoints from A-D.
Exit condition: F1-F12 inputs are real and validated, strategy identity is explicit, and candidate acceptance can be reviewed without hidden dependencies.

## F — Model / Agent
Consumes E only after acceptance.
Owns Model Freeze, V2.0 source recovery, V2.1 Context Compiler / Retrieval Policy / Historical Replay, then OOS admission.

## State machine
TODO -> MATERIALIZING -> VERIFYING -> PASS or BLOCKED -> FROZEN

A-D may proceed independently. E cannot pass until A-D have PASS/FROZEN checkpoints. F cannot open OOS until E and F gates are satisfied.

## Non-negotiable rules
- no forward fill
- no silent proxy substitution
- CI success != data/model success
- module branches cannot silently mutate another module's blocker state
- completion requires evidence identity, PIT semantics, and a checkpoint
