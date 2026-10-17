# Module A — Infoway Custom Plan Technical Data Request

## Purpose

We need to close one missing historical A-share dataset dependency in an audited research pipeline. We are evaluating whether an Infoway Custom Plan can provide an exact, auditable replacement source.

## Required historical coverage

China A-shares, including Shanghai and Shenzhen, for these residual dates:

- 2020-06-08
- 2020-11-04
- 2021-02-24
- 2021-09-23
- 2021-09-24
- 2021-11-25
- 2022-05-06
- 2023-03-20
- 2023-05-22

Overall required date range: **2020-06-08 through 2023-05-22**.

The 16 exact symbol-date keys are:

1. 600306.SH — 2020-06-08
2. 600898.SH — 2020-11-04
3. 603996.SH — 2021-02-24
4. 002618.SZ — 2021-09-23
5. 000020.SZ — 2021-09-24
6. 000157.SZ — 2021-09-24
7. 000592.SZ — 2021-09-24
8. 000753.SZ — 2021-09-24
9. 002684.SZ — 2021-11-25
10. 600112.SH — 2022-05-06
11. 000564.SZ — 2023-03-20
12. 001337.SZ — 2023-03-20
13. 002118.SZ — 2023-05-22
14. 002157.SZ — 2023-05-22
15. 002503.SZ — 2023-05-22
16. 002504.SZ — 2023-05-22

## Exact semantic requirement

Reference definition: Tushare `moneyflow`.

Required output fields are exact equivalents of:

- `buy_lg_amount`
- `buy_elg_amount`
- `sell_lg_amount`
- `sell_elg_amount`

Reference classification:

- Small: transaction/order amount < 50,000 CNY
- Medium: 50,000–200,000 CNY
- Large: 200,000–1,000,000 CNY
- Extra-large: >= 1,000,000 CNY
- Statistics are based on **active buy/sell L2 orders**.

Target derived value:

`main_net_flow_cny = (buy_lg_amount + buy_elg_amount - sell_lg_amount - sell_elg_amount) * 10000`

## Questions for Infoway

Please answer each item explicitly.

1. Do you provide **historical A-share tick-by-tick trade data** for 2020–2023 under a Custom Plan?
2. Do you provide **historical order-level / Level-2 order data** for 2020–2023, not just current top-5 depth snapshots?
3. If historical ticks are available, does each record include:
   - trade price
   - trade volume/value
   - active Buy/Sell direction
   - original order ID or another stable field that lets us group split executions back to the original active order?
4. Can Infoway provide direct historical fields equivalent to:
   - buy_lg_amount
   - buy_elg_amount
   - sell_lg_amount
   - sell_elg_amount
5. If direct fields are available, what exact classification thresholds and order/trade aggregation rules are used?
6. If only raw historical trades/orders are available, is there sufficient information to reconstruct:
   - Large active-buy amount: 200k–1m CNY
   - Large active-sell amount: 200k–1m CNY
   - Extra-large active-buy amount: >=1m CNY
   - Extra-large active-sell amount: >=1m CNY
   using the **original active order amount**, not merely individual execution fragments?
7. What is the earliest available date for:
   - A-share historical tick trades
   - A-share historical L2 orders
   - any direct A-share money-flow dataset
8. Can the 16 symbol-date keys listed above be delivered through API or downloadable raw files?
9. Can you provide reproducible provenance for the delivered data, such as:
   - API endpoint/version
   - request parameters
   - raw response/file identity
   - timestamp
   - checksum or immutable file ID
10. Is this capability available under an existing Custom Plan, and if so what plan/data package is required?

## Acceptance gate

We cannot accept:
- OHLCV-only data
- current/latest trade snapshots
- current top-5 order book snapshots
- generic "main fund flow" or vendor-defined net-flow fields
- inferred/filled/zero-imputed values

We will only accept the source if its semantics can be proven and overlapping historical rows exact-match our pinned reference archive field-by-field.

## Current Infoway public-plan evidence

- Free history: last 6 months
- Basic: last 1 year
- Premium: last 2 years
- Professional: last 3 years
- As of 2026-09-21, all 16 residual dates are earlier than the published Professional 3-year window.
- Public REST/WebSocket trade schema exposes trade price/value/direction but not original-order identity.
- Public depth schema is real-time top-5 only.
