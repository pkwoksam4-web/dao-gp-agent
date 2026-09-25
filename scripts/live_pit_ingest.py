#!/usr/bin/env python3
"""Ingest one immutable prospective Core13 PIT manifest into Neon.

Critical invariants:
- live manifests must be same-China-date, post-close and fresh;
- exactly 13 completed daily bars;
- source provenance is written before facts;
- writes are idempotent;
- features reproduce the 2026-09-22 baseline formulas exactly;
- no forecast/shadow rows are touched.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
from datetime import datetime, timezone, timedelta
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

CORE10 = ["000636.SZ","002138.SZ","002156.SZ","600392.SH","600487.SH","600522.SH","600667.SH","600703.SH","601991.SH","605358.SH"]
ADDED = ["000977.SZ","000938.SZ","000063.SZ"]
CORE13 = CORE10 + ADDED
PROTECTED = ["forecast_runs","forecast_items","live_shadow_run_attestations","shadow_strategy_runs"]
OUT = Path("artifacts/live-pit-ingest-report.json")

def utc_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)

def sh_dt(s: str) -> datetime:
    return utc_dt(s) + timedelta(hours=8)

def raw_text(v) -> str:
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))

def src_id(td: str, symbol: str, dataset: str) -> str:
    return f"SRC-LB-LIVE-{dataset.upper()}-{td.replace('-','')}-{symbol.replace('.','-')}"

def insert_source(cur, *, sid, symbol, dataset, published_at, retrieved_at, raw, manifest_sha):
    rt=raw_text(raw)
    metadata={
      "dataset":dataset,"provider":"longbridge","mode":"LIVE_PIT",
      "trade_date":sh_dt(published_at).date().isoformat() if published_at else None,
      "live_shadow_eligible":True,"retrospective_live_shadow_backfill":False,
      "manifest_sha256":manifest_sha,
    }
    cur.execute("""
      INSERT INTO sources(id,source_type,publisher,uri,published_at,retrieved_at,raw_hash,reliability,metadata_json)
      VALUES (%s,'PROVIDER_MARKET_DATA','Longbridge',%s,%s,%s,%s,0.95,%s)
      ON CONFLICT(id) DO NOTHING
    """,(sid,f"longbridge://{dataset}/{symbol}",published_at,retrieved_at,
         hashlib.sha256(rt.encode()).hexdigest(),json.dumps(metadata,ensure_ascii=False,separators=(",",":"))))
    return rt

def compute_features(cur, symbol: str, td: str):
    cur.execute("""
      SELECT trade_time,high,low,close,volume,turnover
      FROM market_bars
      WHERE provider='longbridge' AND period='day' AND symbol=%s
        AND ((trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date <= %s::date)
      ORDER BY trade_time
    """,(symbol,td))
    rows=cur.fetchall()
    if len(rows)<31:
        raise RuntimeError(f"{symbol}: insufficient bars for 30D features: {len(rows)}")
    closes=[float(r["close"]) for r in rows]
    highs=[float(r["high"]) for r in rows]
    lows=[float(r["low"]) for r in rows]
    vols=[float(r["volume"]) for r in rows]
    amts=[float(r["turnover"]) for r in rows]
    logrets=[math.log(closes[i]/closes[i-1]) for i in range(1,len(closes))]
    high30=max(highs[-30:])
    low30=min(lows[-30:])
    return {
      "close":closes[-1],
      "high_30d":high30,
      "low_30d":low30,
      "drawdown_from_30d_high":closes[-1]/high30-1.0,
      "return_5d":closes[-1]/closes[-6]-1.0,
      "return_20d":closes[-1]/closes[-21]-1.0,
      "return_30d":closes[-1]/closes[-31]-1.0,
      "volume_ratio_5_20":(sum(vols[-5:])/5)/(sum(vols[-20:])/20),
      "amount_ratio_5_20":(sum(amts[-5:])/5)/(sum(amts[-20:])/20),
      "realized_vol_20d":statistics.stdev(logrets[-20:])*math.sqrt(252),
    }

def main():
    p=os.environ.get("PIT_MANIFEST_PATH","").strip()
    if not p:
        raise RuntimeError("PIT_MANIFEST_PATH missing")
    path=Path(p)
    manifest=json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema")!="agent-brain-core13-pit-manifest/v1":
        raise RuntimeError("unsupported manifest schema")
    if manifest.get("universe_id")!="WAT-core13-observation-v1":
        raise RuntimeError("wrong universe")
    if manifest.get("live_shadow_eligible") is not True:
        raise RuntimeError("prospective manifest must be live_shadow_eligible=true")
    if manifest.get("market_closed") is not True or manifest.get("trading_day_verified") is not True:
        raise RuntimeError("market close/trading-day gate not verified")

    td=manifest["trade_date_cn"]
    retrieved=manifest["retrieved_at"]
    rsh=sh_dt(retrieved)
    if rsh.date().isoformat()!=td:
        raise RuntimeError(f"retrieved_at not same China trade date: {rsh} vs {td}")
    if (rsh.hour,rsh.minute) < (15,0):
        raise RuntimeError("manifest retrieved before China market close")
    age=(datetime.now(timezone.utc)-utc_dt(retrieved)).total_seconds()
    if age < -300 or age > 4*3600:
        raise RuntimeError(f"prospective manifest freshness gate failed: age_seconds={age}")

    rows=manifest.get("symbols",[])
    if len(rows)!=13 or sorted(x["symbol"] for x in rows)!=sorted(CORE13):
        raise RuntimeError("Core13 manifest must contain exactly the canonical 13 symbols")
    manifest_sha=hashlib.sha256(path.read_bytes()).hexdigest()

    for x in rows:
        b=x.get("bar")
        if not b or not b.get("raw"):
            raise RuntimeError(f"{x['symbol']}: bar missing")
        raw=b["raw"]
        if sh_dt(raw["timestamp"]).date().isoformat()!=td:
            raise RuntimeError(f"{x['symbol']}: bar trade-date mismatch")
        if raw.get("trade_session")!="Intraday" or raw.get("open_updated") is not True:
            raise RuntimeError(f"{x['symbol']}: incomplete/invalid daily bar")
        q=x.get("quote")
        if not q or not q.get("raw") or not q.get("normalized"):
            raise RuntimeError(f"{x['symbol']}: quote missing")

    report={"schema":"agent-brain-live-pit-ingest-report/v1","manifest_path":p,"manifest_sha256":manifest_sha,
            "trade_date_cn":td,"inserted":{"bars":0,"quotes":0,"flows":0,"features":0,"sources":0},
            "protected_before":{},"protected_after":{}}
    dsn=os.environ["NEON_DATABASE_URL"]
    now=datetime.now(timezone.utc).isoformat()
    with psycopg.connect(dsn,row_factory=dict_row,connect_timeout=15) as conn:
      with conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("SET LOCAL statement_timeout='30s'")
        for t in PROTECTED:
            cur.execute(f"SELECT count(*) AS n FROM {t}")
            report["protected_before"][t]=cur.fetchone()["n"]

        for x in rows:
          s=x["symbol"]; b=x["bar"]; br=b["raw"]
          sid=src_id(td,s,"bar")
          before=cur.rowcount
          bt=insert_source(cur,sid=sid,symbol=s,dataset="candlesticks",published_at=br["timestamp"],
                           retrieved_at=retrieved,raw=br,manifest_sha=manifest_sha)
          if cur.rowcount==1: report["inserted"]["sources"]+=1
          cur.execute("""
            SELECT close FROM market_bars
            WHERE symbol=%s AND period='day' AND provider='longbridge' AND trade_time < %s
            ORDER BY trade_time DESC LIMIT 1
          """,(s,br["timestamp"]))
          prev=cur.fetchone()
          cur.execute("""
            INSERT INTO market_bars(symbol,trade_time,period,provider,open,high,low,close,prev_close,volume,turnover,source_id,raw_json)
            VALUES (%s,%s,'day','longbridge',%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(symbol,trade_time,period,provider) DO NOTHING
          """,(s,br["timestamp"],float(br["open"]),float(br["high"]),float(br["low"]),float(br["close"]),
               prev["close"] if prev else None,float(br["volume"]),float(br["turnover"]),sid,bt))
          report["inserted"]["bars"]+=max(cur.rowcount,0)

          q=x["quote"]; qn=q["normalized"]; qraw=q["raw"]
          qsid=src_id(td,s,"quote")
          qt=insert_source(cur,sid=qsid,symbol=s,dataset="quote",published_at=qn["as_of"],
                           retrieved_at=retrieved,raw=qraw,manifest_sha=manifest_sha)
          if cur.rowcount==1: report["inserted"]["sources"]+=1
          cur.execute("""
            INSERT INTO market_quotes(symbol,as_of,provider,last,prev_close,open,high,low,volume,turnover,source_id,raw_json)
            VALUES (%s,%s,'longbridge',%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(symbol,as_of,provider) DO NOTHING
          """,(s,qn["as_of"],qn.get("last"),qn.get("prev_close"),qn.get("open"),qn.get("high"),qn.get("low"),
               qn.get("volume"),qn.get("turnover"),qsid,qt))
          report["inserted"]["quotes"]+=max(cur.rowcount,0)

          fl=x.get("capital_flow")
          if fl and fl.get("raw") and fl.get("normalized"):
            fn=fl["normalized"]; fraw=fl["raw"]
            fsid=src_id(td,s,"flow")
            ft=insert_source(cur,sid=fsid,symbol=s,dataset="capital_flow",published_at=fn["flow_time"],
                             retrieved_at=retrieved,raw=fraw,manifest_sha=manifest_sha)
            if cur.rowcount==1: report["inserted"]["sources"]+=1
            cur.execute("""
              INSERT INTO capital_flows(symbol,flow_time,provider,net_flow,large_net,medium_net,small_net,source_id,raw_json)
              VALUES (%s,%s,'longbridge',%s,%s,%s,%s,%s,%s)
              ON CONFLICT(symbol,flow_time,provider) DO NOTHING
            """,(s,fn["flow_time"],fn.get("net_flow"),fn.get("large_net"),fn.get("medium_net"),fn.get("small_net"),fsid,ft))
            report["inserted"]["flows"]+=max(cur.rowcount,0)

        cur.execute("""
          SELECT count(DISTINCT symbol) AS n FROM market_bars
          WHERE provider='longbridge' AND period='day'
            AND ((trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date=%s::date)
            AND symbol=ANY(%s)
        """,(td,CORE13))
        if cur.fetchone()["n"]!=13:
            raise RuntimeError("post-write Core13 daily bar coverage !=13/13")

        for s in CORE13:
          f=compute_features(cur,s,td)
          cur.execute("""
            INSERT INTO stock_feature_snapshots(
              snapshot_date,symbol,sector,close,high_30d,low_30d,drawdown_from_30d_high,
              return_5d,return_20d,return_30d,volume_ratio_5_20,amount_ratio_5_20,
              realized_vol_20d,flow_latest,flow_5_obs_mean,flow_positive_share,flow_persistence,
              stock_vs_sector_20d,stock_vs_benchmark_20d,created_at)
            VALUES (%s,%s,NULL,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,NULL,NULL,NULL,NULL,NULL,%s)
            ON CONFLICT(snapshot_date,symbol) DO NOTHING
          """,(td,s,f["close"],f["high_30d"],f["low_30d"],f["drawdown_from_30d_high"],
               f["return_5d"],f["return_20d"],f["return_30d"],f["volume_ratio_5_20"],
               f["amount_ratio_5_20"],f["realized_vol_20d"],now))
          report["inserted"]["features"]+=max(cur.rowcount,0)

          x=next(z for z in rows if z["symbol"]==s)
          payload={
            "trade_date":td,"mode":"LIVE_PIT_GITHUB_BRIDGE","live_shadow_eligible":True,
            "bar_received":True,"quote_received":True,
            "flow_received":bool(x.get("capital_flow")),
            "persisted_verified":{"bars":1,"quotes":1,"flows":1 if x.get("capital_flow") else 0,"features":1},
            "provenance_required":True,"partial_skipped":0,
          }
          cur.execute("""
            INSERT INTO provider_sync_runs(id,provider,symbol,status,report_json,started_at,finished_at)
            VALUES (%s,'longbridge',%s,'COMPLETED',%s,%s,%s)
            ON CONFLICT(id) DO UPDATE SET status='COMPLETED',report_json=EXCLUDED.report_json,finished_at=EXCLUDED.finished_at
          """,(f"SYNC-LB-CORE13-{td.replace('-','')}-{s}",s,json.dumps(payload,separators=(",",":")),retrieved,now))

        cur.execute("SELECT count(*) AS n FROM stock_feature_snapshots WHERE snapshot_date=%s AND symbol=ANY(%s)",(td,CORE13))
        if cur.fetchone()["n"]!=13:
            raise RuntimeError("post-write feature coverage !=13/13")

        for t in PROTECTED:
            cur.execute(f"SELECT count(*) AS n FROM {t}")
            report["protected_after"][t]=cur.fetchone()["n"]
            if report["protected_after"][t]!=report["protected_before"][t]:
                raise RuntimeError(f"PIT ingest unexpectedly changed protected table {t}")
        conn.commit()

    report["status"]="PASS"; report["finished_at"]=datetime.now(timezone.utc).isoformat()
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("LIVE_PIT_INGEST_PASS")
    print("trade_date_cn="+td)
    print("core13_bars=13")
    print("core13_features=13")
    print("protected_shadow_forecast_unchanged=true")
    print("inserted="+json.dumps(report["inserted"],sort_keys=True))

if __name__=="__main__":
    main()
