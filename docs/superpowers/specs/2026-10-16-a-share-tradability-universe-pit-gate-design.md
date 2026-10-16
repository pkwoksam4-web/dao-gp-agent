# A-Share Tradability & Universe PIT Gate — Design

Date: 2026-10-16
Branch: `research/market-regime-fragility-v0`
Status: RESEARCH GOVERNANCE DESIGN
Production use: PROHIBITED

## 1. Purpose

Prevent A-share backtests and shadow evaluation from overstating signal quality because the selected security was not actually tradable or because the historical universe / price / vendor fields were reconstructed with information unavailable at the decision timestamp.

This design is upstream of relative-strength, theme-leader, timing and economic-PnL claims.

## 2. Scope

This version implements two executable research gates:

1. `A_SHARE_TRADABILITY_GATE_V1`
2. `UNIVERSE_PIT_SNAPSHOT_V1`

It also freezes documentation contracts for mutable historical data:

- price / corporate-action snapshot semantics;
- financial announcement-time semantics;
- mutable vendor-field snapshot semantics;
- market-structure regime metadata requirement.

It does **not** freeze numeric liquidity thresholds, new-listing exclusion windows, hard-risk exposure limits, price-limit percentages, fees or slippage values. Those remain explicit mandate / source-backed blockers.

## 3. Decision ordering

The research decision path is:

`HARD RISK CEILINGS -> UNIVERSE PIT ELIGIBILITY -> SIDE-SPECIFIC TRADABILITY -> MODEL VETO / ROUTER -> SOFT RS / THEME / TIMING RANKING -> POSITION TARGET -> EXECUTION`

A security that fails PIT universe eligibility or required tradability cannot enter RS / theme-leader / CHASE_OK candidate ranking for the affected side.

## 4. A_SHARE_TRADABILITY_GATE_V1

### 4.1 Input contract

Per security and decision/execution timestamp, require:

- `symbol`
- `observed_at` timezone-aware
- `decision_cutoff` timezone-aware
- `pit_valid`
- `listing_status`: `LISTED`, `DELISTING`, `DELISTED`, `UNAVAILABLE`
- `st_status`: `NORMAL`, `ST`, `STAR_ST`, `UNAVAILABLE`
- `suspension_status`: `TRADING`, `SUSPENDED`, `UNAVAILABLE`
- `board`: versioned categorical board identifier or `UNAVAILABLE`
- `price_limit_rule_id`: non-empty source-backed rule identifier or `UNAVAILABLE`
- `limit_state`: `NONE`, `UP_LOCKED_NO_BUY`, `DOWN_LOCKED_NO_SELL`, `LIMIT_TOUCH_EXECUTABLE`, `UNAVAILABLE`
- `executed_trade_evidence`: boolean indicating actual contemporaneous market trades exist
- `buy_liquidity_observed`: `YES`, `NO`, `UNAVAILABLE`
- `sell_liquidity_observed`: `YES`, `NO`, `UNAVAILABLE`
- `sell_eligible_quantity`: non-negative numeric quantity or `UNAVAILABLE`
- non-empty provenance for each mutable field group.

No inference from a closing price alone may substitute for missing side-specific executable liquidity.

### 4.2 Outputs

Return:

- `buy_eligible: bool | null`
- `sell_eligible: bool | null`
- `rs_eligible: bool`
- `reasons: list[str]`
- `production_authorized: false`

### 4.3 Conservative semantics

- suspended / delisted / unavailable critical state => no RS eligibility;
- one-word / locked limit-up with no buy liquidity => `buy_eligible = false`;
- locked limit-down with no sell liquidity => `sell_eligible = false`;
- zero sell-eligible quantity under T+1 => `sell_eligible = false` even if quote liquidity exists;
- RS eligibility requires listed, trading, actual trade evidence and normal two-sided tradability; a non-trading or one-sided locked name cannot qualify as a strong RS survivor merely because its price did not fall;
- missing critical data fails closed to `null/false`, never assumed tradable;
- the gate does not infer exchange-specific price-limit percentages; it consumes the PIT `price_limit_rule_id` and already-resolved `limit_state`.

## 5. UNIVERSE_PIT_SNAPSHOT_V1

### 5.1 Purpose

Freeze the stock universe as it was knowable on each decision date rather than applying today's symbol list retrospectively.

### 5.2 Required per-symbol fields

