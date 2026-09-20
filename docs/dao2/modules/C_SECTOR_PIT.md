# Module C — SECTOR_PIT

Status: READY_TO_START

## Objective
Build a reproducible PIT sector package: sector series, historical membership, and sector breadth for F3/F4/F5.

## Owns
- SECTOR_SERIES_UNBOUND
- SECTOR_MEMBERSHIP_PIT_UNBOUND
- SECTOR_BREADTH_UNBOUND

## Dependencies
- None. May run independently.

## Inputs
- data/GP12_CANDIDATE_FACTORS_V1.json
- data/GP12_FORMAL_INPUT_EVIDENCE_V1.json

## Expected outputs
- data/DAO2_MODULE_C_SECTOR_PIT_STATE_V1.json
- data/GP12_SECTOR_PIT_BINDING_V1.json
- artifact/C_SECTOR_PIT_CHECKPOINT_V1.json

## State machine
TODO -> MATERIALIZING -> VERIFYING -> PASS/BLOCKED -> FROZEN

A PASS/FROZEN state must carry a verified checkpoint. CI success alone does not establish data/model success.
