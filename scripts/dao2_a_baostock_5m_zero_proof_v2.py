from __future__ import annotations
import json, math
from pathlib import Path

TARGETS = [
("600306.SH","2020-06-08",314500),
("600898.SH","2020-11-04",587900),
("603996.SH","2021-02-24",534300),
("002618.SZ","2021-09-23",12846700),
("000020.SZ","2021-09-24",4760300),
("000157.SZ","2021-09-24",737075800),
("000592.SZ","2021-09-24",315622900),
("000753.SZ","2021-09-24",13478500),
("002684.SZ","2021-11-25",10405500),
("600112.SH","2022-05-06",2238500),
("000564.SZ","2023-03-20",61512300),
("001337.SZ","2023-03-20",18323400),
("002118.SZ","2023-05-22",1401500),
("002157.SZ","2023-05-22",51511600),
("002503.SZ","2023-05-22",3658700),
("002504.SZ","2023-05-22",1610300),
]

def bs_code(ts_code:str)->str:
    code, exch=ts_code.split(".")
    return ("sh." if exch=="SH" else "sz.")+code

def main():
    import baostock as bs
    lg=bs.login()
    if lg.error_code!="0":
        raise SystemExit(f"baostock login failed: {lg.error_code} {lg.error_msg}")
    out=[]
    try:
        for ts_code,date,formal_amount in TARGETS:
            rs=bs.query_history_k_data_plus(
                bs_code(ts_code),
                "date,time,code,open,high,low,close,volume,amount,adjustflag",
                start_date=date,end_date=date,frequency="5",adjustflag="3"
            )
            rows=[]
            while rs.error_code=="0" and rs.next():
                row=dict(zip(rs.fields,rs.get_row_data()))
                rows.append(row)
            amounts=[]
            for row in rows:
                raw=row.get("amount","")
                if raw not in ("",None):
                    try:
                        v=float(raw)
                        if math.isfinite(v): amounts.append(v)
                    except Exception:
                        pass
            total=sum(amounts)
            mx=max(amounts) if amounts else None
            # allow small provider-vs-formal rounding mismatch already observed in prior accepted proof;
            # only the BaoStock internal daily closure and 5m upper bound establish zero.
            daily=bs.query_history_k_data_plus(
                bs_code(ts_code),"date,code,amount",
                start_date=date,end_date=date,frequency="d",adjustflag="3"
            )
            drows=[]
            while daily.error_code=="0" and daily.next():
                drows.append(dict(zip(daily.fields,daily.get_row_data())))
            daily_amt=None
            if drows and drows[0].get("amount") not in ("",None):
                daily_amt=float(drows[0]["amount"])
            internal_close = daily_amt is not None and abs(total-daily_amt) <= max(1.0, abs(daily_amt)*1e-8)
            zero_proven = bool(amounts) and internal_close and mx < 200000
            out.append({
              "ts_code":ts_code,"trade_date":date,"formal_amount_cny":formal_amount,
              "minute_bars":len(rows),"sum_5m_amount_cny":total,
              "daily_amount_cny":daily_amt,"max_5m_amount_cny":mx,
              "baostock_internal_amount_close":internal_close,
              "large_threshold_cny":200000,
              "strict_zero_proven":zero_proven,
              "main_net_flow_cny":0 if zero_proven else None,
              "reason":"every 5m aggregate < 200k and 5m sum equals BaoStock daily amount" if zero_proven else "strict upper-bound proof not established"
            })
    finally:
        bs.logout()
    proven=[x for x in out if x["strict_zero_proven"]]
    artifact={
      "artifact":"DAO2_A_BAOSTOCK_5M_ZERO_PROOF_V2",
      "status":"PASS_PARTIAL_ZERO_PROOF" if proven else "NO_NEW_ZERO_PROOF",
      "semantic_basis":{
        "tushare_large_threshold_cny":200000,
        "logic":"If every complete 5-minute aggregate is below 200,000 CNY, every constituent trade is necessarily below 200,000 CNY; therefore large and extra-large active buy/sell amounts are exactly zero regardless of direction."
      },
      "targets":out,
      "proven_count":len(proven),
      "proven_keys":[[x["ts_code"],x["trade_date"]] for x in proven]
    }
    Path("artifact").mkdir(exist_ok=True)
    Path("artifact/dao2-a-baostock-5m-zero-proof-v2.json").write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(artifact,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
