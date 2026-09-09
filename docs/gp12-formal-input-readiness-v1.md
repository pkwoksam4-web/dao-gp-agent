# GP12 Formal Input Readiness V1

`GP12_FORMAL_INPUT_READINESS_V1` is the production-evidence gate for the unapproved `GP12_REBUILD_CANDIDATE_V1`. It is Formal-only through `2026-04-17`. It does not recover historical GP V1.1, adopt the candidate, freeze a model, or open OOS metrics.

## What the readiness states mean

These states are deliberately separate:

1. **Source exists / structural availability** — a source or API can return rows. This is not production validation.
2. **Artifact bound** — the exact audited upstream artifact/digest is pinned and re-verified.
3. **PIT verified** — historical values are proven known no later than each scoring snapshot, including any transformation metadata.
4. **Formal feature ready** — the feature family has a verified artifact, PIT proof, Formal-only coverage, and no remaining blocker.
5. **Candidate scoring ready** — every factor dependency plus status/liquidity execution gates is ready.
6. **Candidate adoption/freeze** — a separate future approval decision. This V1 gate never permits it.

In particular, a QFQ/event chain that is correct over a full history does **not** automatically prove that an adjusted-close value at historical date T was computable without later corporate-action information. The current stock-adjusted-close binding is therefore structural only and PIT-unverified.

## First fully verified production run

GitHub Actions run: `34327032021`

- `contracts`: SUCCESS
- `production-readiness`: SUCCESS
- regression suite: **116/116 tests PASS**
- production artifact: `gp12-formal-input-readiness-v1`
- artifact ID: `10094178271`
- artifact ZIP SHA256: `46b7120185d4516a891774c8cf66958e7229df8c9803f6901dda70310a4872cf`

The production job re-downloaded and re-verified the authoritative Formal-era artifacts before generating readiness:

| Evidence | Run | Artifact ID | Artifact digest / semantic identity |
|---|---:|---:|---|
| Formal final | `34192462041` | `10042687724` | ZIP `fdd2f45f4c6998ce2e130363aaf49bab16c9f964c28ba3202b552fbe07c5f5c6`; canonical JSON `e642481399a05635d07b1baa39f57d3aa84dfd1c18e315edd927ec42da553796` |
| Formal calendar | `33977325822` | `9972698555` | ZIP `a86d807829deb393e012e93fea44637cefd1759c973fa109e2a728647fa83f58`; 1426 dates; semantic SHA `5a872a47cf7a338cc48aa628b8de46053fddc3ed161a2617550199d0607efae7` |
| Full RAW | `34192233633` | `10042614517` | ZIP `cee7e91f1fda605f7c3bdf41c3f4a7796feeae83f8c3702e50900e6af3fa9550`; 847 symbols; 1,011,607 trade rows |
| Frozen liquidity | `34192233633` | `10042615093` | ZIP `a041d50ab2c9bbbe5f129d9afae87e817de0b1d8073c86cf829427f031bbc37b`; 1,207,822 panel rows; 80M CNY threshold |

The downloaded calendar was independently parsed as `trade_date`, with exactly 1426 strictly increasing dates from `2020-06-01` through `2026-04-17`, and its semantic hash was recomputed in the workflow.

## Observed production readiness

Exactly one scorer family is currently Formal-feature-ready:

```text
market_calendar
```

The following ten scorer families are missing or not yet production/PIT validated:

```text
amount_turnover
intraday_15m
intraday_60m
main_net_flow
market_adjusted_close
market_breadth
sector_adjusted_close
sector_breadth
status
stock_adjusted_close
```

Supporting evidence already bound:

- frozen 847-symbol Formal universe;
- Full RAW V4.82 panel;
- frozen liquidity contract and PIT-ST/trading-day support.

Supporting evidence still missing:

- `historical_label_provenance`;
- `sector_membership_pit`.

The RAW panel does not substitute for adjusted close, turnover ratio, main net flow, breadth, or intraday data. The liquidity contract is a supporting execution/filter gate and does not satisfy the candidate's turnover-ratio input. PIT-ST/trading-day evidence does not by itself supply the candidate's full `is_st + tradable + upper_limit` status semantics.

## Factor readiness

Current production output has:

```text
ready_factor_ids = []
blocked_factor_ids = F1..F12
candidate_scoring_ready = false
real_feature_inputs_validated = false
```

The exact blockers are:

```text
ADJUSTED_CLOSE_PIT_UNVERIFIED
INTRADAY_15M_UNBOUND
INTRADAY_60M_UNBOUND
LABEL_PROVENANCE_UNBOUND
MAIN_NET_FLOW_UNBOUND
MARKET_BENCHMARK_UNBOUND
MARKET_BREADTH_UNBOUND
SECTOR_BREADTH_UNBOUND
SECTOR_MEMBERSHIP_PIT_UNBOUND
SECTOR_SERIES_UNBOUND
STATUS_SEMANTICS_INCOMPLETE
TURNOVER_RATIO_UNBOUND
```

This means the existing data chain is useful evidence but is not yet sufficient to score the GP12 candidate on real Formal snapshots. No partial factor score is promoted into a full score.

## Candidate and OOS boundary

The report remains fixed at:

```text
candidate_adoption_status = UNAPPROVED
candidate_freeze_ready = false
model_freeze_allowed = false
oos_metrics_allowed = false
```

The workflow downloads only previously frozen Formal-era evidence. It consumes no market data after `2026-04-17`, no OOS outcomes, and no performance metrics.

Historical GP V1.1 recovery remains a separate line of work with its existing three blockers unchanged:

```text
STRATEGY_CODE_MISSING
PARAMETER_SET_MISSING
FACTOR_DEFINITION_MISSING
```

## Artifact file identities from run 34327032021

- `GP12_FORMAL_INPUT_EVIDENCE_V1.json`: SHA256 `a418a7e36b335ba4b4ec2d8d663c8b706df972031b5478ce26c07aa8ef459982`
- `GP12_FORMAL_INPUT_READINESS_V1.json`: SHA256 `0109e7808bf6e940904c8a9b7f476fbe9bd21b0e48041de10bac25e6201055ef`
- `GP12_FORMAL_UPSTREAM_BINDING_CHECK_V1.json`: SHA256 `927e7cdd56474cb3e0dd4ffb5231dc652404b2e5897acaf87e0d3c96bcc087d4`

These file hashes describe the first fully verified run. A later CI rerun may have a different artifact ZIP digest because archive metadata can differ; the semantic readiness state must remain identical unless source evidence or code changes.
