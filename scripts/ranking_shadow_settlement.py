#!/usr/bin/env python3
"""Settle matured Core10 ranking-only prospective Shadow runs."""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

CORE10=["000636.SZ","002138.SZ","002156.SZ","600392.SH","600487.SH","600522.SH","600667.SH","600703.SH","601991.SH","605358.SH"]
RANK_VERSION="core10-stable-reversion-lowvol-candidate-v1"
MODE=f"LIVE_SHADOW_RANKING_ONLY|{RANK_VERSION}"
OUT=Path("artifacts/ranking-settlement-report.json")

def avg_ranks(values):
    n=len(values)
    pairs=sorted(enumerate(values),key=lambda x:x[1])
    ranks=[0.0]*n
    i=0
    while i<n:
        j=i
        while j+1<n and pairs[j+1][1]==pairs[i][1]:
            j+=1
        r=(i+j)/2.0
        for k in range(i,j+1):
            ranks[pairs[k][0]]=r
        i=j+1
    return ranks

def corr(a,b):
    ma=sum(a)/len(a); mb=sum(b)/len(b)
    xa=[x-ma for x in a]; xb=[x-mb for x in b]
    da=math.sqrt(sum(x*x for x in xa)); db=math.sqrt(sum(x*x for x in xb))
    if da==0 or db==0:
        return None
    return sum(x*y for x,y in zip(xa,xb))/(da*db)

def main():
    dsn=os.environ["NEON_DATABASE_URL"]
    now=datetime.now(timezone.utc).isoformat()
    report={"schema":"agent-brain-ranking-settlement/v1","checked_at":now,
            "pending_checked":0,"settled_now":0,"still_pending":0,"settled_runs":[]}

    with psycopg.connect(dsn,row_factory=dict_row,connect_timeout=15) as conn:
      with conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("SET LOCAL statement_timeout='30s'")
        cur.execute("""
          SELECT * FROM shadow_strategy_runs
          WHERE mode=%s
          ORDER BY start_date,id
        """,(MODE,))
        runs=cur.fetchall()
        for run in runs:
          metrics=json.loads(run["metrics_json"])
          if metrics.get("settlement")!="PENDING":
              continue
          report["pending_checked"]+=1
          anchor=run["start_date"]
          daily=json.loads(run["daily_json"])
          ranking=daily.get("ranking",[])
          if len(ranking)!=10 or sorted(x["symbol"] for x in ranking)!=sorted(CORE10):
              raise RuntimeError(f"{run['id']}: invalid ranking payload")
          if any(x.get("anchor_close") in (None,0) for x in ranking):
              raise RuntimeError(f"{run['id']}: missing anchor_close; cannot settle")

          cur.execute("""
            SELECT ((trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date)::text AS trade_date,
                   count(DISTINCT symbol) AS n
            FROM market_bars
            WHERE provider='longbridge' AND period='day'
              AND symbol=ANY(%s)
              AND ((trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date > %s::date)
            GROUP BY 1
            HAVING count(DISTINCT symbol)=10
            ORDER BY 1
          """,(CORE10,anchor))
          dates=[r["trade_date"] for r in cur.fetchall()]
          if len(dates)<20:
              report["still_pending"]+=1
              continue
          target=dates[19]

          outcomes=[]
          for x in ranking:
              s=x["symbol"]
              cur.execute("""
                SELECT mb.close,mb.source_id,s.metadata_json
                FROM market_bars mb
                LEFT JOIN sources s ON s.id=mb.source_id
                WHERE mb.provider='longbridge' AND mb.period='day' AND mb.symbol=%s
                  AND ((mb.trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date=%s::date)
                ORDER BY mb.trade_time DESC LIMIT 1
              """,(s,target))
              row=cur.fetchone()
              if not row:
                  raise RuntimeError(f"{run['id']}: missing target bar {s} {target}")
              actual=float(row["close"])/float(x["anchor_close"])-1.0
              md={}
              try: md=json.loads(row["metadata_json"]) if row["metadata_json"] else {}
              except Exception: md={}
              outcomes.append({
                "symbol":s,"rank":x["rank"],"candidate_score":x["candidate_score"],
                "anchor_close":x["anchor_close"],"target_close":row["close"],
                "actual_return_20d":actual,"target_source_id":row["source_id"],
                "target_source_mode":md.get("mode"),
              })

          top=sorted(outcomes,key=lambda z:z["rank"])[:3]
          bottom=sorted(outcomes,key=lambda z:z["rank"])[-3:]
          top_mean=sum(x["actual_return_20d"] for x in top)/3
          bottom_mean=sum(x["actual_return_20d"] for x in bottom)/3
          scores=[x["candidate_score"] for x in outcomes]
          rets=[x["actual_return_20d"] for x in outcomes]
          rank_ic=corr(avg_ranks(scores),avg_ranks(rets))

          metrics.update({
            "settlement":"SETTLED",
            "settlement_trade_date":target,
            "settled_at":now,
            "top3_mean_return":top_mean,
            "bottom3_mean_return":bottom_mean,
            "top_bottom_spread":top_mean-bottom_mean,
            "spearman_rank_ic":rank_ic,
            "outcomes":outcomes,
            "settlement_rule":"20th completed China trading session strictly after anchor",
            "outcome_data_may_include_recovered_future_bars":True,
            "automatic_promotion":False,
            "production_ranking_use":False,
          })
          cur.execute("""
            UPDATE shadow_strategy_runs
            SET end_date=%s, metrics_json=%s
            WHERE id=%s
          """,(target,json.dumps(metrics,ensure_ascii=False,separators=(",",":")),run["id"]))
          report["settled_now"]+=1
          report["settled_runs"].append({
            "id":run["id"],"anchor":anchor,"target":target,
            "top3_mean_return":top_mean,"bottom3_mean_return":bottom_mean,
            "top_bottom_spread":top_mean-bottom_mean,"spearman_rank_ic":rank_ic
          })

        conn.commit()

    report["status"]="PASS"
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("RANKING_SETTLEMENT_CHECK_PASS")
    print(f"pending_checked={report['pending_checked']}")
    print(f"settled_now={report['settled_now']}")
    print(f"still_pending={report['still_pending']}")
    print("automatic_promotion=false")

if __name__=="__main__":
    main()
