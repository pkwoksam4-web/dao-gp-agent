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

try:
    from pit_calendar_gate import (
        feature_window_dates,
        load_exchange_trading_calendar,
        validate_feature_window_continuity,
        validate_prev_close_continuity,
    )
except ModuleNotFoundError:
    from scripts.pit_calendar_gate import (
        feature_window_dates,
        load_exchange_trading_calendar,
        validate_feature_window_continuity,
        validate_prev_close_continuity,
    )

CORE10 = ["000636.SZ","002138.SZ","002156.SZ","600392.SH","600487.SH","600522.SH","600667.SH","600703.SH","601991.SH","605358.SH"]
ADDED = ["000977.SZ","000938.SZ","000063.SZ"]
CORE13 = CORE10 + ADDED
PROTECTED = ["forecast_runs","forecast_items","live_shadow_run_attestations","shadow_strategy_runs"]
OUT = Path("artifacts/live-pit-ingest-report.json")
EXCHANGE_CALENDAR = Path(os.environ.get(
    "CN_EXCHANGE_CALENDAR_PATH",
    "evidence/agent_brain/cn_exchange_calendar_2026.json",
))

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
    rh=hashlib.sha256(rt.encode()).hexdigest()
    metadata={
      "dataset":dataset,"provider":"longbridge","mode":"LIVE_PIT",
      "trade_date":sh_dt(published_at).date().isoformat() if published_at else None,
      "live_shadow_eligible":True,"retrospective_live_shadow_backfill":False,
      "manifest_sha256":manifest_sha,
    }
    cur.execute("SELECT raw_hash,metadata_json FROM sources WHERE id=%s",(sid,))
    existing=cur.fetchone()
    if existing:
        if existing["raw_hash"] != rh:
            raise RuntimeError(f"immutable source conflict: {sid}")
        try:
            em=json.loads(existing["metadata_json"])
        except Exception:
            em={}
        if em.get("manifest_sha256") not in (None,manifest_sha):
            raise RuntimeError(f"immutable manifest conflict for source: {sid}")
        return rt, False
    cur.execute("""
      INSERT INTO sources(id,source_type,publisher,uri,published_at,retrieved_at,raw_hash,reliability,metadata_json)
      VALUES (%s,'PROVIDER_MARKET_DATA','Longbridge',%s,%s,%s,%s,0.95,%s)
    """,(sid,f"longbridge://{dataset}/{symbol}",published_at,retrieved_at,
         rh,json.dumps(metadata,ensure_ascii=False,separators=(",",":"))))
    return rt, True

def _source_metadata(value):
    if isinstance(value, dict):
        return value
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return None
    return decoded if isinstance(decoded, dict) else None


def validate_feature_window_provenance(symbol, expected_dates, rows, target_date):
    if not expected_dates or expected_dates[-1]!=target_date:
        raise RuntimeError(f"{symbol}: LOOKBACK_TARGET_MISMATCH")
    observed_dates=[r.get("trade_date") for r in rows]
    validate_feature_window_continuity(symbol,expected_dates,observed_dates)
    attested=[]
    for expected_date,row in zip(expected_dates,rows):
        source_id=row.get("source_id")
        raw_json=row.get("raw_json")
        claimed_hash=row.get("source_raw_hash")
        metadata=_source_metadata(row.get("source_metadata_json"))
        retrieved=row.get("ingested_at")
        if not source_id or raw_json is None or not metadata or not claimed_hash or retrieved is None:
            raise RuntimeError(f"{symbol} {expected_date}: BAR_PROVENANCE_MISSING")
        raw_text_value=raw_text(raw_json) if isinstance(raw_json,(dict,list)) else str(raw_json)
        actual_hash=hashlib.sha256(raw_text_value.encode("utf-8")).hexdigest()
        if actual_hash!=claimed_hash:
            raise RuntimeError(f"{symbol} {expected_date}: BAR_HASH_MISMATCH")
        try:
            if isinstance(retrieved,datetime):
                retrieved_dt=retrieved
            else:
                retrieved_dt=datetime.fromisoformat(str(retrieved).replace("Z","+00:00"))
            if retrieved_dt.tzinfo is None:
                raise ValueError("timezone missing")
        except (TypeError,ValueError) as exc:
            raise RuntimeError(f"{symbol} {expected_date}: BAR_INGEST_TIME_INVALID") from exc
        mode=metadata.get("mode")
        if not isinstance(mode,str) or not mode:
            raise RuntimeError(f"{symbol} {expected_date}: BAR_SOURCE_MODE_MISSING")
        record={
            "trade_date":expected_date,"source_id":source_id,
            "bar_sha256":actual_hash,"ingested_at":retrieved_dt.astimezone(timezone.utc).isoformat(),
            "source_mode":mode,
        }
        manifest_hash=metadata.get("manifest_sha256")
        if manifest_hash is not None:
            if not isinstance(manifest_hash,str) or len(manifest_hash)!=64 or any(c not in "0123456789abcdef" for c in manifest_hash):
                raise RuntimeError(f"{symbol} {expected_date}: SOURCE_MANIFEST_HASH_INVALID")
            record["manifest_sha256"]=manifest_hash
        if expected_date==target_date:
            if mode!="LIVE_PIT" or metadata.get("live_shadow_eligible") is not True:
                raise RuntimeError(f"{symbol} {expected_date}: CURRENT_BAR_NOT_LIVE_PIT")
        else:
            lookback_tag=metadata.get("lookback_tag")
            if lookback_tag is None and mode=="HISTORICAL_LOOKBACK":
                lookback_tag=mode
            if lookback_tag!="HISTORICAL_LOOKBACK":
                raise RuntimeError(f"{symbol} {expected_date}: HISTORICAL_LOOKBACK_TAG_MISSING")
            record["lookback_tag"]=lookback_tag
        attested.append(record)
    return {"symbol":symbol,"target_date":target_date,"bars":attested}


