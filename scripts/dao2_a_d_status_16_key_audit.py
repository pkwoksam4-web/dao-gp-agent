#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FIELDS = ["date", "code", "tradestatus", "isST"]
EXPECTED_KEY_COUNT = 16
EXPECTED_KEY_SET_SHA256 = "8d0151f61adba6d10da2b06aa0ebcf82d74fa9a3d17cda627c652e71f8697e9c"
D_FROZEN_COMMIT = "2a7056ffd61885046e34dc1494bc668143d96793"
D_SEMANTICS_SOURCE = "scripts/pit_st_collector_v480.py"


def to_baostock_code(symbol: str) -> str:
    symbol = str(symbol).strip().upper()
    if len(symbol) != 9 or symbol[6] != ".":
        raise ValueError(f"invalid exchange-qualified symbol: {symbol}")
    code, exch = symbol.split(".")
    if not (len(code) == 6 and code.isdigit()):
        raise ValueError(f"invalid stock code: {symbol}")
    if exch == "SZ":
        return f"sz.{code}"
    if exch == "SH":
        return f"sh.{code}"
    raise ValueError(f"unsupported exchange: {symbol}")


def _date_in_lifecycle(trade_date: str, basic_rows: list[dict[str, Any]]) -> tuple[str, dict[str, str] | None]:
    if not basic_rows:
        return "LIFECYCLE_UNKNOWN", None

    for row in basic_rows:
        ipo = str(row.get("ipoDate") or "").strip()
        out = str(row.get("outDate") or "").strip()
        if not ipo:
            continue
        if trade_date >= ipo and (not out or trade_date <= out):
            return "INSIDE_LIFECYCLE", {"ipoDate": ipo, "outDate": out}

    usable = [
        {"ipoDate": str(r.get("ipoDate") or "").strip(), "outDate": str(r.get("outDate") or "").strip()}
        for r in basic_rows
        if str(r.get("ipoDate") or "").strip()
    ]
    if usable:
        return "OUTSIDE_LIFECYCLE", usable[0]
    return "LIFECYCLE_UNKNOWN", None


