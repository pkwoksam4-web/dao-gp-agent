# Module F — MODEL_AGENT

Status: WAITING_ON_E

## Objective
After E passes, recover Multi-Agent V2.0 reproducibly, build V2.1 replay/context contracts, then evaluate Model Freeze and finally OOS admission.

## Owns
- No upstream blocker ownership; integration/freeze stage only.

## Dependencies
- Module E verified checkpoint

## Inputs
- E checkpoint
- V2.0 source snapshot or reconstructed equivalent evidence

## Expected outputs
- data/DAO2_MODULE_F_MODEL_AGENT_STATE_V1.json
- artifact/F_MODEL_AGENT_CHECKPOINT_V1.json

## State machine
TODO -> MATERIALIZING -> VERIFYING -> PASS/BLOCKED -> FROZEN

A PASS/FROZEN state must carry a verified checkpoint. CI success alone does not establish data/model success.
