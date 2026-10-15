# A-SHARE EXECUTION CONTRACT V0

Status: GOVERNANCE_PREREG
Production use: PROHIBITED
Economic-PnL eligibility: BLOCKED_PENDING_COST_CAPACITY_FREEZE

## 1. Purpose

Separate signal quality from executable trading results. A signal is not a fill.

Any future historical or prospective PnL comparison must apply the same execution rules to the complex model and all baselines.

## 2. Decision timestamp

Every signal must carry an explicit decision timestamp and data cutoff.

For daily close-based research:

- signal uses information available through completed session `T`;
- no fill before `T+1` unless the signal itself was generated from a separately preregistered pre-open / intraday information set;
- same-day close cannot be used as both unseen information and an executable fill price.

## 3. T+1 settlement constraint

For A-share cash equities:

- shares purchased on date `T` are not eligible for sale on date `T`;
- execution ledger must track `sell_eligible_quantity` separately from total position;
- an exit signal that exceeds sell-eligible quantity remains partially / fully unexecuted and is carried forward.

Backtests may not assume same-day round trips in ordinary A-share cash equities.

## 4. Suspension

If a security is suspended at an intended execution timestamp:

- executable quantity = 0;
- no synthetic fill is permitted;
- position / pending instruction is carried until the next admissible execution timestamp under the same versioned policy.

## 5. Price-limit and one-word-board handling

A price at the daily limit is not automatically executable.

Required conservative semantics:

- a one-word limit-up session cannot be assumed buyable merely because the closing price exists;
- a one-word limit-down session cannot be assumed sellable merely because the closing price exists;
- if no auditable executable liquidity exists for the intended side, fill quantity = 0;
- partial-liquidity cases require actual timestamped trade / quote evidence or a separately preregistered conservative fill model.

No future close may be used to invent a fill that was unavailable intraday.

## 6. Liquidity / capacity

Production PnL requires a frozen capacity policy covering at least:

- order value relative to contemporaneous ADV / turnover;
- participation-rate cap;
- minimum tradable liquidity;
- treatment of small-cap / micro-cap names;
- market-impact model.

Current numeric values: `NOT_FROZEN`.

Until frozen, research may compare informational quality but must not claim capacity-adjusted economic tradability.

## 7. Fees and slippage

A future execution version must freeze, before evaluation:

- commissions;
- stamp duty where applicable;
- exchange / regulatory fees;
- slippage model;
- adverse gap treatment;
- market impact.

Current values: `NOT_FROZEN`.

Gross, frictionless returns must be labeled as such and cannot support production promotion.

## 8. Financing / shorting

No strategy may assume shorting or financed long exposure without a timestamped eligibility / availability source.

For margin financing / securities lending:

- instrument eligibility;
- borrow availability;
- financing rate / borrow cost;
- quantity availability

must be known at the decision timestamp.

Missing availability => unavailable action, not zero cost.

## 9. Unfilled-signal state

Execution ledger must distinguish:

- `SIGNAL_CREATED`
- `ORDER_ELIGIBLE`
- `ORDER_BLOCKED_T1`
- `ORDER_BLOCKED_SUSPENSION`
- `ORDER_BLOCKED_PRICE_LIMIT`
- `ORDER_BLOCKED_LIQUIDITY`
- `PARTIAL_FILL`
- `FULL_FILL`
- `EXPIRED_OR_CANCELLED`

A blocked signal remains analytically separate from a wrong signal.

## 10. Comparison fairness

When comparing complex architecture vs `BASELINE_0` / `BASELINE_1`:

- identical security universe;
- identical execution timestamp convention;
- identical T+1 treatment;
- identical price-limit / suspension rules;
- identical liquidity / capacity rules;
- identical transaction-cost assumptions.

Otherwise economic comparison is invalid.

## 11. Promotion blocker

No regime / router module may reach `PRODUCTION_FROZEN` while its claimed economic benefit depends on execution assumptions that are absent, asymmetric between models, or unavailable at decision time.
