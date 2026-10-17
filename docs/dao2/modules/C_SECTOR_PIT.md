# Module C — SECTOR_PIT

Status: BLOCKED

## Objective
Build a reproducible, PIT-valid sector package for F3/F4/F5 without claiming reconstructed inputs are historical GP V1.1 inputs.

## Owns
- SECTOR_SERIES_UNBOUND
- SECTOR_MEMBERSHIP_PIT_UNBOUND
- SECTOR_BREADTH_UNBOUND

## Formal contract
- Formal window: 2020-06-01 through 2026-04-17.
- Frozen market calendar: 1,426 trading days.
- Missing inputs are rejected.
- Forward fill, silent proxy substitution, synthetic market-history rows, and post-date membership lookups are forbidden.

## Historical recovery boundary
Historical recovery evidence is recorded in:
- data/dao2/modules/C_SECTOR_HISTORICAL_RECOVERY_V1.json

The recovered V3.10 Silver path proves only row-level passthrough for `citic_l1` and `citic_l3`. It does **not** prove PIT membership, recover an authoritative sector index series, or recover the executable F3/F4/F5 sector formulas.

The V3.10 Library ZIP is currently listed at `/倒/v11_offline_backtest_v3_10.zip`, but the current Project cannot materialize its raw bytes. Historical recovery claims therefore remain disabled.

## Candidate reconstruction source
Pinned public source:
- repository: Jessica-Zhangyj/dlquant
- commit: 6b245fa09cb628f3bcb812f0662bfef520e65fb4
- generator blob: f00fed00a969a39a73a71152fb3031e1631c3476

The candidate generator uses Tushare `index_classify` / `index_member_all` for membership and Tushare `sw_daily` or AKShare `index_hist_sw` for industry series.

Pre-switch membership is a projection of SW2021 intervals back to SW2014 L1 through an explicit L3 bridge. It is not direct official historical SW2014 membership. The published manifest has 7 unresolved pre-switch rows, all of which remain fail-closed.

## Independent component checkpoints
- Sector series: data/dao2/modules/C_SECTOR_SERIES_CHECKPOINT_V1.json
- PIT membership: data/dao2/modules/C_SECTOR_MEMBERSHIP_PIT_CHECKPOINT_V1.json
- Sector breadth: data/dao2/modules/C_SECTOR_BREADTH_CHECKPOINT_V1.json

No component is currently PASS. Preflight run `35498836988` verified the frozen 1,426-day Formal calendar and the fail-closed verifier contract; artifact `10600914594` records that all three data blockers remain open.

## Verifier
`scripts/dao2_sector_pit_verify_v1.py` enforces:
- date-effective membership intervals;
- the 2021-12-10 -> 2021-12-13 taxonomy switch;
- unresolved-row fail-closed behavior;
- exact required sector/date coverage derived from active membership;
- same-date source provenance;
- `fill_method=NONE`;
- no duplicate sector/date rows;
- finite positive sector closes.

The verifier intentionally does **not** invent the sector-breadth ratio definition.

## Remaining blockers
1. Historical PIT membership and sector-series bytes are not recovered.
2. Candidate membership backing bytes are not committed in the pinned public source.
3. Candidate sector series backing bytes are not committed in the pinned public source and its manifest records required-date gaps.
4. The provider industry-index close level has not yet been proven equivalent to GP12's `sector_adjusted_close` input family.
5. The same-day `sector_breadth_ratio` numerator/denominator remains undefined.

## State machine
TODO -> MATERIALIZING -> VERIFYING -> PASS/BLOCKED -> FROZEN

A PASS/FROZEN state must carry a verified checkpoint. CI success alone does not establish sector data/model success.


## Verified preflight
- Workflow run: 35498836988
- Artifact: 10600914594 (`dao2-c-sector-pit-preflight-v1`)
- Artifact ZIP SHA256: `d7163a7f7b8b5a70a9af292a31c18bbba05e8db9e7bf5d96ae56dc1306e37b76`
- Contract tests: PASS
- Frozen Formal calendar replay: 1,426 / 1,426
- PR Actions `TUSHARE_TOKEN`: absent at this run

The missing token is an environment limitation, not a claim that the provider data is globally unavailable.
