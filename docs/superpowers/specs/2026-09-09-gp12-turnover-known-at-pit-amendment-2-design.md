# GP12 Turnover Formal V1 — Amendment 2: Dual-Source Known-At PIT

Status: approved design amendment. This document supersedes Section 5 of `docs/superpowers/specs/2026-09-09-gp12-turnover-formal-v1-design.md` where that section treated the ShareAmount API `date` as potentially sufficient for PIT resolution. It also supersedes the resolver sentence in Amendment 1 that used only `record_date <= trade_date`.

## Goal

Close the future-information risk exposed by the live Sina evidence: the ShareAmount API returns a historical `date` and circulating-A-share amount, while the Sina StockStructure page separately exposes `变动日期` and `公告日期`. The API date is therefore an effective/change date, not by itself a proven known-at date.

The production turnover denominator must be built from two Sina sources:

1. ShareAmount API — numeric historical circulating-A-share state;
2. StockStructure page — change date, announcement date, reason, and displayed circulating-A-share amount.

Neither source alone may promote `amount_turnover` to `PIT_VERIFIED`.

## Source identities

ShareAmount endpoint family remains:

`https://stock.finance.sina.com.cn/stock/api/jsonp.php/var%20KKE_ShareAmount_{sina_symbol}=/StockService.getAmountBySymbol?_=20&symbol={sina_symbol}`

StockStructure source is:

`https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_StockStructure/stockid/{code}.phtml`

For each source retain exact raw response bytes, request identity, HTTP status, fetch timestamp, byte count, and SHA256.

## StockStructure normalized row

Each parsed historical column must normalize to exactly:

- `symbol`
- `change_date` — canonical ISO `YYYY-MM-DD`
- `announcement_date` — canonical ISO `YYYY-MM-DD`
- `change_reason` — non-empty text when supplied by Sina; empty string is allowed only when the source cell is empty
- `circulating_a_10k_display` — exact decimal value displayed by Sina in units of 10,000 shares
- `circulating_a_display_scale` — number of decimal places present in the displayed value
- `stock_structure_raw_sha256`

Malformed date rows, missing announcement dates, missing/nonpositive circulating-A values, duplicate normalized columns, or ambiguous table alignment are blocked.

## Cross-source binding

For every ShareAmount API row `(change_date, amount_10k)` retained for Formal use, find StockStructure rows with the same `change_date`.

A StockStructure candidate matches the API amount only when the API decimal, quantized to the exact display scale of the StockStructure value, equals the displayed decimal value. Quantization uses decimal `ROUND_HALF_UP`; binary-float tolerance is not used.

The match must be unique.

- zero matches → `SINA_STOCK_STRUCTURE_MATCH_MISSING`
- more than one matching row → `SINA_STOCK_STRUCTURE_MATCH_AMBIGUOUS`
- same date exists but displayed value does not match → `SINA_STOCK_STRUCTURE_AMOUNT_MISMATCH`

No fuzzy percentage tolerance, nearest-neighbor date, present-day fallback, or cross-vendor substitution is permitted.

## Known-at rule

For a uniquely matched state:

`known_at = max(change_date, announcement_date)`

The normalized PIT state contains:

- `symbol`
- `change_date`
- `announcement_date`
- `known_at`
- `outstanding_share_shares` — ShareAmount API `amount * 10,000`
- `share_amount_raw_sha256`
- `stock_structure_raw_sha256`

For Formal trade date `d`, a state is eligible only if both:

- `change_date <= d`
- `known_at <= d`

Among eligible states, select the state with the latest `change_date`. Never use a state whose `known_at` is in the future, never backfill from a future state, and never interpolate.

If no eligible prior/equal known state exists, the trade row is unresolved and full turnover readiness remains blocked.

## Formal boundary

Raw source responses may contain records after `2026-04-17`, but post-Formal values cannot influence normalized Formal states, cross-source matching used for Formal output, PIT resolution, coverage, blocker clearing, or readiness.

Only matched states with `change_date <= 2026-04-17` are materialized into the Formal PIT state set. A StockStructure announcement after the Formal boundary may remain in raw provenance but cannot make a Formal row usable.

## Row schema change

`GP12_TURNOVER_FORMAL_V1` turnover rows extend the original schema with:

- `share_change_date`
- `share_announcement_date`
- `share_known_at`
- `share_amount_raw_sha256`
- `stock_structure_raw_sha256`

The old `share_record_date` field is removed from new Amendment-2 materializations to avoid implying that effective date and known-at date are the same concept.

## Manifest and blockers

The share manifest must bind both source families and report independent fetch/parse/cross-match counts. Add deterministic blockers:

- `SINA_STOCK_STRUCTURE_SOURCE_UNAVAILABLE`
- `SINA_STOCK_STRUCTURE_PAYLOAD_INVALID`
- `SINA_STOCK_STRUCTURE_MATCH_MISSING`
- `SINA_STOCK_STRUCTURE_MATCH_AMBIGUOUS`
- `SINA_STOCK_STRUCTURE_AMOUNT_MISMATCH`
- `SINA_SHARE_KNOWN_AT_UNVERIFIED`
- `TURNOVER_FUTURE_KNOWN_AT_VIOLATION`

`SINA_SHARE_DATE_SEMANTICS_UNVERIFIED` is not cleared merely because ShareAmount parsing succeeds. The promotion condition is now a complete dual-source unique match with the known-at rule enforced.

## Single-symbol gate before 847-symbol production

Before enabling 847-symbol collection, the workflow must prove on `600000.SH` that:

1. ShareAmount fetch is HTTP-successful and structurally valid;
2. StockStructure fetch is HTTP-successful and structurally valid;
3. at least one Formal-era ShareAmount row uniquely cross-matches a StockStructure row;
4. the matched output includes `change_date`, `announcement_date`, and `known_at`;
5. a synthetic trade date between `change_date` and a later `announcement_date` does not resolve the new state;
6. a trade date on/after `known_at` may resolve it;
7. `pit_verified` remains false if any cross-source gate fails.

Only after this gate is green may the workflow attempt the frozen 847-symbol universe.

## Safety invariants

This amendment does not alter candidate factor formulas, F11, candidate approval, model freeze, or OOS policy.

Always retain:

- `candidate_adoption_status = UNAPPROVED` where applicable;
- `candidate_freeze_ready = false`;
- `model_freeze_allowed = false`;
- `oos_metrics_allowed = false`.

Closing turnover alone must not clear `MAIN_NET_FLOW_UNBOUND`, `ADJUSTED_CLOSE_PIT_UNVERIFIED`, or the F11 blocker.
