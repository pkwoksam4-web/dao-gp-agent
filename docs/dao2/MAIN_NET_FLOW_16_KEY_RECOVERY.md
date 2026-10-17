# MAIN_NET_FLOW 16-Key Exact Recovery

The main-net-flow family is 1,011,591 / 1,011,607 resolved. Exactly 16 Formal symbol-date keys remain.

## Semantic contract
Use only the Tushare moneyflow large + extra-large active buy/sell definition:

`main_net_flow_cny = (buy_lg_amount + buy_elg_amount - sell_lg_amount - sell_elg_amount) * 10000`

Generic “main flow” fields from other vendors are not substitutes.

## Recovery order
1. Search older commits/tags/history of the same public Tushare-derived archive.
2. Search forks, mirrors and archived snapshots preserving the exact four bucket fields.
3. Use exact-zero proof only when intraday evidence rigorously proves every constituent trade is below the Tushare large-order threshold.
4. Keep a key unresolved if exact evidence is absent.

## Residual keys
| Symbol | Date | Formal amount CNY |
|---|---|---:|
| 600306.SH | 2020-06-08 | 314,500 |
| 600898.SH | 2020-11-04 | 587,900 |
| 603996.SH | 2021-02-24 | 534,300 |
| 002618.SZ | 2021-09-23 | 12,846,700 |
| 000020.SZ | 2021-09-24 | 4,760,300 |
| 000157.SZ | 2021-09-24 | 737,075,800 |
| 000592.SZ | 2021-09-24 | 315,622,900 |
| 000753.SZ | 2021-09-24 | 13,478,500 |
| 002684.SZ | 2021-11-25 | 10,405,500 |
| 600112.SH | 2022-05-06 | 2,238,500 |
| 000564.SZ | 2023-03-20 | 61,512,300 |
| 001337.SZ | 2023-03-20 | 18,323,400 |
| 002118.SZ | 2023-05-22 | 1,401,500 |
| 002157.SZ | 2023-05-22 | 51,511,600 |
| 002503.SZ | 2023-05-22 | 3,658,700 |
| 002504.SZ | 2023-05-22 | 1,610,300 |

## Closed route
The FDL2026 submission archive contains documentation/code mentioning the engineered moneyflow feature, but no stored `large_net_amount_ratio` asset and none of the 16 residual rows. Do not retry that inversion route without a materially different archive.
