# Project Response Quality Rule

Status: project-level operating rule requested by the user for the GP / dao-gp-agent project.

## Core requirement

Before giving a substantive answer, recommendation, implementation decision, progress claim, or completion claim, aim for very high confidence in the reasoning and evidence. The user's shorthand target is **95% confidence**. This is an operating threshold, not a statistically calibrated probability claim.

If the answer is not yet sufficiently well-supported, do not rush to a conclusion. Continue verification, change the investigative path, or explicitly mark the unresolved uncertainty.

## Required reasoning discipline

For material conclusions, use both directions of validation:

1. **Forward reasoning** — derive the proposed answer from the available evidence, project contracts, tests, artifacts, source data, and current repository state.
2. **Reverse check** — assume the proposed answer is wrong and actively search for the strongest failure mode, contradictory evidence, hidden assumption, alternative explanation, stale state, provenance problem, or boundary-condition violation.
3. **Evidence refresh** — when correctness depends on current repository state, data, APIs, CI, artifacts, hashes, dates, or external facts, verify them with the relevant tool rather than relying only on memory or an earlier report.
4. **Fail closed** — if a material dependency remains unresolved, preserve the blocker. Do not infer PASS, do not fabricate evidence, and do not substitute a weaker proxy merely to produce a complete answer.
5. **State uncertainty clearly** — when the evidence cannot support a high-confidence conclusion, report what is known, what is not known, and the shortest path to resolution.

## Completion claims

Before saying work is complete, fixed, PASS, production-ready, or verified:

- check the latest relevant commit/branch state;
- run or inspect the fresh relevant tests/workflow;
- inspect the actual artifact/output when the claim depends on it;
- compare expected vs observed invariants;
- reverse-check whether a green workflow could still contain a fail-closed data gate;
- distinguish infrastructure success from data/model success.

A green workflow is not automatically a green data gate. Network/source failure is not a factor/model FAIL. Historical recovery evidence must not be confused with a newly authored candidate model.

## Project-specific application

This rule applies to the GP project, including but not limited to:

- GP V1.1 historical strategy recovery;
- V4.82 Formal / QFQ / PIT-ST / RAW / Liquidity evidence;
- OOS Admission and OOS isolation;
- GP12 reconstruction candidate work;
- source adapters and production data binding;
- readiness, model-freeze, adoption, and performance-gate decisions;
- progress reports and blocker status.

When two interpretations are plausible, prefer the one that preserves provenance, PIT correctness, reproducibility, and fail-closed behavior until evidence resolves the ambiguity.
