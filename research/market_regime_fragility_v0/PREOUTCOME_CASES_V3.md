# MARKET REGIME V0 — PRE-OUTCOME CASE LABELS V3

Status: RESEARCH_ONLY
Thresholds: NOT_FROZEN
Production use: PROHIBITED

These labels are locked before forward-return retrieval.

## Case E — 2026-03-19 — realized external/geopolitical macro shock after a healthy prior session

### Prior-state evidence available before the signal

2026-03-18 closed with broad headline strength:
- Shanghai Composite +0.32%;
- Shenzhen Component +1.05%;
- ChiNext +2.02%.

Therefore the pre-signal trajectory is not classified as a multi-session local deterioration.

Locked pre-signal trajectory:

`HEALTHY_PRIOR_STATE`

### Signal-close evidence on 2026-03-19

- Shanghai Composite -1.39%, Shenzhen Component -2.02%, ChiNext -1.11%; Shanghai briefly broke 4,000 intraday.
- A-share turnover about CNY 2.13tn, approximately CNY 66bn higher than the prior session.
- 4,955 stocks declined and only 505 advanced.
- Most SW1 industries fell; non-ferrous metals, steel and basic chemicals were among the largest losers.
- Coal, oil/petrochemical and utilities were among the few positive industries, consistent with an energy/geopolitical receiving side rather than broad risk appetite.
- The same-day public record tied the move to a verified external macro/geopolitical stack: hawkish Fed repricing, US equity weakness, stronger USD/higher yields, and escalating Middle-East/oil-supply risk.

Locked state:

`EXTERNAL_SHOCK` + `ACTIVE_DE_RISKING`

Locked severity:

`SEVERITY_HIGH`

Locked shock transmission state:

`REALIZED_SHOCK`

Reasoning:

By the 2026-03-19 close, the external shock had already produced broad local repricing with expanding turnover and extreme breadth damage. This differs from a pre-open `PENDING_TRANSMISSION` case. Under the preregistered framework, high severity does not imply that further downside must persist after the close.

## Locked evaluation

- If the market repairs quickly after 03-19, count the episode as evidence that `REALIZED_SHOCK` requires absorption/repair analysis rather than automatic extrapolation.
- If weakness persists without new material events, it supports persistent high-severity stress.
- Any new post-signal external/policy/sector event inside +1D/+3D/+5D must be flagged separately and must not be back-attributed to the original 03-19 signal.
- Original state/severity/transmission labels are immutable after outcome retrieval.
