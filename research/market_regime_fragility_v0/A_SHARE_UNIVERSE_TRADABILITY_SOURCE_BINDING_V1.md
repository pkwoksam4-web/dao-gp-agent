# A-SHARE UNIVERSE / TRADABILITY SOURCE BINDING V1

Status: PARTIAL_SOURCE_BOUND / CROSS_MODULE_REUSE
Production use: PROHIBITED
Formal OOS: NO
Scope: research-layer source inventory for `UNIVERSE_PIT_SNAPSHOT_V1` and `A_SHARE_TRADABILITY_GATE_V1`

## 1. Governing rule

Do not rebuild historical ST / suspension state if an already-audited immutable carrier exists elsewhere in the repository. Reuse by commit/artifact identity and preserve the original semantics. Cross-module reuse does not silently widen the source's meaning.

In particular:

- `tradestatus` is a suspension/trading-status field, not proof of buy/sell-side executable liquidity;
- `isST` is ST state, not a price-limit rule by itself;
- a same-day upper-limit event is not proof that a next-session buy could fill;
- lifecycle coverage does not by itself prove every listing/delisting/board-policy field required by the new Universe snapshot contract.

## 2. Reusable audited carrier: DAO2 Module D

Immutable branch checkpoint:

- branch: `gp/dao2-d-label-status`
- commit: `2a7056ffd61885046e34dc1494bc668143d96793`
- commit message: `checkpoint(dao2-d): close label provenance and status semantics`

Primary discovery manifest at that checkpoint:

`data/dao2/modules/D_LABEL_STATUS_DISCOVERY_V1.json`

Blob SHA:

`84f3eaca94fa290d4d185af9d684124ff746ac18`

The manifest records the frozen V4.80 PIT-ST audit as:

- workflow artifact: `gp-pit-st-v480-final-audit`
- artifact id: `9972698555`
- artifact digest: `sha256:a86d807829deb393e012e93fea44637cefd1759c973fa109e2a728647fa83f58`
- lifecycle: `847/847 PASS`
- calendar: `1426/1426 PASS`
- missing required dates: `0`
- duplicate daily keys: `0`
- invalid daily rows: `0`
- outside-calendar rows: `0`
- transition cross-check: `6/6 PASS`
- formal overlay rows: `1,021,953`
- source semantics: BaoStock daily `tradestatus + isST`, fail-closed on UNKNOWN/FAILED, with lifecycle/calendar audit.

### Binding ruling

For the frozen formal universe/window already covered by this artifact, this is the preferred historical source for:

- decision-date ST state (`isST`);
- suspension/trading-status state (`tradestatus`);
- audited lifecycle/calendar domain membership needed to decide whether a status row is expected.

This reuse is evidence binding only. The research branch must still materialize or read the exact artifact by immutable identity before claiming row-level integration.

## 3. V4.82 tradestatus correction layer

Module D binds exactly four point corrections in:

`docs/v482-pitst-tradestatus-corrections.md`

Blob SHA:

`5897c86535348ffcc6ddbb06f4e7ae1725d54d5a`

Exact corrected keys:

- `002087.SZ / 2024-06-13`: `tradestatus 0 -> 1`
- `600647.SH / 2024-06-13`: `tradestatus 0 -> 1`
- `600766.SH / 2024-06-13`: `tradestatus 0 -> 1`
- `603133.SH / 2024-06-13`: `tradestatus 0 -> 1`

The correction document explicitly states:

- no rule-based broadening beyond these four keys;
- `isST` is unchanged;
- evidence is positive-volume trading in the V4.82 Sohu raw tape plus an independent historical-price carrier.

### Binding ruling

Any research consumer choosing V4.82 corrected `tradestatus` semantics must apply exactly this four-key correction set and nothing broader. It must record the correction-layer identity in provenance.

## 4. Independent ST transition evidence

`data/PIT_ST_TRANSITION_EVIDENCE_V480.json`

Blob SHA:

`b1fc4354420111b8f88b82086ef984a8d5fcc02c`

Method recorded by Module D:

`Independent company disclosures on CNINFO; exact effective date and direction must match BaoStock observed transition.`

It contains six audited ST transition checks across `000007.SZ`, `000692.SZ`, and `002141.SZ`.

### Binding ruling

This file supports semantic validation of the BaoStock `isST` transition carrier. It is not a complete replacement source for all symbol-date ST rows.

## 5. Existing candidate status contract

`data/GP12_LABEL_STATUS_BINDING_V1.json`

Blob SHA:

`8d425d30dd699be13adb0ff222b52281b73f8456`

The existing contract binds:

