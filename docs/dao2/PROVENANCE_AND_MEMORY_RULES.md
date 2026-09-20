# 倒2 Provenance and Memory Rules

## Daily knowledge persistence
The Master Agent must create a daily durable archive of high-value research and chat outcomes.

Each retained item should carry:
- observed_at
- event_time when applicable
- available_at
- source
- source identity / URL / artifact
- hash when available
- revision/version
- affected entity
- confidence/evidence state
- supersedes / superseded_by links

## Deduplication
Deduplicate by evidence identity, not only by text similarity.
Revisions must not overwrite historical observations.

## Reverse verification
Before substantive completion claims:
1. forward-check the evidence chain;
2. reverse-check the conclusion back to source artifacts;
3. distinguish infrastructure success from data success and model success;
4. retain blockers when confidence is insufficient.

## Failure handling
Do not repeat a failed route when the execution environment has not materially changed.
Record:
- route attempted
- failure class
- environment state
- retry precondition
- alternative route

## Agent consistency
All specialist Agents must receive context through a shared Context Manifest / Compiler path so that:
- PIT state is consistent;
- future leakage is prevented;
- provenance is identical;
- decisions can be replayed later.
