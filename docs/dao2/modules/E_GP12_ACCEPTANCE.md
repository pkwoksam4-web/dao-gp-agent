# Module E — GP12_ACCEPTANCE

Status: WAITING_ON_A_TO_D

## Objective
Integrate only verified checkpoints from A-D, verify F1-F12 real inputs and strategy identity, then run candidate acceptance.

## Owns
- No upstream blocker ownership; integration/freeze stage only.

## Dependencies
- Module A verified checkpoint
- Module B verified checkpoint
- Module C verified checkpoint
- Module D verified checkpoint

## Inputs
- A checkpoint
- B checkpoint
- C checkpoint
- D checkpoint
- data/GP12_CANDIDATE_FACTORS_V1.json
- data/GP12_CANDIDATE_PARAMETERS_V1.json

## Expected outputs
- data/DAO2_MODULE_E_GP12_ACCEPTANCE_STATE_V1.json
- artifact/E_GP12_ACCEPTANCE_CHECKPOINT_V1.json

## State machine
TODO -> MATERIALIZING -> VERIFYING -> PASS/BLOCKED -> FROZEN

A PASS/FROZEN state must carry a verified checkpoint. CI success alone does not establish data/model success.
