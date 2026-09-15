# GP12 Candidate Input Readiness Checkpoint Plan

**Goal:** Build and CI-verify a single candidate readiness checkpoint for all 11 frozen input families without changing factor/parameter hashes.

- [ ] Add regression tests for exact current family/factor state and fail-closed benchmark/binding drift.
- [ ] Run the tests before implementation and retain the red result.
- [ ] Implement `gp12_candidate_input_readiness_v1.py` by composing the existing PIT adjusted-close and intraday integration validators plus the candidate benchmark validation gate.
- [ ] Keep 000985 as benchmark reference only; explicitly leave `market_adjusted_close` unready with `MARKET_ADJUSTED_CLOSE_FEATURE_BINDING_UNBOUND`.
- [ ] Assert ready families exactly `market_calendar`, `stock_adjusted_close`, `intraday_15m`, `intraday_60m` and ready factors exactly `F6`–`F10`, `F12`.
- [ ] Emit remaining blockers and choose `amount_turnover` as the next priority family without claiming it ready.
- [ ] Wire the checkpoint into the candidate workflow using the same freshly generated 000985 validation evidence.
- [ ] Verify workflow success, artifact metadata, and a branch diff proving factor/parameter contract files remain unchanged.