- `symbol`
- `asof`
- `listed_at_asof: bool`
- `delisting_status_at_asof`
- `st_status_at_asof`
- `suspension_status_at_asof`
- `board_at_asof`
- `listing_date`
- `listing_age_sessions` if derivable from the PIT calendar, else `UNAVAILABLE`
- `liquidity_policy_version`
- `new_listing_policy_version`
- `price_limit_rule_id`
- provenance / observed timestamp / PIT-valid flag.

### 5.3 Snapshot-level outputs

- deterministic `universe_snapshot_hash`
- `eligible_symbols`
- `ineligible_symbols_with_reasons`
- `unresolved_symbols`
- `policy_versions`
- `production_authorized = false`

### 5.4 Policy rule

This version validates PIT membership inputs and policy identities; it does not invent numeric new-listing or liquidity thresholds. If a policy version requires parameters not frozen in the manifest, affected symbols remain unresolved / ineligible for economic claims.

## 6. Price-series PIT contract

Mutable back-adjusted histories are not immutable evidence.

Permitted research representations:

1. raw prices plus corporate-action data available as of the decision timestamp, with snapshot/hash; or
2. vendor-adjusted series only when the exact fetched snapshot, retrieved timestamp, adjustment mode and content hash are archived.

Refreshing a vendor QFQ series later cannot silently replace the historical feature input used by an earlier decision.

Any return feature used in formal evaluation must bind to the exact source snapshot/hash that generated it.

## 7. Financial-report PIT contract

Fundamental features must bind to the date on which the information became public, not merely the accounting report period.

At minimum distinguish:

- statutory report announcement;
- earnings preview / guidance;
- preliminary earnings report;
- correction / restatement.

A later full report cannot be projected backward to an earlier decision date.

## 8. Mutable vendor-field contract

Fields such as vendor capital-flow / order-size distributions that may be revised must be stored as timestamped snapshots with source metadata and content hashes.

Formal evaluation may consume only the snapshot available by the decision cutoff. Latest-value APIs are not sufficient evidence for a past decision unless an archived snapshot proves identity.

Vendor flow remains a vendor-defined flow field, not institutional identity.

## 9. Market-structure regime metadata

Every formal evaluation row must carry `market_structure_regime_id` referencing a separately versioned schedule covering any material rule environment relevant to interpretation, including price-limit regime, transaction-cost schedule, financing/shorting rule environment and other preregistered structural breaks.

This design does not hard-code historical dates or percentages. Those must be source-backed before formal use.

E2 cross-window replication must be reported separately by comparable regime. Pooling across structurally different regimes cannot be the sole evidence for robustness.

## 10. Formal evaluation preflight integration

`formal_eval_preflight_v1.py` will require non-empty:

- `universe_snapshot_hash`
- `universe_pit_valid = true`
- `tradability_policy_version = A_SHARE_TRADABILITY_GATE_V1`
- `market_structure_regime_schedule_version`

Economic / execution evaluation must also declare that side-specific tradability filtering was applied before RS/theme/timing candidate selection.

The preflight remains evaluation-only and never authorizes production.

## 11. TDD acceptance tests

### Tradability gate

Tests must prove:

- suspended name is not RS eligible;
- locked limit-up with no buy liquidity is not buyable and not RS eligible;
- locked limit-down with no sell liquidity is not sellable and not RS eligible;
- T+1 zero sell-eligible quantity blocks sell;
- missing price-limit rule / liquidity evidence fails closed;
- normal listed/trading/two-sided-liquid security with actual trades is RS eligible.

### Universe PIT snapshot

Tests must prove:

- deterministic hash independent of input ordering;
- delisted / not-yet-listed symbol is excluded at that as-of date;
- missing policy identity fails closed;
- mutable timestamp after decision cutoff invalidates the symbol record;
- unresolved new-listing/liquidity policy parameters cannot be silently treated as eligible.

### Preflight

Tests must prove missing or false universe/tradability fields block formal evaluation while existing valid fixture behavior remains unchanged when the required fields are present.

## 12. Non-goals

This version does not:

- claim actual historical tradability for any specific security/date;
- invent ADV thresholds or participation caps;
- infer exchange rule schedules from memory;
- calculate price-limit states from unverified numeric rules;
- alter Core10/Core13 ranking weights;
- promote any regime/theme/timing module;
- open an unused E3 set.

## 13. Success criteria

The research branch can no longer call a signal economically evaluable unless the symbol was in a PIT-valid universe snapshot and passed side-specific A-share tradability gating before candidate ranking / execution assumptions.

This closes a structural source of optimistic bias without claiming predictive improvement.
