#!/usr/bin/env python3
"""Settle only clean Core10 ranking Shadow runs at independent 5D/20D horizons."""
from __future__ import annotations

import hashlib
import json
import os
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from shadow_contract_gates import (
        ContractGateError,
        load_exchange_trading_calendar,
        load_quarantine_registry,
        maturity_targets_from_exchange_calendar,
        source_is_live_pit,
        target_is_due,
    )
except ModuleNotFoundError:
    from scripts.shadow_contract_gates import (
        ContractGateError,
        load_exchange_trading_calendar,
        load_quarantine_registry,
        maturity_targets_from_exchange_calendar,
        source_is_live_pit,
        target_is_due,
    )

CORE10=["000636.SZ","002138.SZ","002156.SZ","600392.SH","600487.SH","600522.SH","600667.SH","600703.SH","601991.SH","605358.SH"]
RANK_VERSION="core10-stable-reversion-lowvol-candidate-v1"
MODE=f"LIVE_SHADOW_RANKING_ONLY|{RANK_VERSION}"
OUT=Path("artifacts/ranking-settlement-report.json")
QUARANTINE=Path(os.environ.get(
    "PROSPECTIVE_QUARANTINE_REGISTRY",
    "evidence/agent_brain/prospective_quarantine_registry_v1.json",
))
EXCHANGE_CALENDAR=Path(os.environ.get(
    "CN_EXCHANGE_CALENDAR_PATH",
    "evidence/agent_brain/cn_exchange_calendar_2026.json",
))
SHANGHAI=ZoneInfo("Asia/Shanghai")


def build_settlement_event(strategy_id, horizon, target, result, evaluated_at):
    material = {
        "schema": "agent-brain-settlement-event/v1",
        "strategy_run_id": strategy_id,
        "horizon_sessions": int(horizon),
        "settlement_trade_date": target,
        "result": result,
    }
    canonical = json.dumps(material, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False)
    event_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {**material, "event_id": event_id, "evaluated_at": evaluated_at}


def persist_settlement_event(cur, event):
    cur.execute("""
      INSERT INTO public.agent_brain_settlement_events(
        event_id,strategy_run_id,horizon_sessions,settlement_trade_date,status,event_json
      ) VALUES (%s,%s,%s,%s,%s,%s::jsonb)
      ON CONFLICT (event_id) DO NOTHING
    """, (event["event_id"], event["strategy_run_id"], event["horizon_sessions"],
          event["settlement_trade_date"], event["result"]["status"],
          json.dumps(event, ensure_ascii=False, separators=(",", ":"), allow_nan=False)))
    return cur.rowcount == 1


def decoded_event(value):
    return value if isinstance(value, dict) else json.loads(value)


def latest_settlement_events(rows):
    """Resolve the current append-only event independently for each horizon."""
    latest = {}
    for row in rows:
        horizon = int(row["horizon_sessions"])
        current = latest.get(horizon)
        event_order = (row["created_at"], row["event_id"])
        current_order = (current["created_at"], current["event_id"]) if current else None
        if current is None or event_order > current_order:
            latest[horizon] = {**row, "event_json": decoded_event(row["event_json"])}
    return latest


def require_shadow_success(cur, strategy_id):
    cur.execute("""
      SELECT evidence_json FROM live_shadow_run_attestations
      WHERE status='PASS_RANKING_ONLY'
        AND (evidence_json::jsonb ->> 'strategy_run_id')=%s
      ORDER BY created_at DESC LIMIT 1
    """,(strategy_id,))
    row=cur.fetchone()
    if not row:
        raise RuntimeError(f"{strategy_id}: SETTLEMENT_BLOCKED_WAITING_SHADOW_OBSERVATION")
    evidence=json.loads(row["evidence_json"])
    ingest=evidence.get("ingest_evidence")
    if not isinstance(ingest,dict) or ingest.get("status")!="PASS":
        raise RuntimeError(f"{strategy_id}: attestation missing PASS ingest_evidence")
    hashes=[ingest.get("manifest_sha256"),ingest.get("ingest_report_sha256")]
    if any(not isinstance(h,str) or len(h)!=64 or any(c not in "0123456789abcdef" for c in h) for h in hashes):
        raise RuntimeError(f"{strategy_id}: attestation has invalid ingest evidence hash")
    if ingest.get("verified_rows")!={"bars":13,"features":13}:
        raise RuntimeError(f"{strategy_id}: attestation ingest row counts are not 13/13")
    observation_id=evidence.get("core13_observation_id")
    if not observation_id:
        raise RuntimeError(f"{strategy_id}: attestation missing core13_observation_id")
    cur.execute("SELECT 1 FROM shadow_observation_snapshots WHERE id=%s",(observation_id,))
    if not cur.fetchone():
        raise RuntimeError(f"{strategy_id}: attested observation missing: {observation_id}")


