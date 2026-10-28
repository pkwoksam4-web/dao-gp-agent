#!/usr/bin/env python3
"""Evaluate a settled cohort only against the exact owner-frozen specification."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path


class EvaluationGateError(RuntimeError):
    pass


def _finite_number(value, name, *, minimum=None):
    try:
        number=float(value)
    except (TypeError,ValueError) as exc:
        raise EvaluationGateError(f"EVALUATION_SPEC_FIELD_INVALID: {name}") from exc
    if not math.isfinite(number) or (minimum is not None and number<minimum):
        raise EvaluationGateError(f"EVALUATION_SPEC_FIELD_INVALID: {name}")
    return number


def load_frozen_evaluation_spec(path, expected_sha256):
    if not isinstance(expected_sha256,str) or not re.fullmatch(r"[0-9a-f]{64}",expected_sha256):
        raise EvaluationGateError("EVALUATION_SPEC_SHA256_REQUIRED")
    try:
        raw=Path(path).read_bytes()
        spec=json.loads(raw)
    except (OSError,ValueError) as exc:
        raise EvaluationGateError("EVALUATION_SPEC_FILE_INVALID") from exc
    actual=hashlib.sha256(raw).hexdigest()
    if actual!=expected_sha256:
        raise EvaluationGateError("EVALUATION_SPEC_SHA256_MISMATCH")
    if not isinstance(spec,dict) or spec.get("schema")!="agent-brain-frozen-evaluation-spec/v1":
        raise EvaluationGateError("EVALUATION_SPEC_SCHEMA_INVALID")
    if spec.get("status")!="FROZEN":
        raise EvaluationGateError("EVALUATION_SPEC_NOT_FROZEN")
    if spec.get("metric")!="top_k_long_only_vs_equal_weight_pool_net_excess":
        raise EvaluationGateError("EVALUATION_SPEC_METRIC_INVALID")
    if spec.get("primary_horizon_sessions")!=5 or 20 not in spec.get("descriptive_only_horizons",[]):
        raise EvaluationGateError("EVALUATION_SPEC_HORIZONS_INVALID")
    symbols=spec.get("universe_symbols")
    top_k=spec.get("top_k")
    if (not isinstance(symbols,list) or len(symbols)<2 or len(set(symbols))!=len(symbols)
            or not isinstance(top_k,int) or top_k<1 or top_k>=len(symbols)):
        raise EvaluationGateError("EVALUATION_SPEC_UNIVERSE_INVALID")
    impl=spec.get("implementation")
    if not isinstance(impl,dict) or impl.get("execution_rule")!="buy_at_anchor_close_hold_then_sell_at_target_close":
        raise EvaluationGateError("EVALUATION_SPEC_EXECUTION_RULE_INVALID")
    for key in ("starting_capital_cny","commission_rate","minimum_commission_cny",
                "sell_stamp_duty_rate","slippage_bps_per_side"):
        _finite_number(impl.get(key),f"implementation.{key}",minimum=0)
    transfer=impl.get("transfer_fee_rate_by_exchange")
    if not isinstance(transfer,dict) or not {"SH","SZ"}.issubset(transfer):
        raise EvaluationGateError("EVALUATION_SPEC_TRANSFER_FEE_INVALID")
    for exchange in ("SH","SZ"):
        _finite_number(transfer[exchange],f"implementation.transfer_fee_rate_by_exchange.{exchange}",minimum=0)
    if _finite_number(impl.get("starting_capital_cny"),"implementation.starting_capital_cny")<=0:
        raise EvaluationGateError("EVALUATION_SPEC_FIELD_INVALID: implementation.starting_capital_cny")
    hurdle=spec.get("minimum_net_excess_pp")
    _finite_number(hurdle,"minimum_net_excess_pp")
    inference=spec.get("inference")
    if not isinstance(inference,dict):
        raise EvaluationGateError("EVALUATION_SPEC_INFERENCE_INVALID")
    for key in ("alpha","power","sigma_pp","method","sigma_source","unit"):
        value=inference.get(key)
        if value is None or (isinstance(value,str) and not value.strip()):
            raise EvaluationGateError(f"EVALUATION_SPEC_INFERENCE_INVALID: {key}")
    for key in ("company_action_rule","missing_data_rule","lookback_rule"):
        value=spec.get(key)
        if not isinstance(value,str) or not value.strip():
            raise EvaluationGateError(f"EVALUATION_SPEC_POLICY_MISSING: {key}")
    return {"spec":spec,"sha256":actual}


def _cost_fraction(positions, capital, implementation):
    commission_rate=float(implementation["commission_rate"])
    minimum_commission=float(implementation["minimum_commission_cny"])
    stamp_rate=float(implementation["sell_stamp_duty_rate"])
    slippage=float(implementation["slippage_bps_per_side"])/10000.0
    transfer_rates=implementation["transfer_fee_rate_by_exchange"]
    total=0.0
    for item,weight in positions:
        exchange=item["symbol"].rsplit(".",1)[-1]
        if exchange not in transfer_rates:
            raise EvaluationGateError(f"EVALUATION_EVENT_EXCHANGE_UNSUPPORTED: {exchange}")
        initial=capital*weight
        terminal=initial*(1.0+float(item["actual_return_5d"]))
        fee=lambda notional:max(minimum_commission,notional*commission_rate)
        transfer_rate=float(transfer_rates[exchange])
        total+=fee(initial)+fee(terminal)
        total+=terminal*stamp_rate
        total+=(initial+terminal)*transfer_rate
        total+=(initial+terminal)*slippage
    return total/capital


def evaluate_settlement_event(event, frozen_spec):
    if isinstance(event.get("result"),dict):
        envelope=event
        event={**envelope["result"],"event_id":envelope.get("event_id"),
               "strategy_run_id":envelope.get("strategy_run_id")}
    spec=frozen_spec["spec"]
    if int(event.get("horizon_sessions",0))!=5:
        raise EvaluationGateError("EVALUATION_PRIMARY_HORIZON_ONLY")
    if event.get("status")!="SETTLED":
        raise EvaluationGateError("EVALUATION_REQUIRES_SETTLED_EVENT")
    outcomes=event.get("outcomes")
    if not isinstance(outcomes,list):
        raise EvaluationGateError("EVALUATION_OUTCOMES_MISSING")
    by_symbol={}
    for item in outcomes:
        symbol=item.get("symbol")
        if not symbol or symbol in by_symbol:
            raise EvaluationGateError("EVALUATION_OUTCOME_SYMBOL_INVALID")
        try:
            value=float(item["actual_return_5d"])
        except (KeyError,TypeError,ValueError) as exc:
            raise EvaluationGateError(f"EVALUATION_RETURN_INVALID: {symbol}") from exc
        if not math.isfinite(value):
            raise EvaluationGateError(f"EVALUATION_RETURN_INVALID: {symbol}")
        by_symbol[symbol]=item
    symbols=spec["universe_symbols"]
    if set(by_symbol)!=set(symbols):
        raise EvaluationGateError("EVALUATION_UNIVERSE_MISMATCH")
    ranked=sorted((by_symbol[s] for s in symbols),key=lambda x:int(x["rank"]))
    k=spec["top_k"]
    top=[(x,1.0/k) for x in ranked[:k]]
    pool=[(x,1.0/len(ranked)) for x in ranked]
    top_gross=sum(weight*float(x["actual_return_5d"]) for x,weight in top)
    pool_gross=sum(weight*float(x["actual_return_5d"]) for x,weight in pool)
    impl=spec["implementation"]
    capital=float(impl["starting_capital_cny"])
    top_net=top_gross-_cost_fraction(top,capital,impl)
    pool_net=pool_gross-_cost_fraction(pool,capital,impl)
    net_excess_pp=100.0*(top_net-pool_net)
    return {
        "schema":"agent-brain-settlement-evaluation/v1",
        "evaluation_status":"CALCULATED",
        "strategy_run_id":event.get("strategy_run_id"),
        "settlement_event_id":event.get("event_id"),
        "horizon_sessions":5,
        "metric":"top_k_long_only_vs_equal_weight_pool_net_excess",
        "gross_excess_pp":100.0*(top_gross-pool_gross),
        "top_k_net_return":top_net,
        "equal_weight_pool_net_return":pool_net,
        "net_excess_pp":net_excess_pp,
        "minimum_net_excess_pp":float(spec["minimum_net_excess_pp"]),
        "meets_point_threshold":net_excess_pp>=float(spec["minimum_net_excess_pp"]),
        "frozen_spec_sha256":frozen_spec["sha256"],
        "target_manifest_sha256":event.get("target_manifest_sha256"),
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--settlement-event",required=True)
    ap.add_argument("--frozen-spec",required=True)
    ap.add_argument("--frozen-spec-sha256",required=True)
    ap.add_argument("--output",default="artifacts/settlement-evaluation.json")
    args=ap.parse_args()
    loaded=load_frozen_evaluation_spec(args.frozen_spec,args.frozen_spec_sha256)
    event=json.loads(Path(args.settlement_event).read_text(encoding="utf-8"))
    report=evaluate_settlement_event(event,loaded)
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SETTLEMENT_EVALUATION_CALCULATED")
    print("frozen_spec_sha256="+loaded["sha256"])


if __name__=="__main__":
    main()
