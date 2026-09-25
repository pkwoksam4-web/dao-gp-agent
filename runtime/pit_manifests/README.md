# Core13 prospective PIT manifest contract

Path: `runtime/pit_manifests/YYYY-MM-DD.json` (immutable once created).

Required top-level fields:
- `schema = agent-brain-core13-pit-manifest/v1`
- `trade_date_cn`
- `retrieved_at` (real UTC retrieval time; must map to same Asia/Shanghai date and be after 15:00)
- `universe_id = WAT-core13-observation-v1`
- `market_closed = true`
- `trading_day_verified = true`
- `live_shadow_eligible = true`
- `symbols`: exactly 13 canonical symbols.

Each symbol entry requires:
- `symbol`
- `bar.raw`: exact Longbridge completed daily candle payload.
- `quote.raw` and `quote.normalized` with `as_of,last,prev_close,open,high,low,volume,turnover`.
- optional `capital_flow.raw` and `capital_flow.normalized` with `flow_time,net_flow,large_net,medium_net,small_net`.

No reconstructed/estimated/forward-filled payloads are admissible. Missing capital flow stays absent. Historical recovery uses a different manifest namespace and is never live-shadow eligible.
