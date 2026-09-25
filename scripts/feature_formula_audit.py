#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import statistics
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ANCHOR = "2026-09-22"
CORE10 = ["000636.SZ","002138.SZ","002156.SZ","600392.SH","600487.SH","600522.SH","600667.SH","600703.SH","601991.SH","605358.SH"]
OUT = Path("artifacts/feature-formula-audit.json")

def rel(a,b):
    return None if a is None or b in (None,0) else a/b-1.0

def stdev(xs, ddof):
    if len(xs) <= ddof:
        return None
    m=sum(xs)/len(xs)
    return math.sqrt(sum((x-m)**2 for x in xs)/(len(xs)-ddof))

def close_returns(closes):
    return [closes[i]/closes[i-1]-1.0 for i in range(1,len(closes))]

def log_returns(closes):
    return [math.log(closes[i]/closes[i-1]) for i in range(1,len(closes))]

def main():
    dsn=os.environ["NEON_DATABASE_URL"]
    report={"anchor":ANCHOR,"symbols":{},"candidate_errors":{}}
    candidates=[
      "high30_last30","high30_last31","low30_last30","low30_last31",
      "drawdown_signed","drawdown_positive",
      "return_5d","return_20d","return_30d",
      "volume_mean5_mean20","amount_mean5_mean20",
      "vol_20ret_ddof1_ann","vol_20ret_ddof0_ann",
      "vol_last20bars_19ret_ddof1_ann","vol_last20bars_19ret_ddof0_ann",
      "vol_20ret_ddof1_noann","vol_20ret_ddof0_noann",
      "vol_log20_ddof1_ann252","vol_log20_ddof0_ann252",
      "vol_log19_ddof1_ann252","vol_log19_ddof0_ann252",
      "vol_20ret_ddof1_ann250","vol_20ret_ddof0_ann250",
      "vol_20ret_ddof1_ann244","vol_20ret_ddof0_ann244",
      "vol_log20_ddof1_ann250","vol_log20_ddof0_ann250",
      "vol_log20_ddof1_ann244","vol_log20_ddof0_ann244",
      "implied_ann_simple20_ddof0","implied_ann_log20_ddof0",
    ]
    agg={c:[] for c in candidates}
    with psycopg.connect(dsn,row_factory=dict_row,connect_timeout=15) as conn:
      with conn.cursor() as cur:
        for s in CORE10:
          cur.execute("""
            SELECT symbol,trade_time,open,high,low,close,volume,turnover
            FROM market_bars
            WHERE provider='longbridge' AND period='day' AND symbol=%s
              AND ((trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date <= %s::date)
            ORDER BY trade_time
          """,(s,ANCHOR))
          rows=cur.fetchall()
          cur.execute("SELECT * FROM stock_feature_snapshots WHERE snapshot_date=%s AND symbol=%s",(ANCHOR,s))
          stored=cur.fetchone()
          if not stored:
            raise RuntimeError(f"missing stored feature {s}")
          closes=[float(r["close"]) for r in rows]
          highs=[float(r["high"]) for r in rows]
          lows=[float(r["low"]) for r in rows]
          vols=[float(r["volume"]) for r in rows]
          amts=[float(r["turnover"]) for r in rows]
          rets=close_returns(closes)
          lrets=log_returns(closes)
          vals={
            "high30_last30":max(highs[-30:]),
            "high30_last31":max(highs[-31:]),
            "low30_last30":min(lows[-30:]),
            "low30_last31":min(lows[-31:]),
            "drawdown_signed":closes[-1]/max(highs[-30:])-1.0,
            "drawdown_positive":1.0-closes[-1]/max(highs[-30:]),
            "return_5d":closes[-1]/closes[-6]-1.0,
            "return_20d":closes[-1]/closes[-21]-1.0,
            "return_30d":closes[-1]/closes[-31]-1.0,
            "volume_mean5_mean20":(sum(vols[-5:])/5)/(sum(vols[-20:])/20),
            "amount_mean5_mean20":(sum(amts[-5:])/5)/(sum(amts[-20:])/20),
            "vol_20ret_ddof1_ann":stdev(rets[-20:],1)*math.sqrt(252),
            "vol_20ret_ddof0_ann":stdev(rets[-20:],0)*math.sqrt(252),
            "vol_last20bars_19ret_ddof1_ann":stdev(close_returns(closes[-20:]),1)*math.sqrt(252),
            "vol_last20bars_19ret_ddof0_ann":stdev(close_returns(closes[-20:]),0)*math.sqrt(252),
            "vol_20ret_ddof1_noann":stdev(rets[-20:],1),
            "vol_20ret_ddof0_noann":stdev(rets[-20:],0),
            "vol_log20_ddof1_ann252":stdev(lrets[-20:],1)*math.sqrt(252),
            "vol_log20_ddof0_ann252":stdev(lrets[-20:],0)*math.sqrt(252),
            "vol_log19_ddof1_ann252":stdev(log_returns(closes[-20:]),1)*math.sqrt(252),
            "vol_log19_ddof0_ann252":stdev(log_returns(closes[-20:]),0)*math.sqrt(252),
            "vol_20ret_ddof1_ann250":stdev(rets[-20:],1)*math.sqrt(250),
            "vol_20ret_ddof0_ann250":stdev(rets[-20:],0)*math.sqrt(250),
            "vol_20ret_ddof1_ann244":stdev(rets[-20:],1)*math.sqrt(244),
            "vol_20ret_ddof0_ann244":stdev(rets[-20:],0)*math.sqrt(244),
            "vol_log20_ddof1_ann250":stdev(lrets[-20:],1)*math.sqrt(250),
            "vol_log20_ddof0_ann250":stdev(lrets[-20:],0)*math.sqrt(250),
            "vol_log20_ddof1_ann244":stdev(lrets[-20:],1)*math.sqrt(244),
            "vol_log20_ddof0_ann244":stdev(lrets[-20:],0)*math.sqrt(244),
            "implied_ann_simple20_ddof0":(float(stored["realized_vol_20d"])/stdev(rets[-20:],0))**2,
            "implied_ann_log20_ddof0":(float(stored["realized_vol_20d"])/stdev(lrets[-20:],0))**2,
          }
          targets={
            "high30_last30":stored["high_30d"],
            "high30_last31":stored["high_30d"],
            "low30_last30":stored["low_30d"],
            "low30_last31":stored["low_30d"],
            "drawdown_signed":stored["drawdown_from_30d_high"],
            "drawdown_positive":stored["drawdown_from_30d_high"],
            "return_5d":stored["return_5d"],
            "return_20d":stored["return_20d"],
            "return_30d":stored["return_30d"],
            "volume_mean5_mean20":stored["volume_ratio_5_20"],
            "amount_mean5_mean20":stored["amount_ratio_5_20"],
            "vol_20ret_ddof1_ann":stored["realized_vol_20d"],
            "vol_20ret_ddof0_ann":stored["realized_vol_20d"],
            "vol_last20bars_19ret_ddof1_ann":stored["realized_vol_20d"],
            "vol_last20bars_19ret_ddof0_ann":stored["realized_vol_20d"],
            "vol_20ret_ddof1_noann":stored["realized_vol_20d"],
            "vol_20ret_ddof0_noann":stored["realized_vol_20d"],
            "vol_log20_ddof1_ann252":stored["realized_vol_20d"],
            "vol_log20_ddof0_ann252":stored["realized_vol_20d"],
            "vol_log19_ddof1_ann252":stored["realized_vol_20d"],
            "vol_log19_ddof0_ann252":stored["realized_vol_20d"],
            "vol_20ret_ddof1_ann250":stored["realized_vol_20d"],
            "vol_20ret_ddof0_ann250":stored["realized_vol_20d"],
            "vol_20ret_ddof1_ann244":stored["realized_vol_20d"],
            "vol_20ret_ddof0_ann244":stored["realized_vol_20d"],
            "vol_log20_ddof1_ann250":stored["realized_vol_20d"],
            "vol_log20_ddof0_ann250":stored["realized_vol_20d"],
            "vol_log20_ddof1_ann244":stored["realized_vol_20d"],
            "vol_log20_ddof0_ann244":stored["realized_vol_20d"],
            "implied_ann_simple20_ddof0":None,
            "implied_ann_log20_ddof0":None,
          }
          errors={}
          for k,v in vals.items():
            target=targets[k]
            e=None if target is None or v is None else abs(float(target)-v)
            errors[k]=e
            if e is not None: agg[k].append(e)
          report["symbols"][s]={
            "stored":{k:stored[k] for k in [
              "close","high_30d","low_30d","drawdown_from_30d_high",
              "return_5d","return_20d","return_30d","volume_ratio_5_20",
              "amount_ratio_5_20","realized_vol_20d",
              "flow_latest","flow_5_obs_mean","flow_positive_share","flow_persistence",
              "stock_vs_sector_20d","stock_vs_benchmark_20d"
            ]},
            "computed":vals,
            "abs_error":errors,
          }
    for k,es in agg.items():
      report["candidate_errors"][k]={
        "max_abs_error":max(es) if es else None,
        "mean_abs_error":sum(es)/len(es) if es else None,
      }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print("FEATURE_FORMULA_AUDIT_DONE")
    flow_summary = {
      s: {k: report["symbols"][s]["stored"][k] for k in [
        "flow_latest","flow_5_obs_mean","flow_positive_share","flow_persistence",
        "stock_vs_sector_20d","stock_vs_benchmark_20d"
      ]} for s in CORE10
    }
    print("stored_context_fields=" + json.dumps(flow_summary, ensure_ascii=False, default=str))
    for k,v in report["candidate_errors"].items():
      print(f"{k}: max_abs_error={v['max_abs_error']}")
if __name__=="__main__":
  main()
