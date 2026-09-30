#!/usr/bin/env python3
"""9/29 Core13 factual continuity repair. NOT prospective PIT or Shadow."""
from __future__ import annotations
import hashlib
import json
import os
from datetime import datetime,timezone,timedelta
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

MANIFEST=Path("recovery/manifests/2026-09-30-core13-20260929-nonlive.json")
OUT=Path("artifacts/core13-0929-nonlive-recovery.json")
SYMBOLS=["000636.SZ","002138.SZ","002156.SZ","600392.SH","600487.SH","600522.SH",
 "600667.SH","600703.SH","601991.SH","605358.SH","000977.SZ","000938.SZ","000063.SZ"]
PROTECTED=["forecast_runs","forecast_items","shadow_strategy_runs","live_shadow_run_attestations",
 "shadow_observation_snapshots","shadow_maturity_snapshots","settlement_integrity_snapshots","shadow_cohort_snapshots"]

def raw_json(v):
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))

def main():
    payload=MANIFEST.read_bytes()
    manifest=json.loads(payload)
    if manifest.get("schema")!="agent-brain-core13-nonlive-recovery/v1" or manifest.get("provenance_mode")!="HISTORICAL_RECOVERY_NON_LIVE":
        raise RuntimeError("wrong recovery manifest semantics")
    if any(manifest.get(key) is not False for key in (
        "live_shadow_eligible","retrospective_live_shadow_backfill","recovery_contains_quotes",
        "recovery_contains_flows","recovery_contains_features","recovery_contains_predictions","recovery_contains_shadow"
    )):
        raise RuntimeError("recovery must be strictly factual and non-live")
    td=manifest["trade_date_cn"]
    if td!="2026-09-29":
        raise RuntimeError("unexpected recovery trade date")
    rows=manifest["bars"]
    if len(rows)!=13 or sorted(x["symbol"] for x in rows)!=sorted(SYMBOLS):
        raise RuntimeError("expected 13 distinct Core13 symbols")
    for item in rows:
        raw=item["raw"]
        if item["trade_date_cn"]!=td or raw["timestamp"]!="2026-09-28T16:00:00Z":
            raise RuntimeError("source bar China-trade-date mismatch")
        if raw["trade_session"]!="Intraday" or raw["open_updated"] is not True:
            raise RuntimeError("source bar is not completed Intraday daily candle")
        for field in ("close","open","high","low","volume","turnover"):
            if raw.get(field) is None:
                raise RuntimeError(f"{item['symbol']}: missing {field}")
    retrieved=manifest["retrieved_at"]
    raw_hash=hashlib.sha256(payload).hexdigest()
    started=datetime.now(timezone.utc).isoformat()
    report={"status":"UNVERIFIED","mode":"HISTORICAL_RECOVERY_NON_LIVE","trade_date_cn":td,
        "manifest_sha256":raw_hash,"manifest_retrieved_at":retrieved,
        "inserted_bars":0,"already_present":0,"inserted_sources":0,
        "protected_counts_before":{},"protected_counts_after":{},
        "live_shadow_eligible":False,"generated_forecasts":False,
        "generated_shadows":False,"generated_features":False}
    with psycopg.connect(os.environ["NEON_DATABASE_URL"],row_factory=dict_row,connect_timeout=15) as conn:
      with conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout='25s'")
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",("core13-20260929-nonlive-recovery",))
        for table in PROTECTED:
            cur.execute(f"SELECT count(*) AS n FROM {table}")
            report["protected_counts_before"][table]=cur.fetchone()["n"]
        cur.execute("SELECT count(*) AS n FROM stock_feature_snapshots WHERE snapshot_date=%s",(td,))
        feature_count_before=cur.fetchone()["n"]
        cur.execute("""
            SELECT count(*) AS n FROM market_bars
            WHERE provider='longbridge' AND period='day'
            AND (trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date=DATE '2026-09-28'
            AND symbol=ANY(%s)
        """,(SYMBOLS,))
        previous_count=cur.fetchone()["n"]
        if previous_count!=13:
            raise RuntimeError(f"9/28 established baseline missing: {previous_count}/13")

        for item in sorted(rows,key=lambda x:x["symbol"]):
            symbol=item["symbol"]
            raw=item["raw"]
            raw_text=raw_json(raw)
            source_hash=hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            sid=f"SRC-LB-HISTREC-20260929-{symbol.replace('.','-')}"
            metadata={"mode":"HISTORICAL_RECOVERY_NON_LIVE","dataset":"market_bars",
                "provider":"longbridge","trade_date":"2026-09-29","live_shadow_eligible":False,
                "retrospective_live_shadow_backfill":False,"retrieved_after_trade_date":True,
                "manifest_sha256":raw_hash,
                "reason":"original prospective manifest creation blocked by execution security"}
            cur.execute("SELECT raw_hash FROM sources WHERE id=%s",(sid,))
            old_source=cur.fetchone()
            if old_source is not None and old_source["raw_hash"]!=source_hash:
                raise RuntimeError(f"existing source identity differs: {sid}")
            cur.execute("""
                INSERT INTO sources(id,source_type,publisher,uri,published_at,retrieved_at,raw_hash,reliability,metadata_json)
                VALUES (%s,'PROVIDER_MARKET_DATA','Longbridge',%s,%s,%s,%s,0.95,%s)
                ON CONFLICT(id) DO NOTHING
            """,(sid,f"longbridge://candlesticks/{symbol}?period=day",raw["timestamp"],retrieved,
                 source_hash,raw_json(metadata)))
            report["inserted_sources"]+=max(cur.rowcount,0)
            cur.execute("""
                SELECT close FROM market_bars WHERE symbol=%s AND provider='longbridge' AND period='day'
                  AND trade_time<%s ORDER BY trade_time DESC LIMIT 1
            """,(symbol,raw["timestamp"]))
            prev=cur.fetchone()
            if prev is None:
                raise RuntimeError(f"{symbol}: previous close unavailable")
            cur.execute("""
                SELECT raw_json FROM market_bars
                WHERE symbol=%s AND trade_time=%s AND period='day' AND provider='longbridge'
            """,(symbol,raw["timestamp"]))
            old_bar=cur.fetchone()
            if old_bar:
                if raw_json(json.loads(old_bar["raw_json"]))!=raw_text:
                    raise RuntimeError(f"{symbol}: historical existing bar conflict")
                report["already_present"]+=1
                continue
            cur.execute("""
                INSERT INTO market_bars(symbol,trade_time,period,provider,open,high,low,close,prev_close,volume,
                    turnover,source_id,raw_json)
                VALUES (%s,%s,'day','longbridge',%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(symbol,trade_time,period,provider) DO NOTHING
            """,(symbol,raw["timestamp"],float(raw["open"]),float(raw["high"]),float(raw["low"]),
                float(raw["close"]),float(prev["close"]),float(raw["volume"]),float(raw["turnover"]),sid,raw_text))
            if cur.rowcount!=1:
                raise RuntimeError(f"{symbol}: unexpected duplicate during recovery")
            report["inserted_bars"]+=1
            sync_id=f"SYNC-LB-HISTREC-20260929-{symbol}"
            sync_report={"mode":"HISTORICAL_RECOVERY_NON_LIVE","trade_date":"2026-09-29",
                "live_shadow_eligible":False,"bars_recovered":1,"quotes_recovered":False,
                "capital_flows_recovered":False,"features_recovered":False,
                "forecast_or_shadow_generated":False,"manifest_sha256":raw_hash}
            cur.execute("""
                INSERT INTO provider_sync_runs(id,provider,symbol,status,report_json,started_at,finished_at)
                VALUES (%s,'longbridge',%s,'COMPLETED',%s,%s,%s)
                ON CONFLICT(id) DO NOTHING
            """,(sync_id,symbol,raw_json(sync_report),started,started))

        cur.execute("""
            SELECT count(DISTINCT symbol) AS n FROM market_bars
            WHERE provider='longbridge' AND period='day'
              AND (trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date=DATE '2026-09-29'
              AND symbol=ANY(%s)
        """,(SYMBOLS,))
        n=cur.fetchone()["n"]
        if n!=13: raise RuntimeError(f"Core13 recovery coverage failed: {n}/13")
        cur.execute("SELECT count(*) AS n FROM stock_feature_snapshots WHERE snapshot_date=%s",(td,))
        if cur.fetchone()["n"]!=feature_count_before:
            raise RuntimeError("Historical recovery illegally modified feature snapshots")
        for table in PROTECTED:
            cur.execute(f"SELECT count(*) AS n FROM {table}")
            report["protected_counts_after"][table]=cur.fetchone()["n"]
            if report["protected_counts_after"][table]!=report["protected_counts_before"][table]:
                raise RuntimeError(f"protected table modified: {table}")
        cur.execute("""
            SELECT count(*) AS n FROM market_bars
            WHERE provider='longbridge' AND period='day'
            AND (trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date=DATE '2026-09-28'
            AND symbol=ANY(%s)
        """,(SYMBOLS,))
        if cur.fetchone()["n"]!=13: raise RuntimeError("9/28 row coverage changed")
        conn.commit()

    report["status"]="PASS";report["verified_core13_0929_bars"]=13
    report["finished_at"]=datetime.now(timezone.utc).isoformat()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("CORE13_NONLIVE_0929_RECOVERY_PASS")
    print(f"inserted_bars={report['inserted_bars']}")
    print(f"already_present={report['already_present']}")
    print(f"inserted_sources={report['inserted_sources']}")
    print("core13_0929_bars=13")
    print("9_28_core13_bars_unchanged=true")
    print("historical_features_not_generated=true")
    print("prospective_forecast_shadow_unchanged=true")

if __name__=="__main__":
    main()
