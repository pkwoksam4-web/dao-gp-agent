# V4.82 PIT-ST tradestatus corrections

V4.82 applies exactly four point corrections to the frozen V4.80 PIT-ST panel. The V4.80 rows mark `tradestatus=0`, but both the Sohu RAW tape collected by the V4.82 pipeline and an independent historical-price source show positive-volume trading on the same date.

No rule-based broadening is allowed: these four `(symbol, date)` keys are the complete correction set.

| Symbol | Date | V4.80 | V4.82 | Independent evidence |
|---|---|---:|---:|---|
| 002087.SZ | 2024-06-13 | 0 | 1 | Sohu `hisHq` positive-volume row; Investing historical tape shows close 0.16 and volume 20.06M: https://cn.investing.com/equities/xinye-textile-a-historical-data |
| 600647.SH | 2024-06-13 | 0 | 1 | Sohu `hisHq` positive-volume row; Investing historical tape shows close 1.79 and volume 2.62M: https://cn.investing.com/equities/sh-tongda-historical-data |
| 600766.SH | 2024-06-13 | 0 | 1 | Sohu `hisHq` positive-volume row; Investing historical tape shows close 0.36 and volume 8.07M: https://cn.investing.com/equities/yantai-yuanche-historical-data |
| 603133.SH | 2024-06-13 | 0 | 1 | Sohu `hisHq` positive-volume row; Investing historical tape shows close 0.30 and volume 6.18M: https://cn.investing.com/equities/tanyuan-technology-co-ltd-historical-data |

## Formal impact

- Frozen V4.80 trade-row count: `1,011,602`.
- V4.82 corrected trade-row count: `1,011,606`.
- Symbol universe remains `847`.
- Zero-trade symbols remain exactly `600074.SH`, `600485.SH`, `600677.SH`.
- `isST` is not changed by this correction layer.
- Formal/OOS admission remains disabled until the corrected full RAW panel passes exact date, duplicate, OHLC, volume, amount, and shard-error gates.
