# MARKET STRUCTURE SOURCE BINDING V1

Status: PARTIAL_SOURCE_BOUND
Formal window: 2020-06-01 .. 2026-04-17
Scope: A-share research/evaluation governance only
Production use: PROHIBITED
Formal OOS authorization: NO

## 1. Purpose

Bind material A-share market-structure changes to authoritative contemporaneous sources before any pooled historical economic evaluation. This file is evidence/provenance. It does not by itself authorize a machine schedule, a production rule, or a causal adjustment.

The schedule is deliberately multi-axis. A taxonomy change is not silently treated as a fill-rule change; a financing or securities-lending change is not silently treated as a long-only price-limit change; a program-trading reporting rule is context unless a direct execution dependency is separately demonstrated.

## 2. Axis registry

- `BOARD_PRICE_LIMIT_REGIME`: ordinary/risk-warning board price-limit and price-cage semantics.
- `IPO_NEW_LISTING_REGIME`: first-day/first-five-day price-limit and intraday-halt semantics.
- `BOARD_TAXONOMY_REGIME`: board/security-category identity changes that may affect historical joins but not necessarily execution.
- `TRANSACTION_COST_REGIME`: statutory/exchange/clearing cost changes used in executable return simulation.
- `FINANCING_REGIME`: financing-margin requirements and contract-vintage scope.
- `SHORT_HEDGE_REGIME`: securities-lending/refinancing availability and margin rules.
- `PROGRAM_TRADING_REGULATORY_REGIME`: program-trading reporting/monitoring regime; context unless direct execution impact is established.

## 3. Source-bound baseline states at the formal-window start

### SSE main board — ordinary / ST price limits

