# GP12 Candidate Implementation Plan

> For agentic workers: execute inline with the executing-plans workflow; use requesting-code-review for an independent review once the candidate exists.

**Goal:** Supply reviewable scorer code, parameters and exact definitions without claiming recovery of the lost strategy.

**Architecture:** A standard-library scorer consumes explicit point-in-time snapshots. Two JSON contracts carry proposed parameters and formulas. A review command emits byte hashes and keeps original-model recovery and OOS disabled.

**Tech Stack:** Python 3.12 standard library, unittest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-09-gp12-candidate-design.md`

## Global constraints

- Strategy ID `GP12_REBUILD_CANDIDATE_V1`; all newly authored rules are proposals.
- Formal end `2026-04-17`; frozen liquidity threshold `80_000_000` CNY.
- No edits to existing recovery, Formal or OOS gate files.
- No data filling, invented probabilities, original-model provenance claims or automatic model freeze.

## Task 1: Implement the complete candidate package

Files: create the three deliverables in the spec and `scripts/test_gp12_candidate_v1.py`.

Interfaces: `score_snapshot(snapshot, parameters) -> dict`; `rank_candidates(scores, parameters) -> list[dict]`; `exit_reasons(position, score, parameters) -> list[str]`; `probability_lookup(rows, query_score, horizon, as_of) -> dict`; `review_package(parameters_path, factors_path) -> dict`.

- [ ] Write hand-derived tests: a constant price/neutral breadth/zero-flow history must score exactly 50 in all 12 factors and be excluded for non-positive momentum; a 1% compounding path has signed ER=1 and a perfect log-linear trend.
- [ ] Run `PYTHONPATH=scripts python3 -m unittest scripts/test_gp12_candidate_v1.py -v` and confirm the missing feature fails.
- [ ] Implement those interfaces and strict temporal/input checks. All parameter values must be validated and consumed by the relevant behavior.
- [ ] Validate future/OOS rows, missing factor data, invalid ratios, upper-limit and ST exclusions, rank ties, sector caps, holding expiry and negative price moves.
- [ ] Run all candidate tests plus the 47 existing related tests.

## Task 2: Make the result reviewable and durable

Files: create `.github/workflows/gp12-candidate-v1.yml` and `docs/gp12-candidate-review.md`.

- [ ] Execute `python3 scripts/gp12_candidate_v1.py --review --out <temporary output>` and inspect the hashes and non-admitted status.
- [ ] Obtain independent code review focused on leakage, formulas, guardrails and misleading completeness claims. Fix concrete findings and rerun affected tests.
- [ ] Publish changes on a new candidate branch from the verified remote base, create a draft PR, and inspect that exact commit's CI result.
- [ ] Report engineering results separately from adoption and real-data validation. Present one concrete adoption decision to the user if original strategy replacement is necessary.