def load_reviewed_outcome_manifest(path, *, expected_trade_date):
    """Load only an explicitly reviewed, hash-bound no-database price manifest."""
    path=Path(path)
    try:
        raw=path.read_bytes()
        document=json.loads(raw)
    except FileNotFoundError as exc:
        raise ContractGateError(f"REVIEWED_OUTCOME_MANIFEST_MISSING: {path}") from exc
    except (OSError,ValueError) as exc:
        raise ContractGateError(f"REVIEWED_OUTCOME_MANIFEST_INVALID: {path}") from exc
    if document.get("schema")!="agent-brain-reviewed-outcome-manifest/v1":
        raise ContractGateError("OUTCOME_MANIFEST_SCHEMA_INVALID")
    if document.get("status")!="REVIEWED":
        raise ContractGateError("OUTCOME_MANIFEST_NOT_REVIEWED")
    review=document.get("review")
    if (not isinstance(review,dict) or review.get("status")!="APPROVED"
            or not str(review.get("pull_request_url","")).startswith(
                "https://github.com/pkwoksam4-web/dao-gp-agent/pull/"
            ) or not review.get("approver")):
        raise ContractGateError("OUTCOME_MANIFEST_REVIEW_ATTESTATION_MISSING")
    payload=document.get("payload")
    if not isinstance(payload,dict):
        raise ContractGateError("OUTCOME_MANIFEST_PAYLOAD_INVALID")
    canonical=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)
    payload_sha=hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    claimed=document.get("payload_sha256")
    if not isinstance(claimed,str) or claimed!=payload_sha:
        raise ContractGateError("OUTCOME_MANIFEST_HASH_MISMATCH")
    if payload.get("trade_date_cn")!=expected_trade_date:
        raise ContractGateError("OUTCOME_MANIFEST_TRADE_DATE_MISMATCH")
    bars=payload.get("symbols")
    if not isinstance(bars,list) or not bars:
        raise ContractGateError("OUTCOME_MANIFEST_SYMBOLS_MISSING")
    seen=set()
    for bar in bars:
        if not isinstance(bar,dict) or not isinstance(bar.get("symbol"),str):
            raise ContractGateError("OUTCOME_MANIFEST_SYMBOL_INVALID")
        symbol=bar["symbol"]
        if symbol in seen:
            raise ContractGateError(f"OUTCOME_MANIFEST_DUPLICATE_SYMBOL: {symbol}")
        seen.add(symbol)
        raw_hash=bar.get("raw_response_sha256")
        if not isinstance(raw_hash,str) or not re.fullmatch(r"[0-9a-f]{64}",raw_hash):
            raise ContractGateError(f"OUTCOME_MANIFEST_RAW_HASH_INVALID: {symbol}")
        try:
            close=Decimal(str(bar.get("target_close")))
        except (InvalidOperation,TypeError,ValueError) as exc:
            raise ContractGateError(f"OUTCOME_MANIFEST_CLOSE_INVALID: {symbol}") from exc
        if not close.is_finite() or close<=0:
            raise ContractGateError(f"OUTCOME_MANIFEST_CLOSE_INVALID: {symbol}")
    return {
        "payload":payload,
        "payload_sha256":payload_sha,
        "manifest_sha256":hashlib.sha256(raw).hexdigest(),
        "review":review,
    }


