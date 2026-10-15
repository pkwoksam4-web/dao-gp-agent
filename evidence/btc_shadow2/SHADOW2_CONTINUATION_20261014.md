# BTC Shadow2 continuation checkpoint — 2026-10-15

## Verified state

- Branch: `btc-shadow2-rest-rescue-20261009`
- Latest checkpoint commit: `6d53be4b7d7277a79ec859ee58c105032fdf7198`
- Funding REST carrier was added in commit `184979e92f8ed77be1a224084d9efe03dc2e911d`; the bounded workflow and shell exit-code fix are in `84f470f0f0d05c43e64f558a793b8eca25cb27b8`.
- Offline unit tests passed 5/5 in GitHub Actions run `38710415197`.
- The live capture itself failed closed: official endpoint `GET /fapi/v1/fundingRate` returned HTTP 451 from the GitHub runner's restricted location. No funding rows were obtained. The failed raw response is preserved in artifact `11959673998`, ZIP SHA-256 `474857793c85f90b729708f98bf60422e21d17f34b0820f17d48646b5150c58e`; its raw response SHA-256 is `79c1db471a4cdc1c8565b5dfc52e0ed2d29962738ee4d28597696fcd0920e348`.
- Audit record: [`BINANCE_FUNDING_REST_CAPTURE_AUDIT_20261015.json`](BINANCE_FUNDING_REST_CAPTURE_AUDIT_20261015.json).
- Earlier official Data Vision funding ZIP/checksum probes for 2026-10-01..04 returned HTTP 404; do not count a successful probe workflow as data coverage.
- Current state remains `UNVERIFIED` / `NOT_PROMOTED`; funding coverage is unproven. Do not enable alpha, paper trading, or mainnet.

## Next action

Do not rerun the same endpoint from the same restricted runner or bypass the provider's location restriction. Continue only through a pre-approved, policy-compliant source or authorized environment that can access the official data. Preserve the frozen interval `[2026-10-01T00:00:00Z, 2026-10-05T00:00:00Z)`, exact raw response, request metadata, UTC retrieval timestamp, and hashes. Compare exact observed event timestamps with the frozen preregistration/ledger before making any coverage claim. If there is no approved source or authorized environment, record the branch as blocked pending authorized source access; leave every promotion gate closed.

## Frozen status controls

- Bridge: `FAIL_CLOSED`
- BID_DEPTH: `UNVERIFIED`
- QH: `NOT_PROMOTED`
- Crash: `DATA_AUDIT_ONLY`
- PAPER: `NO TRADE`
- Direction Audit: `UNVERIFIED`

## Source contract

The official Binance USDⓈ-M Futures docs define `GET /fapi/v1/fundingRate`, inclusive `startTime`/`endTime`, maximum `limit=1000`, and response fields `symbol`, `fundingRate`, `fundingTime`, `markPrice`, `rateType`:
https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data