As-of formal-window start, the historical SSE trading rule states ordinary stocks/funds at 10% and ST/*ST at 5%.

Authoritative source:
`https://www.sse.com.cn/lawandrules/sselawsrules/repeal/rules/c/c_20230418_5720136.shtml`

Evidence use: `BOARD_PRICE_LIMIT_REGIME`, DIRECT_EXECUTION.

### SZSE main/SME — ordinary / ST price limits

Historical SZSE trading rule states ordinary stocks/funds at 10% and ST/*ST at 5%.

Authoritative source:
`https://www.szse.cn/disclosure/notice/general/t20060515_499577.html`

Evidence use: `BOARD_PRICE_LIMIT_REGIME`, DIRECT_EXECUTION.

### STAR Market — already active before the formal window

SSE states that STAR stocks have no price limit for the first five trading days after IPO, 20% thereafter, with the 102%/98% continuous-auction price-declaration range.

Authoritative source:
`https://star.sse.com.cn/star/media/news/c/c_20190719_4866789.shtml`

Evidence use: `BOARD_PRICE_LIMIT_REGIME` + `IPO_NEW_LISTING_REGIME`, DIRECT_EXECUTION.

### ChiNext before the 2020 reform switch

SZSE/CSRC reform materials state that, before the special provisions took effect, ordinary existing ChiNext stocks were on the old 10% regime and risk-warning stocks were 5%; the new regime changes ChiNext stocks to 20% with first five IPO trading days unrestricted.

Authoritative sources:
`https://investor.szse.cn/knowledge/t20200721_579820.html`
`https://www.csrc.gov.cn/tianjin/c105375/c1263458/content.shtml`

Evidence use: baseline for the 2020-08-24 switch.

## 4. Source-bound events inside the formal window

### 2020-08-24 — ChiNext registration-system trading regime switch

SZSE announced that registration-system IPOs have no price limit for their first five trading days and 20% thereafter; existing ChiNext stocks changed from 10% to 20% on 2020-08-24. Continuous-auction 102%/98% price-declaration bounds and 30%/60% intraday halt thresholds also apply under the new regime.

Authoritative sources:
`https://www.szse.cn/aboutus/trends/conference/t20200821_580925.html`
`https://investor.szse.cn/knowledge/t20200721_579820.html`

Axis: `BOARD_PRICE_LIMIT_REGIME`, `IPO_NEW_LISTING_REGIME`.
Causal use: DIRECT_EXECUTION.

### 2021-04-06 — SZSE Main Board / SME Board merger

SZSE states the merger became effective on 2021-04-06 and former SME securities were recategorized as Main Board A shares while codes/names remained unchanged. The accompanying regulatory description says the trading mechanism remained unchanged.

Authoritative source:
`https://www.szse.cn/disclosure/notice/general/t20210331_585343.html`

Axis: `BOARD_TAXONOMY_REGIME`.
Causal use: TAXONOMY_ONLY. Do not create an execution-cost or price-limit break solely from this event.

### 2022-04-29 — stock transfer fee reduction

ChinaClear's official chronology records its 2022-04-28 notice reducing the stock-transfer fee overall by 50%. Contemporaneous publication of the ChinaClear notice states the effective date was 2022-04-29 and the A-share rate changed from 0.02‰ bilateral to 0.01‰ bilateral.

Authoritative primary chronology:
`https://m.chinaclear.cn/zdjs/dsj/about_dsj.shtml`

Effective-date carrier reproducing the ChinaClear notice:
`https://finance.sina.com.cn/money/bond/2022-04-28/doc-imcwipii6993883.shtml`

Axis: `TRANSACTION_COST_REGIME`.
Causal use: DIRECT_EXECUTION.
Evidence caveat: effective-date text is presently bound through a contemporaneous republication of the ChinaClear notice; keep primary-URL recovery open.

### 2023-04-10 — full-registration main-board trading reform lands

SZSE's official technical material states that the full registration reform landed on 2023-04-10 and the 2023 trading rules took effect the same day. Main-board IPOs have no price limits for the first five trading days, 30%/60% intraday halt thresholds and the 2% price-cage mechanism.

Authoritative source:
`https://www.szse.cn/www/marketServices/technicalservice/doc/P020230724535729507237.pdf`

Axis: `IPO_NEW_LISTING_REGIME`, `BOARD_PRICE_LIMIT_REGIME` where applicable.
Causal use: DIRECT_EXECUTION.

### 2023-08-28 — exchange transaction handling fee cut

CSRC states that, from 2023-08-28, SSE/SZSE A- and B-share handling fees were cut from 0.00487% bilateral to 0.00341% bilateral.

Authoritative source:
`https://www.csrc.gov.cn/csrc/c100028/c7426794/content.shtml`

Axis: `TRANSACTION_COST_REGIME`.
Causal use: DIRECT_EXECUTION.

### 2023-08-28 — securities transaction stamp tax halved

MOF/STA states securities transaction stamp tax is halved from 2023-08-28. An official tax authority FAQ states the statutory pre-cut securities-transaction rate was 1‰, so the executable post-cut rate is 0.5‰ on the taxable side, subject to the tax-base/direction contract used by the simulator.

Authoritative sources:
`https://www.mof.gov.cn/jrttts/202308/t20230828_3904235.htm`
`https://tianjin.chinatax.gov.cn/11200000000/0300/030005/20220725150235434.shtml`

Axis: `TRANSACTION_COST_REGIME`.
Causal use: DIRECT_EXECUTION.

### after 2023-09-08 close — financing margin minimum 100% -> 80%

CSRC/SSE/SZSE state the minimum financing margin ratio was reduced from 100% to 80%, effective after the 2023-09-08 close. The first ordinary trading session under the new market-level minimum is therefore 2023-09-11. The 2023 change could also apply to outstanding contracts subject to broker/client arrangements.

Authoritative sources:
`https://www.csrc.gov.cn/csrc/c100028/c7428485/content.shtml`
`https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20230827_5725661.shtml`
`https://www.szse.cn/aboutus/trends/news/t20230827_602969.html`

Axis: `FINANCING_REGIME`.
Causal use: FINANCING_ONLY unless the evaluated strategy explicitly uses leverage.

### 2023-10-30 — securities-lending margin tightened

SSE/SZSE state that the minimum securities-lending margin ratio rose from 50% to 80%, with private securities investment funds at 100%; the margin-ratio clause took effect on 2023-10-30. Other clauses in the notice had different effective dates and must not be collapsed into this one boundary.

Authoritative sources:
`https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/specific/margin/c/c_20250616_10782023.shtml`
`https://investor.szse.cn/lawrules/rule/trade/t20231013_604060.html`

Axis: `SHORT_HEDGE_REGIME`.
Causal use: HEDGE_ONLY unless the evaluated strategy uses securities lending.

### 2024-01-29 and 2024-03-18 — securities-lending supply/availability restrictions

CSRC states restricted-share lending was fully suspended from 2024-01-29 and market-oriented negotiated securities-lending transfers changed from real-time availability to next-day availability from 2024-03-18.

Authoritative source:
`https://www.csrc.gov.cn/csrc/c100028/c7459730/content.shtml`

Axis: `SHORT_HEDGE_REGIME`.
Causal use: HEDGE_ONLY.

### 2024-07-11 and 2024-07-22 — refinancing suspended and lending margin tightened again

CSRC states securities refinancing was suspended from 2024-07-11. It also states the minimum securities-lending margin ratio rose from 80% to 100%, and private securities funds from 100% to 120%, effective 2024-07-22.

Authoritative source:
`https://www.csrc.gov.cn/csrc/c100028/c7493852/content.shtml`

Axis: `SHORT_HEDGE_REGIME`.
Causal use: HEDGE_ONLY.

### 2024-10-08 — CSRC program-trading management provisions take effect

CSRC states the Program Trading Management Provisions (Trial) took effect on 2024-10-08.

Authoritative source:
`https://www.csrc.gov.cn/csrc/c100028/c7480577/content.shtml`

Axis: `PROGRAM_TRADING_REGULATORY_REGIME`.
Causal use: CONTEXT_ONLY unless a direct model/execution dependency is separately demonstrated.

### 2025-07-07 — exchange program-trading implementation rules take effect

SSE states its program-trading implementation rules took effect on 2025-07-07. The SZSE implementation rule is governed on the same effective date and must be kept as a separate venue source in the machine schedule.

Authoritative SSE source:
`https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20250612_10781696.shtml`

Axis: `PROGRAM_TRADING_REGULATORY_REGIME`.
Causal use: CONTEXT_ONLY.

### 2026-01-12 — Northbound program-trading reporting

SSE and SZSE state their Shanghai-/Shenzhen-Stock-Connect program-trading reporting rules took effect on 2026-01-12.

Authoritative sources:
`https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20250711_10784631.shtml`
`https://www.szse.cn/lawrules/rule/trade/t20250711_614858.html`

Axis: `PROGRAM_TRADING_REGULATORY_REGIME`.
Causal use: CONTEXT_ONLY / CROSS_BORDER_FLOW_CONTEXT.

### 2026-01-19 — financing margin minimum 80% -> 100% for new contracts

SSE/SZSE state that the minimum financing margin ratio returned to 100% from 2026-01-19. Existing financing contracts and rollovers remain under the prior requirement, so an account-level simulation requires contract vintage; a market-level regime flag alone is insufficient to rewrite outstanding contracts.

Authoritative sources:
`https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/specific/margin/c/c_20260114_10805174.shtml`
`https://www.szse.cn/lawrules/rule/trade/t20260114_618495.html`

Axis: `FINANCING_REGIME`.
Causal use: FINANCING_ONLY.

## 5. Explicit post-cutoff exclusion

SSE/SZSE published 2026 revised trading rules on 2026-04-24, after the formal-window end 2026-04-17. Those rules are post-cutoff for the current formal window and must not be used to rewrite prior decision rows.

## 6. Binding rulings

1. `2021-04-06 SZ Main/SME merger` = taxonomy break, not an execution break by itself.
2. `2023-09 financing change` = effective after 2023-09-08 close; session-level new regime begins 2023-09-11.
3. `2026-01 financing increase` = new-contract rule; existing-contract vintage remains relevant.
4. Securities-lending/refinancing changes live on `SHORT_HEDGE_REGIME`; they do not alter long-only fill rules by default.
5. Program-trading rules live on `PROGRAM_TRADING_REGULATORY_REGIME`; they are context by default, not a causal return adjustment.
6. Structural schedule is multi-axis. A single monolithic regime label is prohibited for formal economic interpretation.
7. Missing authoritative applicability for a row fails closed; do not default to today's rule.

## 7. Remaining source-binding gaps

This artifact does **not** claim schedule completeness. Remaining work includes:

- bind a primary ChinaClear URL carrying the exact 2022-04-29 transfer-fee effective-date text, replacing the current primary-chronology + contemporaneous-republication pair;
- bind SZSE's 2025 program-trading implementation-rule source directly in the machine artifact;
- source-bind historical suspension/resumption rules only where those rules are needed by a concrete row/execution simulation;
- verify current formal-universe venue coverage before adding BSE-specific events to required scope;
- bind row-level venue/board/security-state data separately; this file does not manufacture Universe PIT observations;
- audit whether any additional execution-cost changes inside 2020-06-01..2026-04-17 materially affect the chosen simulator.

Until those gaps and row-level mappings are resolved, status remains `PARTIAL_SOURCE_BOUND` and formal economic evaluation remains blocked.