def settle_horizon(ranking, target, horizon, manifest):
    """Persist only per-symbol target closes and returns from reviewed evidence."""
    payload=manifest["payload"]
    target_by_symbol={x["symbol"]:x for x in payload["symbols"]}
    outcomes=[]
    missing=[]
    return_key=f"actual_return_{horizon}d"
    for item in ranking:
        symbol=item["symbol"]
        bar=target_by_symbol.get(symbol)
        if not bar:
            missing.append({"symbol":symbol,"reason":"MISSING_TARGET_SYMBOL_IN_REVIEWED_MANIFEST"})
            continue
        try:
            anchor=Decimal(str(item.get("anchor_close")))
            close=Decimal(str(bar.get("target_close")))
        except (InvalidOperation,TypeError,ValueError) as exc:
            raise ContractGateError(f"SETTLEMENT_PRICE_INVALID: {symbol}") from exc
        if not anchor.is_finite() or anchor<=0 or not close.is_finite() or close<=0:
            raise ContractGateError(f"SETTLEMENT_PRICE_INVALID: {symbol}")
        outcome={
            "symbol":symbol,
            "rank":int(item["rank"]),
            "anchor_close":str(item["anchor_close"]),
            "target_close":str(bar["target_close"]),
            return_key:float(close/anchor-Decimal(1)),
            "target_source_raw_sha256":bar["raw_response_sha256"],
            "target_manifest_sha256":manifest["manifest_sha256"],
            "target_provider":payload.get("provider"),
        }
        outcomes.append(outcome)
    settlement_rule=f"{horizon}th China exchange trading session strictly after anchor; reviewed exact-date manifest required"
    if missing:
        return {
            "status":"BLOCKED_DATA_GAP","horizon_sessions":horizon,
            "settlement_trade_date":target,"missing_target_symbols":missing,
            "settlement_rule":settlement_rule,"later_date_substitution_allowed":False,
            "target_manifest_sha256":manifest["manifest_sha256"],
        }
    return {
        "status":"SETTLED","horizon_sessions":horizon,"settlement_trade_date":target,
        "outcomes":outcomes,"settlement_rule":settlement_rule,
        "later_date_substitution_allowed":False,
        "target_manifest_sha256":manifest["manifest_sha256"],
        "target_payload_sha256":manifest["payload_sha256"],
    }

