# GP12 Candidate Input Readiness Checkpoint Design

## Goal

Produce one machine-readable checkpoint for the 11 frozen GP12 candidate feature families after applying the already verified Formal calendar, PIT adjusted-close, Formal847 intraday, and candidate-only CSI All Share / 000985 benchmark evidence.

## Invariants

- Do not modify `GP12_CANDIDATE_FACTORS_V1.json` or `GP12_CANDIDATE_PARAMETERS_V1.json`.
- Preserve factor SHA256 `b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e`.
- Preserve parameter SHA256 `22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204`.
- Reuse the existing pinned integration validators for `GP12_INTRADAY_FORMAL847_BINDING_V1` and `GP12_PIT_ADJUSTED_CLOSE_BINDING_V1`; do not reinterpret their hashes or audit identities.
- Validate benchmark evidence using the existing `gp12_candidate_package_review_v1` benchmark gate.
- CSI All Share / 000985 remains `BENCHMARK_REFERENCE_ONLY`; a valid benchmark reference does not make `market_adjusted_close` ready and may not be substituted for that feature family.
- The old `MARKET_BENCHMARK_UNBOUND` wording is superseded at the candidate checkpoint by the more precise `MARKET_ADJUSTED_CLOSE_FEATURE_BINDING_UNBOUND` while the family remains unready.
- Historical GP V1.1 strategy/benchmark recovery remains false. Candidate adoption remains UNAPPROVED. Model freeze and OOS metrics remain disallowed.

## Expected state after current verified overlays

Ready feature families:
- `market_calendar`
- `stock_adjusted_close`
- `intraday_15m`
- `intraday_60m`

Ready factors:
- `F6`, `F7`, `F8`, `F9`, `F10`, `F12`

Still-unready feature families:
- `market_adjusted_close`
- `sector_adjusted_close`
- `amount_turnover`
- `main_net_flow`
- `market_breadth`
- `sector_breadth`
- `status`

The checkpoint must preserve all truthful upstream blockers, including supporting-evidence blockers, while removing only blockers that the pinned PIT/intraday integrations actually closed.

## Output

Artifact: `GP12_CANDIDATE_INPUT_READINESS_V1`

Required safety fields:
- `candidate_benchmark_reference_validated=true` only with exact current 000985 validation evidence.
- `benchmark_feature_binding_allowed=false`.
- `market_adjusted_close_substitution_allowed=false`.
- `historical_benchmark_recovered=false`.
- `historical_strategy_recovered=false`.
- `candidate_scoring_ready=false` until all factor dependencies and status semantics are ready.
- `model_freeze_allowed=false`.
- `oos_metrics_allowed=false`.

The checkpoint should identify a deterministic `next_priority_family`; initially prefer `amount_turnover` because its raw fields already exist in the bound daily panel, but keep it blocked until a dedicated coverage/PIT binding is verified.