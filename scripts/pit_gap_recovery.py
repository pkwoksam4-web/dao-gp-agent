#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

MANIFEST = Path("recovery/manifests/2026-09-25-core13-pit-gap-recovery.json")
REPORT = Path("artifacts/pit-gap-recovery-report.json")
CORE10 = ["000636.SZ","002138.SZ","002156.SZ","600392.SH","600487.SH","600522.SH","600667.SH","600703.SH","601991.SH","605358.SH"]
ADDED = ["000977.SZ","000938.SZ","000063.SZ"]
PROTECTED_TABLES = ["forecast_runs","forecast_items","live_shadow_run_attestations","shadow_strategy_runs","shadow_observation_snapshots","shadow_maturity_snapshots","settlement_integrity_snapshots","shadow_cohort_snapshots"]

def cn_date(ts: str) -> str:
    dt = datetime.fromisoformat(ts.replace("Z","+00:00")) + timedelta(hours=8)
    return dt.date().isoformat()

def canonical_raw(raw: dict) -> str:
    return json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",",":"))

def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["mode"] != "HISTORICAL_RECOVERY_NON_LIVE":
        raise RuntimeError("Wrong recovery mode")
    if manifest.get("live_shadow_eligible") is not False:
        raise RuntimeError("Recovery must be live_shadow_eligible=false")
    if manifest.get("forecast_or_shadow_generated") is not False:
        raise RuntimeError("Recovery manifest must forbid forecast/shadow generation")

    bars = manifest["bars"]
    if len(bars) != 140:
        raise RuntimeError(f"Expected 140 staged bars, got {len(bars)}")

    for item in bars:
        raw = item["raw"]
        if cn_date(raw["timestamp"]) != item["trade_date_cn"]:
            raise RuntimeError(f"CN date mismatch for {item['symbol']} {raw['timestamp']}")
        if item["trade_date_cn"] > "2026-09-24":
            raise RuntimeError("Recovery includes post-gap/future date")
        if raw.get("trade_session") != "Intraday":
            raise RuntimeError("Unexpected trade_session")
        if raw.get("open_updated") is not True:
            raise RuntimeError("Incomplete candle in recovery manifest")

    dsn = os.environ["NEON_DATABASE_URL"]
    now = datetime.now(timezone.utc).isoformat()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "schema":"agent-brain-pit-gap-recovery-report/v1",
        "mode":"HISTORICAL_RECOVERY_NON_LIVE",
        "live_shadow_eligible":False,
        "manifest_retrieved_at":manifest["retrieved_at"],
        "writer_started_at":now,
        "inserted_bars":0,
        "existing_bars":0,
        "inserted_sources":0,
        "symbols":{},
        "protected_counts_before":{},
        "protected_counts_after":{},
    }

    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute("BEGIN")
            cur.execute("SET LOCAL statement_timeout = '30s'")

            for table in PROTECTED_TABLES:
                cur.execute(f"SELECT count(*) AS n FROM {table}")
                report["protected_counts_before"][table] = cur.fetchone()["n"]

            manifest_hash = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
            inserted_by_symbol = {s:0 for s in CORE10 + ADDED}
            total_by_symbol = {s:0 for s in CORE10 + ADDED}

            bars_sorted = sorted(bars, key=lambda x: (x["symbol"], x["raw"]["timestamp"]))
            for item in bars_sorted:
                symbol = item["symbol"]
                td = item["trade_date_cn"]
                raw = item["raw"]
                raw_text = canonical_raw(raw)
                raw_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
                source_id = f"SRC-LB-HISTREC-{td.replace('-','')}-{symbol.replace('.','-')}"

                metadata = {
                    "dataset":"market_bars",
                    "provider":"longbridge",
                    "mode":"HISTORICAL_RECOVERY_NON_LIVE",
                    "trade_date":td,
                    "live_shadow_eligible":False,
                    "retrospective_live_shadow_backfill":False,
                    "retrieved_after_original_trade_date":True,
                    "recovery_manifest_sha256":manifest_hash,
                    "reason":"Neon connector control-plane outage continuity repair",
                }

                cur.execute(
                    """
                    INSERT INTO sources(
                        id,source_type,publisher,uri,published_at,retrieved_at,
                        raw_hash,reliability,metadata_json
                    ) VALUES (%s,'PROVIDER_MARKET_DATA','Longbridge',%s,%s,%s,%s,0.95,%s)
                    ON CONFLICT(id) DO NOTHING
                    """,
                    (
                        source_id,
                        f"longbridge://candlesticks/{symbol}?period=day",
                        raw["timestamp"],
                        manifest["retrieved_at"],
                        raw_hash,
                        json.dumps(metadata,ensure_ascii=False,separators=(",",":")),
                    ),
                )
                if cur.rowcount == 1:
                    report["inserted_sources"] += 1

                cur.execute(
                    """
                    SELECT close FROM market_bars
                    WHERE symbol=%s AND period='day' AND provider='longbridge' AND trade_time < %s
                    ORDER BY trade_time DESC LIMIT 1
                    """,
                    (symbol, raw["timestamp"]),
                )
                prev = cur.fetchone()
                prev_close = prev["close"] if prev else None

                cur.execute(
                    """
                    INSERT INTO market_bars(
                        symbol,trade_time,period,provider,open,high,low,close,
                        prev_close,volume,turnover,source_id,raw_json
                    )
                    VALUES (%s,%s,'day','longbridge',%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(symbol,trade_time,period,provider) DO NOTHING
                    """,
                    (
                        symbol,raw["timestamp"],float(raw["open"]),float(raw["high"]),
                        float(raw["low"]),float(raw["close"]),prev_close,float(raw["volume"]),
                        float(raw["turnover"]),source_id,raw_text,
                    ),
                )
                total_by_symbol[symbol] += 1
                if cur.rowcount == 1:
                    report["inserted_bars"] += 1
                    inserted_by_symbol[symbol] += 1
                else:
                    report["existing_bars"] += 1

            for symbol in CORE10 + ADDED:
                rows = [x for x in bars if x["symbol"] == symbol]
                dates = sorted(x["trade_date_cn"] for x in rows)
                sync_id = f"SYNC-LB-HISTREC-20260925-{symbol}"
                payload = {
                    "mode":"HISTORICAL_RECOVERY_NON_LIVE",
                    "source":"Longbridge",
                    "requested_bars":len(rows),
                    "inserted_bars":inserted_by_symbol[symbol],
                    "existing_bars":len(rows)-inserted_by_symbol[symbol],
                    "first_trade_date":dates[0],
                    "last_trade_date":dates[-1],
                    "live_shadow_eligible":False,
                    "capital_flows_recovered":False,
                    "quotes_recovered":False,
                    "feature_snapshots_generated":False,
                    "forecast_or_shadow_generated":False,
                    "prospective_effective_trade_date":"2026-09-28" if symbol in ADDED else None,
                }
                cur.execute(
                    """
                    INSERT INTO provider_sync_runs(id,provider,symbol,status,report_json,started_at,finished_at)
                    VALUES (%s,'longbridge',%s,'COMPLETED',%s,%s,%s)
                    ON CONFLICT(id) DO UPDATE
                    SET status='COMPLETED', report_json=EXCLUDED.report_json, finished_at=EXCLUDED.finished_at
                    """,
                    (sync_id,symbol,json.dumps(payload,ensure_ascii=False,separators=(",",":")),now,now),
                )
                report["symbols"][symbol] = payload

            for td in ["2026-09-23","2026-09-24"]:
                cur.execute(
                    """
                    SELECT count(DISTINCT symbol) AS n
                    FROM market_bars
                    WHERE provider='longbridge'
                      AND ((trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date = %s::date)
                      AND symbol = ANY(%s)
                    """,
                    (td,CORE10),
                )
                n = cur.fetchone()["n"]
                if n != 10:
                    raise RuntimeError(f"Core10 recovery incomplete for {td}: {n}/10")

            for symbol in ADDED:
                cur.execute(
                    "SELECT count(*) AS n FROM market_bars WHERE provider='longbridge' AND period='day' AND symbol=%s",
                    (symbol,),
                )
                n = cur.fetchone()["n"]
                if n < 40:
                    raise RuntimeError(f"Added symbol history incomplete for {symbol}: {n}<40")

            for table in PROTECTED_TABLES:
                cur.execute(f"SELECT count(*) AS n FROM {table}")
                report["protected_counts_after"][table] = cur.fetchone()["n"]
                if report["protected_counts_after"][table] != report["protected_counts_before"][table]:
                    raise RuntimeError(f"Protected Shadow/forecast table changed during recovery: {table}")

            conn.commit()

    report["writer_finished_at"] = datetime.now(timezone.utc).isoformat()
    report["status"] = "PASS"
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("PIT_GAP_RECOVERY_PASS")
    print(f"inserted_bars={report['inserted_bars']}")
    print(f"existing_bars={report['existing_bars']}")
    print(f"inserted_sources={report['inserted_sources']}")
    print("shadow_forecast_tables_unchanged=true")
    print("capital_flows_recovered=false")
    print("feature_snapshots_generated=false")

if __name__ == "__main__":
    main()
