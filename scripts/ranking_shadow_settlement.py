#!/usr/bin/env python3
"""Settle only clean Core10 ranking Shadow runs at independent 5D/20D horizons."""
from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from shadow_contract_gates import (
        load_exchange_trading_calendar,
        load_quarantine_registry,
        maturity_targets_from_exchange_calendar,
        source_is_live_pit,
        target_is_due,
    )
except ModuleNotFoundError:
    from scripts.shadow_contract_gates import (
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


def avg_ranks(values):
    n=len(values); pairs=sorted(enumerate(values),key=lambda x:x[1]); ranks=[0.0]*n; i=0
    while i<n:
        j=i
        while j+1<n and pairs[j+1][1]==pairs[i][1]: j+=1
        r=(i+j)/2.0
        for k in range(i,j+1): ranks[pairs[k][0]]=r
        i=j+1
    return ranks


def corr(a,b):
    ma=sum(a)/len(a); mb=sum(b)/len(b)
    xa=[x-ma for x in a]; xb=[x-mb for x in b]
    da=math.sqrt(sum(x*x for x in xa)); db=math.sqrt(sum(x*x for x in xb))
    return None if da==0 or db==0 else sum(x*y for x,y in zip(xa,xb))/(da*db)


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


def settle_horizon(cur, run_id, ranking, target, horizon):
    outcomes=[]
    missing_target_symbols=[]
    key=f"actual_return_{horizon}d"
    for x in ranking:
        cur.execute("""
          SELECT mb.close,mb.source_id,s.metadata_json
          FROM market_bars mb JOIN sources s ON s.id=mb.source_id
          WHERE mb.provider='longbridge' AND mb.period='day' AND mb.symbol=%s
            AND ((mb.trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date=%s::date)
          ORDER BY mb.trade_time DESC LIMIT 1
        """,(x["symbol"],target))
        row=cur.fetchone()
        if not row:
            missing_target_symbols.append({"symbol":x["symbol"],"reason":"MISSING_TARGET_BAR"})
            continue
        if not source_is_live_pit(row["metadata_json"]):
            missing_target_symbols.append({
                "symbol":x["symbol"],"reason":"TARGET_NOT_LIVE_PIT","source_id":row["source_id"]
            })
            continue
        actual=float(row["close"])/float(x["anchor_close"])-1.0
        outcomes.append({
            "symbol":x["symbol"],"rank":x["rank"],"candidate_score":x["candidate_score"],
            "anchor_close":x["anchor_close"],"target_close":row["close"],key:actual,
            "target_source_id":row["source_id"],"target_source_mode":"LIVE_PIT",
            "live_shadow_eligible":True,
        })
    settlement_rule=f"{horizon}th China exchange trading session strictly after anchor; exact target date required"
    if missing_target_symbols:
        return {
            "status":"BLOCKED_DATA_GAP","horizon_sessions":horizon,
            "settlement_trade_date":target,"missing_target_symbols":missing_target_symbols,
            "settlement_rule":settlement_rule,"later_date_substitution_allowed":False,
        }
    top=sorted(outcomes,key=lambda z:z["rank"])[:3]
    bottom=sorted(outcomes,key=lambda z:z["rank"])[-3:]
    top_mean=sum(x[key] for x in top)/3
    bottom_mean=sum(x[key] for x in bottom)/3
    scores=[x["candidate_score"] for x in outcomes]
    rets=[x[key] for x in outcomes]
    return {
        "status":"SETTLED","horizon_sessions":horizon,"settlement_trade_date":target,
        "top3_mean_return":top_mean,"bottom3_mean_return":bottom_mean,
        "top_bottom_spread":top_mean-bottom_mean,
        "spearman_rank_ic":corr(avg_ranks(scores),avg_ranks(rets)),
        "outcomes":outcomes,"settlement_rule":settlement_rule,
        "later_date_substitution_allowed":False,
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
            SELECT horizon_sessions,settlement_trade_date,status,event_json
            FROM public.agent_brain_settlement_events
            WHERE strategy_run_id=%s
          """,(run["id"],))
          prior_events=cur.fetchall()
          settled_by_horizon={}
          for prior in prior_events:
              horizon=int(prior["horizon_sessions"])
              if horizon not in target_by_horizon or str(prior["settlement_trade_date"])!=target_by_horizon[horizon]:
                  raise RuntimeError(f"{run['id']}: stored settlement event conflicts with frozen calendar")
              if prior["status"]=="SETTLED":
                  settled_by_horizon[horizon]=decoded_event(prior["event_json"])

          outcomes={}
          for horizon in (5,20):
              key=f"settlement_{horizon}d"
              if horizon in settled_by_horizon:
                  outcomes[horizon]=settled_by_horizon[horizon]["result"]
                  continue
              target=target_by_horizon[horizon]
              if not target or not target_is_due(target,as_of_cn):
                  outcomes[horizon]={"status":"PENDING","horizon_sessions":horizon,
                                     "settlement_trade_date":target}
                  report[f"still_pending_{horizon}d"]+=1
                  continue
              candidate=settle_horizon(cur,run["id"],ranking,target,horizon)
              event=build_settlement_event(run["id"],horizon,target,candidate,now)
              inserted=persist_settlement_event(cur,event)
              report["settlement_events"].append({
                  "event_id":event["event_id"],"strategy_run_id":run["id"],
                  "horizon_sessions":horizon,"inserted":inserted,
              })
              outcomes[horizon]=candidate
              if candidate["status"]=="SETTLED":
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
    report["status"]="BLOCKED_DATA_GAP" if blocked else "PASS"
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    if blocked:
        print("RANKING_SETTLEMENT_CHECK_BLOCKED_DATA_GAP")
    else:
        print("RANKING_SETTLEMENT_CHECK_PASS")
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