def main():
    import psycopg
    from psycopg.rows import dict_row

    dsn=os.environ["NEON_DATABASE_URL"]
    now_dt=datetime.now(timezone.utc)
    now=now_dt.isoformat()
    as_of_cn=now_dt.astimezone(SHANGHAI).date().isoformat()
    quarantined=load_quarantine_registry(QUARANTINE)
    exchange_dates=load_exchange_trading_calendar(EXCHANGE_CALENDAR)
    report={"schema":"agent-brain-ranking-settlement/v4","checked_at":now,"as_of_cn":as_of_cn,
            "exchange_calendar_path":str(EXCHANGE_CALENDAR),"exchange_calendar_sessions":len(exchange_dates),
            "pending_checked":0,"settled_5d_now":0,"settled_20d_now":0,
            "still_pending_5d":0,"still_pending_20d":0,
            "blocked_data_gap_5d":0,"blocked_data_gap_20d":0,
            "excluded_strategy_ids":[],"settled_runs":[],"settlement_events":[]}
    with psycopg.connect(dsn,row_factory=dict_row,connect_timeout=15) as conn:
      with conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("SET LOCAL statement_timeout='30s'")
        cur.execute("SELECT * FROM shadow_strategy_runs WHERE mode=%s ORDER BY start_date,id",(MODE,))
        for run in cur.fetchall():
          if run["id"] in quarantined:
              report["excluded_strategy_ids"].append(run["id"])
              continue
          report["pending_checked"]+=1
          require_shadow_success(cur,run["id"])
          ranking=json.loads(run["daily_json"]).get("ranking",[])
          if len(ranking)!=10 or sorted(x["symbol"] for x in ranking)!=sorted(CORE10):
              raise RuntimeError(f"{run['id']}: invalid ranking payload")
          if any(x.get("anchor_close") in (None,0) for x in ranking):
              raise RuntimeError(f"{run['id']}: missing anchor_close; cannot settle")
          anchor=str(run["start_date"])
          targets=maturity_targets_from_exchange_calendar(anchor,exchange_dates)
          target_by_horizon={5:targets["5d"],20:targets["20d"]}
          cur.execute("""
            SELECT horizon_sessions,settlement_trade_date,status,event_id,event_json,created_at
            FROM public.agent_brain_settlement_events
            WHERE strategy_run_id=%s
          """,(run["id"],))
          latest_by_horizon=latest_settlement_events(cur.fetchall())
          for horizon,prior in latest_by_horizon.items():
              if horizon not in target_by_horizon or str(prior["settlement_trade_date"])!=target_by_horizon[horizon]:
                  raise RuntimeError(f"{run['id']}: stored settlement event conflicts with frozen calendar")

          outcomes={}
          for horizon in (5,20):
              key=f"settlement_{horizon}d"
              current=latest_by_horizon.get(horizon)
              if current and current["status"]=="SETTLED":
                  outcomes[horizon]=current["event_json"]["result"]
                  continue
              target=target_by_horizon[horizon]
              if not target or not target_is_due(target,as_of_cn):
                  if current:
                      outcomes[horizon]=current["event_json"]["result"]
                  else:
                      outcomes[horizon]={"status":"PENDING","horizon_sessions":horizon,
                                         "settlement_trade_date":target}
                      report[f"still_pending_{horizon}d"]+=1
                  continue
              manifest_path=REVIEWED_OUTCOME_MANIFEST_DIR / f"{target}.json"
              reviewed_manifest=load_reviewed_outcome_manifest(
                  manifest_path,expected_trade_date=target
              )
              candidate=settle_horizon(ranking,target,horizon,reviewed_manifest)
              event=build_settlement_event(run["id"],horizon,target,candidate,now)
              inserted=persist_settlement_event(cur,event)
              if inserted:
                  latest_by_horizon[horizon]={
                      "event_id":event["event_id"],"horizon_sessions":horizon,
                      "settlement_trade_date":target,"status":candidate["status"],
                      "created_at":now_dt,"event_json":event,
                  }
              report["settlement_events"].append({
                  "event_id":event["event_id"],"strategy_run_id":run["id"],
                  "horizon_sessions":horizon,"inserted":inserted,
              })
              current=latest_by_horizon.get(horizon)
              outcomes[horizon]=current["event_json"]["result"]
              if current["status"]=="SETTLED":
                  if inserted:
                      report[f"settled_{horizon}d_now"]+=1
              else:
                  report[f"blocked_data_gap_{horizon}d"]+=1

          report["settled_runs"].append({
              "id":run["id"],"anchor":anchor,"target_5d":targets["5d"],"target_20d":targets["20d"],
              "maturity_5d":outcomes[5]["status"],"maturity_20d":outcomes[20]["status"]
          })
        conn.commit()
    report["excluded_strategy_ids"]=sorted(set(report["excluded_strategy_ids"]))
    blocked=report["blocked_data_gap_5d"]+report["blocked_data_gap_20d"]
    report["status"]="BLOCKED_DATA_GAP" if blocked else "SETTLEMENT_CAPTURE_COMPLETE"
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    if blocked:
        print("RANKING_SETTLEMENT_CHECK_BLOCKED_DATA_GAP")
    else:
        print("SETTLEMENT_CAPTURE_COMPLETE")
    print("excluded_strategy_ids="+json.dumps(report["excluded_strategy_ids"]))
    print(f"settled_5d_now={report['settled_5d_now']}")
    print(f"settled_20d_now={report['settled_20d_now']}")
    print(f"blocked_data_gap_5d={report['blocked_data_gap_5d']}")
    print(f"blocked_data_gap_20d={report['blocked_data_gap_20d']}")
    print("automatic_promotion=false")
    if blocked:
        raise SystemExit(2)


if __name__=="__main__":
    main()
