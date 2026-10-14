# BTC Shadow2 continuation checkpoint — 2026-10-14

## Verified state

- Branch: `btc-shadow2-rest-rescue-20261009`
- Branch head at review: `271942708ea531561f6801e95625974c8f5be651`
- Latest branch workflows: 7 total; latest completed run is 2026-10-09. No newer run or captured evidence is present.
- REST rescue remains failed: `REST_TRANSPORT_INCOMPLETE` (`REST_MIN_ROWS_NOT_MET`, `REST_TRANSPORT_ERROR`).
- Official Data Vision funding ZIP and checksum probes for 2026-10-01..04 returned HTTP 404. A successful probe workflow means the probe ran; it does not mean funding rows were retrieved.
- Status stays `UNVERIFIED` / `NOT_PROMOTED`; funding coverage is not established. Do not enable alpha, paper trading, or mainnet.

## Next action: add a read-only funding-history REST recovery carrier

The Data Vision archive route is exhausted for the checked dates. Before repeating that probe, implement one bounded capture against Binance USDⓈ-M Futures public market-data endpoint `GET /fapi/v1/fundingRate` for symbol `BTCUSDT` and the frozen UTC interval `[2026-10-01T00:00:00Z, 2026-10-05T00:00:00Z)`.

1. Preserve the unmodified raw JSON response, exact request parameters, retrieval UTC timestamp, HTTP status, and SHA-256.
2. Validate HTTP 200, JSON array shape, symbol identity, in-range `fundingTime`, unique event timestamps, and non-empty result. Preserve `fundingRate`, `markPrice`, and `rateType`; do not round or infer missing events from an assumed 8-hour cadence.
3. Record observed timestamps and count as source evidence only. Compare them with the frozen preregistration/ledger expected event set before claiming coverage. Any missing expected timestamp or contract mismatch keeps the funding gate open.
4. Bind the captured response hash and request metadata to the existing preregistration, ledger, archive, and worker references. Do not create a replacement ledger or change the frozen Shadow contract.
5. Keep all downstream statuses fail-closed: Bridge `FAIL_CLOSED`; BID_DEPTH `UNVERIFIED`; QH `NOT_PROMOTED`; Crash `DATA_AUDIT_ONLY`; PAPER `NO TRADE`; Direction Audit `UNVERIFIED`.

## Re-entry condition

Resume the Shadow2 evidence audit only when a new REST capture, newly available official archive, or live-worker artifact is present. Verify the raw object and hash first, then run only the matching frozen contract checks. If no new object is produced, record `NO_NEW_VERIFIABLE_EVIDENCE` and retain the statuses above; do not rerun the same failed rescue or repeat the same 404 probe.

## Source contract reference

Official Binance USDⓈ-M Futures REST docs identify `GET /fapi/v1/fundingRate`, inclusive `startTime`/`endTime`, maximum `limit=1000`, and response fields including `symbol`, `fundingRate`, `fundingTime`, `markPrice`, and `rateType`:
https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data
