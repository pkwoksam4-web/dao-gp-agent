# 2026 SSE trading calendar source note

Status: frozen source annotation for `evidence/agent_brain/cn_exchange_calendar_2026.json`.

## Official source

- Issuer: Shanghai Stock Exchange (SSE).
- Notice: 关于上海证券交易所2026年部分节假日休市安排的通知.
- Notice number: 上证公告〔2025〕45号.
- Published: 2025-12-22.
- Official notice: https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml
- Official closure schedule cross-check: https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20251222_10802510.shtml

The notice specifies the 2026 holiday closure intervals, including Mid-Autumn closure on 2026-09-25 through 2026-09-27 and National Day closure on 2026-10-01 through 2026-10-07. It also explicitly leaves 2026-10-10 closed as a weekend, despite it being a make-up work Saturday outside the exchange holiday interval.

## Construction and invariants

The frozen JSON calendar is constructed from Monday-Friday dates, excluding the SSE closure intervals; Saturdays and Sundays are always excluded. Calendar validation tests must assert that 2026-09-25, every date from 2026-10-01 through 2026-10-07, 2026-10-10, and representative weekend dates are not sessions.

The canonical 2026 calendar file is pinned by exact-byte SHA-256 in the observer. A changed or incomplete file fails closed; the hash identifies bytes and does not by itself establish that the source or calendar contents are correct.