def classify_key(
    *,
    trade_date: str,
    formal_amount_cny: float,
    status_row: dict[str, Any] | None,
    basic_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    lifecycle_status, lifecycle_row = _date_in_lifecycle(trade_date, basic_rows)
    nonzero_formal_turnover = float(formal_amount_cny) > 0

    tradestatus = None if status_row is None else str(status_row.get("tradestatus") or "").strip()
    is_st_raw = None if status_row is None else str(status_row.get("isST") or "").strip()
    is_st = is_st_raw == "1" if is_st_raw in {"0", "1"} else None

    conflict_reasons: list[str] = []
    if lifecycle_status != "INSIDE_LIFECYCLE":
        conflict_reasons.append(lifecycle_status)
    if status_row is None:
        conflict_reasons.append("STATUS_ROW_ABSENT")
    elif tradestatus != "1":
        conflict_reasons.append(f"TRADESTATUS_{tradestatus or 'UNKNOWN'}")
    if status_row is not None and is_st_raw not in {"0", "1"}:
        conflict_reasons.append("ISST_INVALID_OR_UNKNOWN")

    if nonzero_formal_turnover and conflict_reasons:
        classification = "EXPECTED_AXIS_EVIDENCE_CONFLICT"
        expected_axis_review_required = True
    elif lifecycle_status == "INSIDE_LIFECYCLE" and status_row is not None and tradestatus == "1" and is_st_raw in {"0", "1"}:
        classification = "D_STATUS_VALID_TRADABLE"
        expected_axis_review_required = False
    else:
        classification = "D_STATUS_UNRESOLVED_FAIL_CLOSED"
        expected_axis_review_required = bool(conflict_reasons)

    return {
        "classification": classification,
        "trade_date": trade_date,
        "formal_amount_cny": formal_amount_cny,
        "nonzero_formal_turnover": nonzero_formal_turnover,
        "lifecycle_status": lifecycle_status,
        "lifecycle_row": lifecycle_row,
        "status_row_present": status_row is not None,
        "tradestatus": tradestatus,
        "is_st": is_st,
        "conflict_reasons": conflict_reasons,
        "expected_axis_review_required": expected_axis_review_required,
        "na_allowed": False,
    }


def _materialize_result_set(rs: Any) -> tuple[list[dict[str, str]], str, str]:
    error_code = str(getattr(rs, "error_code", "EXCEPTION"))
    error_msg = str(getattr(rs, "error_msg", "") or "")
    rows: list[dict[str, str]] = []
    if error_code == "0":
        while rs.next():
            rows.append(dict(zip(rs.fields, rs.get_row_data())))
    return rows, error_code, error_msg


def query_exact_status(bs: Any, symbol: str, trade_date: str) -> dict[str, Any]:
    code = to_baostock_code(symbol)
    try:
        rs = bs.query_history_k_data_plus(
            code,
            ",".join(FIELDS),
            start_date=trade_date,
            end_date=trade_date,
            frequency="d",
            adjustflag="3",
        )
        rows, ec, em = _materialize_result_set(rs)
        return {"error_code": ec, "error_msg": em, "rows": rows}
    except Exception as exc:
        return {"error_code": "EXCEPTION", "error_msg": repr(exc), "rows": []}


def query_basic(bs: Any, symbol: str) -> dict[str, Any]:
    code = to_baostock_code(symbol)
    try:
        rs = bs.query_stock_basic(code=code)
        rows, ec, em = _materialize_result_set(rs)
        return {"error_code": ec, "error_msg": em, "rows": rows}
    except Exception as exc:
        return {"error_code": "EXCEPTION", "error_msg": repr(exc), "rows": []}


def load_frozen_keys(path: Path) -> tuple[list[dict[str, Any]], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("artifact") != "GP12_CANDIDATE_MAIN_NET_FLOW_RESIDUAL_LEDGER_V1":
        raise RuntimeError("unexpected residual ledger artifact")
    keys = payload.get("unresolved_keys")
    if not isinstance(keys, list) or len(keys) != EXPECTED_KEY_COUNT:
        raise RuntimeError(f"expected exactly {EXPECTED_KEY_COUNT} unresolved keys")

    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in keys:
        symbol = str(row["ts_code"]).strip().upper()
        trade_date = str(row["trade_date"]).strip()
        amount = float(row["formal_amount_cny"])
        to_baostock_code(symbol)
        if amount <= 0:
            raise RuntimeError(f"frozen residual key has non-positive Formal turnover: {symbol}/{trade_date}")
        key = (symbol, trade_date)
        if key in seen:
            raise RuntimeError(f"duplicate residual key: {symbol}/{trade_date}")
        seen.add(key)
        normalized.append({"ts_code": symbol, "trade_date": trade_date, "formal_amount_cny": amount})

    serialized = "\n".join(f"{r['ts_code']},{r['trade_date']}" for r in sorted(normalized, key=lambda x: (x["ts_code"], x["trade_date"])))
    key_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    if key_hash != EXPECTED_KEY_SET_SHA256:
        raise RuntimeError(f"16-key scope hash mismatch: {key_hash} != {EXPECTED_KEY_SET_SHA256}")
    return normalized, key_hash


def run_audit(ledger: Path, out_dir: Path) -> int:
    import baostock as bs

    out_dir.mkdir(parents=True, exist_ok=True)
    keys, key_hash = load_frozen_keys(ledger)
    retrieved_at = datetime.now(timezone.utc).isoformat()

    raw_queries: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    transport_errors: list[dict[str, str]] = []

    login = bs.login()
    login_ec = str(getattr(login, "error_code", "EXCEPTION"))
    login_em = str(getattr(login, "error_msg", "") or "")
    if login_ec != "0":
        result = {
            "artifact": "DAO2_A_D_STATUS_16_KEY_AUDIT_V1",
            "status": "BLOCKED_TRANSPORT",
            "retrieved_at_utc": retrieved_at,
            "provider": "BaoStock",
            "d_frozen_commit": D_FROZEN_COMMIT,
            "d_semantics_source": D_SEMANTICS_SOURCE,
            "key_count": len(keys),
            "key_set_sha256": key_hash,
            "login_error_code": login_ec,
            "login_error_msg": login_em,
            "admission_changed": False,
            "expected_rows_changed": False,
            "resolved_rows_changed": False,
            "na_rows_admitted": 0,
        }
        (out_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 2

    try:
        basic_cache: dict[str, dict[str, Any]] = {}
        for item in keys:
            symbol = item["ts_code"]
            trade_date = item["trade_date"]
            status = query_exact_status(bs, symbol, trade_date)
            if symbol not in basic_cache:
                basic_cache[symbol] = query_basic(bs, symbol)
            basic = basic_cache[symbol]

            raw_queries.append({
                "ts_code": symbol,
                "trade_date": trade_date,
                "status_query": status,
                "basic_query": basic,
            })

            if status["error_code"] != "0" or basic["error_code"] != "0":
                transport_errors.append({
                    "ts_code": symbol,
                    "trade_date": trade_date,
                    "status_error": f"{status['error_code']} {status['error_msg']}",
                    "basic_error": f"{basic['error_code']} {basic['error_msg']}",
                })
                row = {
                    **item,
                    "classification": "BLOCKED_TRANSPORT",
                    "lifecycle_status": "UNKNOWN_TRANSPORT",
                    "status_row_present": False,
                    "tradestatus": None,
                    "is_st": None,
                    "conflict_reasons": ["QUERY_TRANSPORT_ERROR"],
                    "expected_axis_review_required": False,
                    "na_allowed": False,
                }
            else:
                exact_rows = [r for r in status["rows"] if str(r.get("date") or "").strip() == trade_date]
                if len(exact_rows) > 1:
                    row = {
                        **item,
                        "classification": "D_STATUS_UNRESOLVED_FAIL_CLOSED",
                        "lifecycle_status": "UNKNOWN_DUPLICATE_STATUS_ROWS",
                        "status_row_present": True,
                        "tradestatus": None,
                        "is_st": None,
                        "conflict_reasons": ["DUPLICATE_EXACT_STATUS_ROWS"],
                        "expected_axis_review_required": True,
                        "na_allowed": False,
                    }
                else:
                    classified = classify_key(
                        trade_date=trade_date,
                        formal_amount_cny=item["formal_amount_cny"],
                        status_row=exact_rows[0] if exact_rows else None,
                        basic_rows=basic["rows"],
                    )
                    row = {**item, **classified}
            rows.append(row)
    finally:
        bs.logout()

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    st_keys = [f"{r['ts_code']}/{r['trade_date']}" for r in rows if r.get("is_st") is True]
    conflicts = [f"{r['ts_code']}/{r['trade_date']}" for r in rows if r.get("classification") == "EXPECTED_AXIS_EVIDENCE_CONFLICT"]
    blocked = [f"{r['ts_code']}/{r['trade_date']}" for r in rows if str(r.get("classification", "")).startswith("BLOCKED_")]

    result_status = "PASS_DIAGNOSTIC_ONLY" if not transport_errors and not blocked else "BLOCKED_TRANSPORT"
    result = {
        "artifact": "DAO2_A_D_STATUS_16_KEY_AUDIT_V1",
        "status": result_status,
        "retrieved_at_utc": retrieved_at,
        "provider": "BaoStock",
        "query_contract": {"fields": FIELDS, "frequency": "d", "adjustflag": "3", "exact_date_only": True},
        "d_frozen_commit": D_FROZEN_COMMIT,
        "d_semantics_source": D_SEMANTICS_SOURCE,
        "key_count": len(keys),
        "key_set_sha256": key_hash,
        "classification_counts": counts,
        "st_key_count": len(st_keys),
        "st_keys": st_keys,
        "expected_axis_conflict_count": len(conflicts),
        "expected_axis_conflicts": conflicts,
        "transport_error_count": len(transport_errors),
        "transport_errors": transport_errors,
        "na_rows_admitted": 0,
        "admission_changed": False,
        "expected_rows_changed": False,
        "resolved_rows_changed": False,
        "governance": "DIAGNOSTIC_ONLY_DO_NOT_MUTATE_A_OR_D",
    }

    (out_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "per_key.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "raw_queries.json").write_text(json.dumps(raw_queries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    csv_fields = [
        "ts_code", "trade_date", "formal_amount_cny", "classification", "lifecycle_status",
        "status_row_present", "tradestatus", "is_st", "expected_axis_review_required", "na_allowed",
    ]
    with (out_dir / "per_key.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in csv_fields})

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result_status == "PASS_DIAGNOSTIC_ONLY" else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    return run_audit(Path(args.ledger), Path(args.out_dir))


if __name__ == "__main__":
    raise SystemExit(main())