def compute_features(cur, symbol: str, td: str, exchange_dates):
    expected_dates=feature_window_dates(td,exchange_dates,required_sessions=31)
    cur.execute("""
      SELECT mb.trade_time,mb.high,mb.low,mb.close,mb.volume,mb.turnover,
             ((mb.trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date)::text AS trade_date,
             mb.source_id,mb.raw_json,s.raw_hash AS source_raw_hash,
             s.retrieved_at AS ingested_at,s.metadata_json AS source_metadata_json
      FROM market_bars mb
      LEFT JOIN sources s ON s.id=mb.source_id
      WHERE mb.provider='longbridge' AND mb.period='day' AND mb.symbol=%s
        AND ((mb.trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date >= %s::date)
        AND ((mb.trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date <= %s::date)
      ORDER BY mb.trade_time
    """,(symbol,expected_dates[0],td))
    rows=cur.fetchall()
    window_attestation=validate_feature_window_provenance(symbol,expected_dates,rows,td)
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
    }, window_attestation

def main():
    import psycopg
    from psycopg.rows import dict_row

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
    exchange_dates=load_exchange_trading_calendar(EXCHANGE_CALENDAR)
    expected_feature_dates=feature_window_dates(
        td,exchange_dates,required_sessions=31
    )
    expected_previous_trade_date=expected_feature_dates[-2]
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
        qn=q["normalized"]
        if sh_dt(qn["as_of"]).date().isoformat()!=td:
            raise RuntimeError(f"{x['symbol']}: quote date mismatch")
        if qn.get("last") is not None and abs(float(qn["last"])-float(raw["close"]))>1e-9:
            raise RuntimeError(f"{x['symbol']}: post-close quote last != daily close")
        fl=x.get("capital_flow")
        if fl and fl.get("normalized"):
            if sh_dt(fl["normalized"]["flow_time"]).date().isoformat()!=td:
                raise RuntimeError(f"{x['symbol']}: capital flow date mismatch")

    report={"schema":"agent-brain-live-pit-ingest-report/v1","manifest_path":p,"manifest_sha256":manifest_sha,
            "trade_date_cn":td,"exchange_calendar_path":str(EXCHANGE_CALENDAR),
            "exchange_calendar_sessions":len(exchange_dates),
            "feature_window_start":expected_feature_dates[0],
            "feature_window_end":expected_feature_dates[-1],
            "expected_previous_trade_date":expected_previous_trade_date,
            "inserted":{"bars":0,"quotes":0,"flows":0,"features":0,"sources":0},
            "protected_before":{},"protected_after":{},"prev_close_continuity":{},"verified_coverage":{},
            "feature_window_attestations":{}}
    dsn=os.environ["NEON_DATABASE_URL"]
    now=datetime.now(timezone.utc).isoformat()
    with psycopg.connect(dsn,row_factory=dict_row,connect_timeout=15) as conn:
      with conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("SET LOCAL statement_timeout='30s'")

        # Fail closed before any source/fact write: every required exchange
        # session in the 31-close feature window must exist for Core13, and
        # quote.prev_close must match the exact calendar predecessor.
        latest_by_symbol={}
        for x in rows:
            s=x["symbol"]
            cur.execute("""
              SELECT close,
                     ((trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date)::text AS trade_date
              FROM market_bars
              WHERE provider='longbridge' AND period='day' AND symbol=%s
                AND ((trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date >= %s::date)
                AND ((trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date < %s::date)
              ORDER BY trade_time
            """,(s,expected_feature_dates[0],td))
            history=cur.fetchall()
            observed_dates=[r["trade_date"] for r in history]+[td]
            validate_feature_window_continuity(s,expected_feature_dates,observed_dates)
            previous_rows=[r for r in history if r["trade_date"]==expected_previous_trade_date]
            latest_by_symbol[s]=previous_rows[-1] if len(previous_rows)==1 else None
        report["prev_close_continuity"]=validate_prev_close_continuity(
            rows,latest_by_symbol,
            expected_previous_trade_date=expected_previous_trade_date,
        )

        for t in PROTECTED:
            cur.execute(f"SELECT count(*) AS n FROM {t}")
            report["protected_before"][t]=cur.fetchone()["n"]

        for x in rows:
          s=x["symbol"]; b=x["bar"]; br=b["raw"]
          sid=src_id(td,s,"bar")
          before=cur.rowcount
          bt,source_new=insert_source(cur,sid=sid,symbol=s,dataset="candlesticks",published_at=br["timestamp"],
                           retrieved_at=retrieved,raw=br,manifest_sha=manifest_sha)
          if source_new: report["inserted"]["sources"]+=1
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
          if cur.rowcount==0:
              cur.execute("""SELECT raw_json,source_id FROM market_bars
                             WHERE symbol=%s AND trade_time=%s AND period='day' AND provider='longbridge'""",
                          (s,br["timestamp"]))
              ex=cur.fetchone()
              if not ex or raw_text(json.loads(ex["raw_json"]))!=bt or ex["source_id"]!=sid:
                  raise RuntimeError(f"immutable market_bar conflict: {s} {td}")
          report["inserted"]["bars"]+=max(cur.rowcount,0)

          q=x["quote"]; qn=q["normalized"]; qraw=q["raw"]
          qsid=src_id(td,s,"quote")
          qt,source_new=insert_source(cur,sid=qsid,symbol=s,dataset="quote",published_at=qn["as_of"],
                           retrieved_at=retrieved,raw=qraw,manifest_sha=manifest_sha)
          if source_new: report["inserted"]["sources"]+=1
          cur.execute("""
            INSERT INTO market_quotes(symbol,as_of,provider,last,prev_close,open,high,low,volume,turnover,source_id,raw_json)
            VALUES (%s,%s,'longbridge',%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(symbol,as_of,provider) DO NOTHING
          """,(s,qn["as_of"],qn.get("last"),qn.get("prev_close"),qn.get("open"),qn.get("high"),qn.get("low"),
               qn.get("volume"),qn.get("turnover"),qsid,qt))
          if cur.rowcount==0:
              cur.execute("""SELECT raw_json,source_id FROM market_quotes
                             WHERE symbol=%s AND as_of=%s AND provider='longbridge'""",(s,qn["as_of"]))
              ex=cur.fetchone()
              if not ex or raw_text(json.loads(ex["raw_json"]))!=qt or ex["source_id"]!=qsid:
                  raise RuntimeError(f"immutable market_quote conflict: {s} {td}")
          report["inserted"]["quotes"]+=max(cur.rowcount,0)

          fl=x.get("capital_flow")
          if fl and fl.get("raw") and fl.get("normalized"):
            fn=fl["normalized"]; fraw=fl["raw"]
            fsid=src_id(td,s,"flow")
            ft,source_new=insert_source(cur,sid=fsid,symbol=s,dataset="capital_flow",published_at=fn["flow_time"],
                             retrieved_at=retrieved,raw=fraw,manifest_sha=manifest_sha)
            if source_new: report["inserted"]["sources"]+=1
            cur.execute("""
              INSERT INTO capital_flows(symbol,flow_time,provider,net_flow,large_net,medium_net,small_net,source_id,raw_json)
              VALUES (%s,%s,'longbridge',%s,%s,%s,%s,%s,%s)
              ON CONFLICT(symbol,flow_time,provider) DO NOTHING
            """,(s,fn["flow_time"],fn.get("net_flow"),fn.get("large_net"),fn.get("medium_net"),fn.get("small_net"),fsid,ft))
            if cur.rowcount==0:
                cur.execute("""SELECT raw_json,source_id FROM capital_flows
                               WHERE symbol=%s AND flow_time=%s AND provider='longbridge'""",(s,fn["flow_time"]))
                ex=cur.fetchone()
                if not ex or raw_text(json.loads(ex["raw_json"]))!=ft or ex["source_id"]!=fsid:
                    raise RuntimeError(f"immutable capital_flow conflict: {s} {td}")
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
          f,window_attestation=compute_features(cur,s,td,exchange_dates)
          report["feature_window_attestations"][s]=window_attestation
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
        report["verified_coverage"]={"bars":13,"features":13}

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
