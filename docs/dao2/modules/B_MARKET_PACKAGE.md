# Module B — MARKET_PACKAGE

Status: READY_TO_START

## Objective
Bind PIT-valid market benchmark and market breadth inputs for F1/F2 and shared F3 dependencies.

## Owns
- MARKET_BENCHMARK_UNBOUND
- MARKET_BREADTH_UNBOUND

## Dependencies
- None. May run independently.

## Inputs
- data/GP12_CANDIDATE_FACTORS_V1.json
- data/GP12_FORMAL_INPUT_EVIDENCE_V1.json

## Expected outputs
- data/DAO2_MODULE_B_MARKET_PACKAGE_STATE_V1.json
- data/GP12_MARKET_PACKAGE_BINDING_V1.json
- artifact/B_MARKET_PACKAGE_CHECKPOINT_V1.json

## State machine
TODO -> MATERIALIZING -> VERIFYING -> PASS/BLOCKED -> FROZEN

A PASS/FROZEN state must carry a verified checkpoint. CI success alone does not establish data/model success.
