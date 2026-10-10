# Module A — MAIN_NET_FLOW

Status: ACTIVE

## Objective
Resolve the remaining 16 exact Tushare-semantic moneyflow symbol-date keys and close F11's final missing dependency.

## Owns
- MAIN_NET_FLOW_UNBOUND

## Dependencies
- None. May run independently.

## Inputs
- data/GP12_CANDIDATE_MAIN_NET_FLOW_RESIDUAL_LEDGER_V1.json
- data/DAO2_MAIN_NET_FLOW_16_KEY_TASK_V1.json

## Expected outputs
- data/DAO2_MODULE_A_MAIN_NET_FLOW_STATE_V1.json
- data/GP12_MAIN_NET_FLOW_BINDING_V1.json
- artifact/A_MAIN_NET_FLOW_CHECKPOINT_V1.json

## State machine
TODO -> MATERIALIZING -> VERIFYING -> PASS/BLOCKED -> FROZEN

A PASS/FROZEN state must carry a verified checkpoint. CI success alone does not establish data/model success.