- `is_st`: V4.80 PIT-ST + invariant under V4.82 tradestatus corrections;
- `tradable`: V4.80 PIT-ST with exactly four V4.82 point corrections, where `tradable` means suspension/trading-status only;
- `upper_limit`: same-date raw-unadjusted close equals Tushare `stk_limit.up_limit`, with missing data fail-closed;
- next-session execution: must independently re-check that session's tradability/limit constraints; signal-date status never guarantees a fill.

### Binding ruling

The new `A_SHARE_TRADABILITY_GATE_V1` may reuse the ST/suspension semantics, but it must **not** inherit the old simplified `status_entry_eligible = non-ST and tradable and not upper_limit` formula as a full execution model. The new gate is side-specific and additionally requires actual trade evidence and buy/sell-side liquidity evidence.

## 6. Price-limit source status

Module D's discovery manifest records a pinned source contract for Tushare `stk_limit(trade_date=date)` with fields:

- `ts_code`
- `trade_date`
- `up_limit`
- `down_limit`

Pinned course repository:

`Jessica-Zhangyj/dlquant@6b245fa09cb628f3bcb812f0662bfef520e65fb4`

However, that discovery manifest also states:

`raw_rows_committed_in_course_repo = false`

Therefore:

- semantic/source provenance exists;
- a complete immutable row-level `up_limit/down_limit` carrier is **not yet proven present** for this research branch;
- the new tradability gate cannot claim historical limit-state coverage from the downloader contract alone.

Status:

`PRICE_LIMIT_ROW_CARRIER = UNRESOLVED`

## 7. Side-specific executable-liquidity status

BaoStock `tradestatus=1` proves the session is trading under that source's semantics. It does not prove:

- a buy order could execute at the assumed price;
- a sell order could execute at the assumed price;
- an upper/lower locked board had opposite-side liquidity;
- queue priority or fill probability;
- sufficient capacity for the strategy size.

The V4.82 four-key correction shows that positive-volume raw tape can independently contradict a mistaken non-trading flag, but it is not a general side-liquidity reconstruction.

Status:

`SIDE_SPECIFIC_LIQUIDITY_ROW_CARRIER = UNRESOLVED`

## 8. Universe-field mapping

Current binding assessment for `UNIVERSE_PIT_SNAPSHOT_V1`:

| Required concept | Source status | Ruling |
|---|---|---|
| decision-date ST | SOURCE_BOUND_CROSS_MODULE | V4.80 PIT-ST `isST` |
| decision-date suspension/trading status | SOURCE_BOUND_CROSS_MODULE | V4.80 `tradestatus` + exact four V4.82 corrections if corrected semantics selected |
| required lifecycle/calendar domain | SOURCE_BOUND_CROSS_MODULE | audited 847/847 + 1426/1426 domain |
| listing / delisting effective state | PARTIAL / NEED_EXACT_ROW_BINDING | lifecycle audit helps define expected domain, but this document does not claim a complete listing/delisting field carrier |
| board / venue identity by date | UNRESOLVED_FOR_NEW_CONTRACT | must be bound separately, especially around taxonomy changes |
| price-limit rule id by symbol/date | PARTIAL | market-structure schedule + ST/board inputs can govern rules, but row-level board/security state remains incomplete |
| same-date up/down price-limit values | UNRESOLVED_ROW_CARRIER | downloader provenance exists; raw historical rows not yet bound |
| actual trade evidence | PARTIAL | Sohu/BaoStock raw price-volume carriers exist in the wider project; exact integration to this gate not yet bound |
| buy-side executable liquidity | UNRESOLVED | needs execution-side evidence |
| sell-side executable liquidity | UNRESOLVED | needs execution-side evidence |
| account T+1 sell-eligible quantity | ACCOUNT_STATE_NOT_MARKET_DATA | must remain separate from market-level RS tradability |

## 9. Admission boundary

The source mapping above closes **source discovery** for historical ST and basic trading-status semantics, but it does not close the new Universe/Tradability integration blocker.

The research branch may only mark the relevant field `pit_valid=true` when the exact row carrier used at evaluation time is byte-/artifact-identified and its timestamp/domain semantics match the decision cutoff.

No current change authorizes formal evaluation or production use.

## 10. Next admissible work

1. Bind the exact V4.80 PIT-ST artifact into a read-only row adapter or manifest by immutable artifact digest; do not re-download/recompute the status panel if the artifact is recoverable.
2. Mechanically overlay the exact four V4.82 `tradestatus` corrections only if corrected semantics are selected.
3. Resolve decision-date board/venue identity and listing/delisting effective-state carriers.
4. Resolve immutable daily up/down-limit rows or an equivalently exact rule-derived carrier with PIT board/ST/new-listing inputs.
5. Keep side-specific liquidity/capacity unresolved until actual execution-side evidence exists; never proxy it with `tradestatus=1` alone.
