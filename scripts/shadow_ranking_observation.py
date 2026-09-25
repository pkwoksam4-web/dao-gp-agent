#!/usr/bin/env python3
"""Durable prospective ranking/observation Shadow writer.

Does NOT implement or touch probability forecast tables.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

CORE10=["000636.SZ","002138.SZ","002156.SZ","600392.SH","600487.SH","600522.SH","600667.SH","600703.SH","601991.SH","605358.SH"]
ADDED=["000977.SZ","000938.SZ","000063.SZ"]
CORE13=CORE10+ADDED
OUT=Path("artifacts/shadow-ranking-observation-report.json")
RANK_VERSION="core10-stable-reversion-lowvol-candidate-v1"
WEIGHT_VERSION="RWV-STABLE4-CORE10-CAND-V1"

def utc_dt(s):
    return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)

def sh_dt(s):
    return utc_dt(s)+timedelta(hours=8)

def avg_percent_rank(values):
    # Lowest=0, highest=1. Ties receive average zero-based rank.
    n=len(values)
    pairs=sorted(enumerate(values),key=lambda x:x[1])
    out=[0.0]*n
    i=0
    while i<n:
        j=i
        while j+1<n and pairs[j+1][1]==pairs[i][1]:
            j+=1
        avg=(i+j)/2.0
        pct=0.0 if n==1 else avg/(n-1)
        for k in range(i,j+1): out[pairs[k][0]]=pct
        i=j+1
    return out

def main():
    req_path=Path(os.environ["SHADOW_REQUEST_PATH"])
    req=json.loads(req_path.read_text(encoding="utf-8"))
    if req.get("schema")!="agent-brain-shadow-request/v1":
        raise RuntimeError("unsupported request schema")
    td=req["trade_date_cn"]; requested=req["requested_at"]
    if sh_dt(requested).date().isoformat()!=td:
        raise RuntimeError("shadow request is not same China date")
    if (sh_dt(requested).hour,sh_dt(requested).minute)<(17,30):
        raise RuntimeError("shadow request created too early")
    age=(datetime.now(timezone.utc)-utc_dt(requested)).total_seconds()
    if age < -300 or age > 4*3600:
        raise RuntimeError(f"shadow request freshness failed: {age}")
    if req.get("pit_manifest_path")!=f"runtime/pit_manifests/{td}.json":
        raise RuntimeError("PIT manifest linkage mismatch")

    dsn=os.environ["NEON_DATABASE_URL"]
    now=datetime.now(timezone.utc).isoformat()
    req_hash=hashlib.sha256(req_path.read_bytes()).hexdigest()
    report={"trade_date_cn":td,"request_sha256":req_hash,"ranking_written":0,"observation_written":0,
            "forecast_counts_before":{},"forecast_counts_after":{}}

    with psycopg.connect(dsn,row_factory=dict_row,connect_timeout=15) as conn:
      with conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("SET LOCAL statement_timeout='30s'")
        for t in ["forecast_runs","forecast_items"]:
            cur.execute(f"SELECT count(*) AS n FROM {t}")
            report["forecast_counts_before"][t]=cur.fetchone()["n"]

        # Require all 13 live features and live-provenance bars for this trade date.
        cur.execute("SELECT * FROM stock_feature_snapshots WHERE snapshot_date=%s AND symbol=ANY(%s)",(td,CORE13))
        feats=cur.fetchall()
        if len(feats)!=13:
            raise RuntimeError(f"Core13 feature coverage {len(feats)}/13")

        cur.execute("""
          SELECT count(DISTINCT mb.symbol) AS n
          FROM market_bars mb JOIN sources s ON s.id=mb.source_id
          WHERE mb.provider='longbridge' AND mb.period='day'
            AND mb.symbol=ANY(%s)
            AND ((mb.trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date=%s::date)
            AND (s.metadata_json::jsonb ->> 'live_shadow_eligible')::boolean IS TRUE
            AND s.metadata_json::jsonb ->> 'mode' = 'LIVE_PIT'
        """,(CORE13,td))
        live_n=cur.fetchone()["n"]
        if live_n!=13:
            raise RuntimeError(f"live provenance gate {live_n}/13")

        by={r["symbol"]:r for r in feats}
        factors=["return_5d","return_20d","return_30d","realized_vol_20d"]
        for s in CORE10:
            for f in factors:
                if by[s][f] is None:
                    raise RuntimeError(f"{s} missing ranking factor {f}")

        ranks={}
        for f in factors:
            vals=[float(by[s][f]) for s in CORE10]
            p=avg_percent_rank(vals)
            ranks[f]={s:p[i] for i,s in enumerate(CORE10)}

        ranking=[]
        for s in CORE10:
            score=-0.25*sum(ranks[f][s] for f in factors)
            ranking.append({
              "symbol":s,"candidate_score":score,
              "return_5d":by[s]["return_5d"],"return_20d":by[s]["return_20d"],
              "return_30d":by[s]["return_30d"],"realized_vol_20d":by[s]["realized_vol_20d"],
              "percent_rank":{f:ranks[f][s] for f in factors},
              "source_snapshot":{"snapshot_date":td,"symbol":s}
            })
        ranking.sort(key=lambda x:(-x["candidate_score"],x["symbol"]))
        for i,x in enumerate(ranking,1): x["rank"]=i

        metrics={
          "candidate_version":RANK_VERSION,"weight_version":WEIGHT_VERSION,
          "settlement":"PENDING","origin":"LIVE_SHADOW","context_safety":"PIT_SAFE",
          "probability_model":False,"automatic_promotion":False,"production_ranking_use":False,
          "request_sha256":req_hash,
        }
        daily={"trade_date":td,"ranking":ranking}
        cur.execute("""
          INSERT INTO shadow_strategy_runs(id,watchlist_id,horizon_days,start_date,end_date,top_fraction,
            transaction_cost_bps,mode,metrics_json,daily_json,created_at)
          VALUES (%s,'WAT-core10-final-v1',20,%s,%s,0.30,0,
            %s,%s,%s,%s)
          ON CONFLICT(id) DO NOTHING
        """,(f"SSR-CORE10-STABLE4-{td.replace('-','')}",td,td,
             f"LIVE_SHADOW_RANKING_ONLY|{RANK_VERSION}",
             json.dumps(metrics,ensure_ascii=False,separators=(",",":")),
             json.dumps(daily,ensure_ascii=False,separators=(",",":")),now))
        report["ranking_written"]=max(cur.rowcount,0)

        panel=[]
        for s in CORE13:
            cur.execute("""
              SELECT trade_time,open,high,low,close,volume,turnover
              FROM market_bars
              WHERE provider='longbridge' AND period='day' AND symbol=%s
                AND ((trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date <= %s::date)
              ORDER BY trade_time
            """,(s,td))
            bars=cur.fetchall()
            closes=[float(x["close"]) for x in bars]
            vols=[float(x["volume"]) for x in bars]
            rets=[closes[i]/closes[i-1]-1 for i in range(1,len(closes))]
            upvol=sum(vols[-20+i] for i,r in enumerate(rets[-19:],start=1) if r>0) if len(vols)>=20 else None
            dnvol=sum(vols[-20+i] for i,r in enumerate(rets[-19:],start=1) if r<0) if len(vols)>=20 else None
            high30=float(by[s]["high_30d"]); low30=float(by[s]["low_30d"]); close=float(by[s]["close"])
            price_pct=None if high30==low30 else (close-low30)/(high30-low30)
            cur.execute("""
              SELECT net_flow,large_net,medium_net,small_net,flow_time
              FROM capital_flows
              WHERE symbol=%s AND provider='longbridge'
                AND ((flow_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date=%s::date)
              ORDER BY flow_time DESC LIMIT 1
            """,(s,td))
            flow=cur.fetchone()
            panel.append({
              "symbol":s,
              "mode":"DAILY_OBSERVATION_SHADOW" if s in ADDED else "CORE10_CONTEXT",
              "close":close,"high_30d":high30,"low_30d":low30,"price_position_30d":price_pct,
              "return_5d":by[s]["return_5d"],
              "return_10d":close/closes[-11]-1 if len(closes)>=11 else None,
              "return_20d":by[s]["return_20d"],"return_30d":by[s]["return_30d"],
              "ma5":sum(closes[-5:])/5,"ma10":sum(closes[-10:])/10,"ma20":sum(closes[-20:])/20,
              "volume_ratio_5_20":by[s]["volume_ratio_5_20"],
              "realized_vol_20d":by[s]["realized_vol_20d"],
              "rolling_low_5d":min(float(x["low"]) for x in bars[-5:]),
              "rolling_low_10d":min(float(x["low"]) for x in bars[-10:]),
              "rolling_low_20d":min(float(x["low"]) for x in bars[-20:]),
              "up_down_volume_ratio_20d":None if not dnvol else upvol/dnvol,
              "capital_flow":dict(flow) if flow else None,
              "stock_vs_sector_20d":None,"stock_vs_benchmark_20d":None,
              "accumulation_evidence":None,
              "accumulation_evidence_reason":"RULE_NOT_FROZEN",
              "origin":"LIVE_SHADOW","context_safety":"PIT_SAFE",
            })
        cur.execute("""
          INSERT INTO shadow_observation_snapshots(id,watchlist_id,snapshot_date,panel_json,created_at)
          VALUES (%s,'WAT-core13-observation-v1',%s,%s,%s)
          ON CONFLICT(id) DO NOTHING
        """,(f"SOS-CORE13-{td.replace('-','')}",td,json.dumps({
             "trade_date":td,"origin":"LIVE_SHADOW","context_safety":"PIT_SAFE",
             "forecast_probability_generated":False,
             "probability_blocker":"PROBABILITY_V1_6_EXECUTABLE_MISSING",
             "request_sha256":req_hash,"panel":panel
           },ensure_ascii=False,separators=(",",":")),now))
        report["observation_written"]=max(cur.rowcount,0)

        for t in ["forecast_runs","forecast_items"]:
            cur.execute(f"SELECT count(*) AS n FROM {t}")
            report["forecast_counts_after"][t]=cur.fetchone()["n"]
            if report["forecast_counts_after"][t]!=report["forecast_counts_before"][t]:
                raise RuntimeError(f"forecast table changed unexpectedly: {t}")
        conn.commit()

    report["status"]="PASS"; report["finished_at"]=datetime.now(timezone.utc).isoformat()
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("SHADOW_RANKING_OBSERVATION_PASS")
    print("trade_date_cn="+td)
    print("ranking_candidate_written=true")
    print("core13_observation_written=true")
    print("probability_forecast_generated=false")
    print("probability_blocker=PROBABILITY_V1_6_EXECUTABLE_MISSING")
    print("forecast_tables_unchanged=true")

if __name__=="__main__":
    main()
