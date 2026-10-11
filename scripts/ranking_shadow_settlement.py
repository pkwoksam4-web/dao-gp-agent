#!/usr/bin/env python3
"""Settle only clean Core10 ranking Shadow runs at independent 5D/20D horizons."""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from shadow_contract_gates import load_quarantine_registry, maturity_targets, source_is_live_pit

CORE10=["000636.SZ","002138.SZ","002156.SZ","600392.SH","600487.SH","600522.SH","600667.SH","600703.SH","601991.SH","605358.SH"]
RANK_VERSION="core10-stable-reversion-lowvol-candidate-v1"
MODE=f"LIVE_SHADOW_RANKING_ONLY|{RANK_VERSION}"
OUT=Path("artifacts/ranking-settlement-report.json")
QUARANTINE=Path(os.environ.get(
    "PROSPECTIVE_QUARANTINE_REGISTRY",
    "evidence/agent_brain/prospective_quarantine_registry_v1.json",
))


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
    observation_id=evidence.get("core13_observation_id")
    if not observation_id:
        raise RuntimeError(f"{strategy_id}: attestation missing core13_observation_id")
    cur.execute("SELECT 1 FROM shadow_observation_snapshots WHERE id=%s",(observation_id,))
    if not cur.fetchone():
        raise RuntimeError(f"{strategy_id}: attested observation missing: {observation_id}")


def eligible_dates(cur, anchor):
    cur.execute("""
      SELECT ((mb.trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date)::text AS trade_date,
             count(DISTINCT mb.symbol) AS n
      FROM market_bars mb
      JOIN sources s ON s.id=mb.source_id
      WHERE mb.provider='longbridge' AND mb.period='day'
        AND mb.symbol=ANY(%s)
        AND ((mb.trade_time::timestamptz AT TIME ZONE 'Asia/Shanghai')::date > %s::date)
        AND (s.metadata_json::jsonb ->> 'mode')='LIVE_PIT'
        AND COALESCE((s.metadata_json::jsonb ->> 'live_shadow_eligible')::boolean,false)=true
      GROUP BY 1
      HAVING count(DISTINCT mb.symbol)=10
      ORDER BY 1
    """,(CORE10,anchor))
    return [r["trade_date"] for r in cur.fetchall()]


def settle_horizon(cur, run_id, ranking, target, horizon):
    outcomes=[]
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
        if not row or not source_is_live_pit(row["metadata_json"]):
            raise RuntimeError(f"{run_id}: SETTLEMENT_EXCLUDED_NON_LIVE {x['symbol']} {target}")
        actual=float(row["close"])/float(x["anchor_close"])-1.0
        outcomes.append({
            "symbol":x["symbol"],"rank":x["rank"],"candidate_score":x["candidate_score"],
            "anchor_close":x["anchor_close"],"target_close":row["close"],key:actual,
            "target_source_id":row["source_id"],"target_source_mode":"LIVE_PIT",
            "live_shadow_eligible":True,
        })
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
        "outcomes":outcomes,
        "settlement_rule":f"{horizon}th eligible LIVE_PIT China trading session strictly after anchor",
    }


def main():
    dsn=os.environ["NEON_DATABASE_URL"]
    now=datetime.now(timezone.utc).isoformat()
    quarantined=load_quarantine_registry(QUARANTINE)
    report={"schema":"agent-brain-ranking-settlement/v2","checked_at":now,
            "pending_checked":0,"settled_5d_now":0,"settled_20d_now":0,
            "still_pending_5d":0,"still_pending_20d":0,
            "excluded_strategy_ids":[],"settled_runs":[]}
    with psycopg.connect(dsn,row_factory=dict_row,connect_timeout=15) as conn:
      with conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("SET LOCAL statement_timeout='30s'")
        cur.execute("SELECT * FROM shadow_strategy_runs WHERE mode=%s ORDER BY start_date,id",(MODE,))
        for run in cur.fetchall():
          metrics=json.loads(run["metrics_json"])
          if run["id"] in quarantined:
              report["excluded_strategy_ids"].append(run["id"])
              continue
          if metrics.get("settlement")!="PENDING" and metrics.get("settlement_20d",{}).get("status")=="SETTLED":
              continue
          report["pending_checked"]+=1
          require_shadow_success(cur,run["id"])
          ranking=json.loads(run["daily_json"]).get("ranking",[])
          if len(ranking)!=10 or sorted(x["symbol"] for x in ranking)!=sorted(CORE10):
              raise RuntimeError(f"{run['id']}: invalid ranking payload")
          if any(x.get("anchor_close") in (None,0) for x in ranking):
              raise RuntimeError(f"{run['id']}: missing anchor_close; cannot settle")
          targets=maturity_targets(eligible_dates(cur,run["start_date"]))
          changed=False
          s5=metrics.get("settlement_5d",{"status":"PENDING"})
          s20=metrics.get("settlement_20d",{"status":"PENDING"})
          if s5.get("status")!="SETTLED":
              if targets["5d"]:
                  s5=settle_horizon(cur,run["id"],ranking,targets["5d"],5)
                  s5["settled_at"]=now; report["settled_5d_now"]+=1; changed=True
              else: report["still_pending_5d"]+=1
          if s20.get("status")!="SETTLED":
              if targets["20d"]:
                  s20=settle_horizon(cur,run["id"],ranking,targets["20d"],20)
                  s20["settled_at"]=now; report["settled_20d_now"]+=1; changed=True
              else: report["still_pending_20d"]+=1
          metrics["settlement_5d"]=s5
          metrics["settlement_20d"]=s20
          metrics["eligible_future_live_pit_sessions"]=targets["eligible_future_sessions"]
          metrics["outcome_data_may_include_recovered_future_bars"]=False
          metrics["automatic_promotion"]=False
          metrics["production_ranking_use"]=False
          if s20.get("status")=="SETTLED":
              metrics["settlement"]="SETTLED"
          if changed:
              cur.execute("UPDATE shadow_strategy_runs SET end_date=%s,metrics_json=%s WHERE id=%s",
                          (targets["20d"] if s20.get("status")=="SETTLED" else run["end_date"],
                           json.dumps(metrics,ensure_ascii=False,separators=(",",":")),run["id"]))
          report["settled_runs"].append({"id":run["id"],"anchor":run["start_date"],
                                         "maturity_5d":s5["status"],"maturity_20d":s20["status"]})
        conn.commit()
    report["excluded_strategy_ids"]=sorted(set(report["excluded_strategy_ids"]))
    report["status"]="PASS"
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("RANKING_SETTLEMENT_CHECK_PASS")
    print("excluded_strategy_ids="+json.dumps(report["excluded_strategy_ids"]))
    print(f"settled_5d_now={report['settled_5d_now']}")
    print(f"settled_20d_now={report['settled_20d_now']}")
    print("automatic_promotion=false")


if __name__=="__main__":
    main()
