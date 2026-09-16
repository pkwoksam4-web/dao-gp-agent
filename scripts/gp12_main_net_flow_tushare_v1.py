from __future__ import annotations

import datetime as dt
import math
from zoneinfo import ZoneInfo


FORMAL_START = "2020-06-01"
FORMAL_END = "2026-04-17"
FORMAL_SYMBOL_N = 844
EXPECTED_TRADE_ROWS = 1_011_607
SOURCE = "TUSHARE_MONEYFLOW_LG_ELG_ACTIVE_BUY_MINUS_SELL"
SHANGHAI = ZoneInfo("Asia/Shanghai")


def _append_once(blockers: list[str], value: str) -> None:
    if value not in blockers:
        blockers.append(value)


def normalize_symbol(symbol: str) -> str:
    value = str(symbol).strip().upper()
    if "." not in value:
        raise ValueError(f"exchange-qualified symbol required: {symbol!r}")
    code, exchange = value.split(".", 1)
    if len(code) != 6 or not code.isdigit() or exchange not in {"SZ", "SH"}:
        raise ValueError(f"unsupported symbol: {symbol!r}")
    return f"{code}.{exchange}"


def _finite_nonnegative(value: object, label: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(out):
        raise ValueError(f"{label} must be finite")
    if out < 0:
        raise ValueError(f"{label} must be nonnegative")
    return out


def _trade_date_to_iso(value: object) -> str:
    raw = str(value).strip()
    if len(raw) == 8 and raw.isdigit():
        day = dt.datetime.strptime(raw, "%Y%m%d").date()
    else:
        day = dt.date.fromisoformat(raw[:10])
    return day.isoformat()


def close_known_at(date_value: str) -> str:
    day = dt.date.fromisoformat(date_value)
    return dt.datetime.combine(day, dt.time(15, 0), tzinfo=SHANGHAI).isoformat()


def normalize_moneyflow_records(symbol: str, records: list[dict]) -> list[dict]:
    symbol = normalize_symbol(symbol)
    amount_fields = (
        "buy_lg_amount",
        "sell_lg_amount",
        "buy_elg_amount",
        "sell_elg_amount",
    )
    normalized: list[dict] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"moneyflow row {index} must be an object")
        row_symbol = normalize_symbol(record.get("ts_code", ""))
        if row_symbol != symbol:
            raise ValueError(
                f"moneyflow row {index} identity mismatch: expected {symbol}, got {row_symbol}"
            )
        date_value = _trade_date_to_iso(record.get("trade_date", ""))
        values = {
            field: _finite_nonnegative(record.get(field), f"moneyflow row {index} {field}")
            for field in amount_fields
        }
        main_net_flow_wan = (
            values["buy_lg_amount"]
            + values["buy_elg_amount"]
            - values["sell_lg_amount"]
            - values["sell_elg_amount"]
        )
        normalized.append(
            {
                "symbol": symbol,
                "date": date_value,
                "main_net_flow_cny": main_net_flow_wan * 10_000.0,
                "known_at": close_known_at(date_value),
                "source": SOURCE,
            }
        )
    normalized.sort(key=lambda row: row["date"])
    return normalized


def audit_symbol_rows(symbol: str, expected_dates: list[str], rows: list[dict]) -> dict:
    symbol = normalize_symbol(symbol)
    blockers: list[str] = []
    observed_dates: list[str] = []
    invalid_date = False
    invalid_value = False

    for row in rows:
        date_value = str(row.get("date", "")).strip()
        try:
            dt.date.fromisoformat(date_value)
        except ValueError:
            invalid_date = True
        observed_dates.append(date_value)
        try:
            value = float(row.get("main_net_flow_cny"))
            if not math.isfinite(value):
                invalid_value = True
        except (TypeError, ValueError):
            invalid_value = True

    if invalid_date:
        _append_once(blockers, "MAIN_NET_FLOW_INVALID_DATE")
    if invalid_value:
        _append_once(blockers, "MAIN_NET_FLOW_INVALID_VALUE")
    if len(observed_dates) != len(set(observed_dates)):
        _append_once(blockers, "MAIN_NET_FLOW_DUPLICATE_DATE")
    if any(a >= b for a, b in zip(observed_dates, observed_dates[1:])):
        _append_once(blockers, "MAIN_NET_FLOW_DATE_ORDER_INVALID")

    expected_set = set(expected_dates)
    observed_set = set(observed_dates)
    missing = sorted(expected_set - observed_set)
    extra = sorted(observed_set - expected_set)
    if missing:
        _append_once(blockers, "MAIN_NET_FLOW_DATE_GAP")
    if extra:
        _append_once(blockers, "MAIN_NET_FLOW_EXTRA_DATE")

    coverage_exact = not any(
        blocker in blockers
        for blocker in (
            "MAIN_NET_FLOW_INVALID_DATE",
            "MAIN_NET_FLOW_DUPLICATE_DATE",
            "MAIN_NET_FLOW_DATE_ORDER_INVALID",
            "MAIN_NET_FLOW_DATE_GAP",
            "MAIN_NET_FLOW_EXTRA_DATE",
        )
    )
    first = observed_dates[0] if observed_dates else None
    last = observed_dates[-1] if observed_dates else None
    return {
        "symbol": symbol,
        "expected_row_n": len(expected_dates),
        "row_n": len(rows),
        "first": first,
        "last": last,
        "missing_date_n": len(missing),
        "extra_date_n": len(extra),
        "missing_dates_sample": missing[:20],
        "extra_dates_sample": extra[:20],
        "coverage_exact": coverage_exact,
        "pit_policy_valid": not invalid_date,
        "pit_scope": "SESSION_CLOSE_NO_LOOKAHEAD_POLICY",
        "same_session_main_net_flow_usable_before_close": False,
        "historical_provider_publication_timestamp_proven": False,
        "symbol_pass": not blockers,
        "blockers": blockers,
    }


def summarize_formal_audit(
    records: list[dict], *, expected_trade_rows: int = EXPECTED_TRADE_ROWS
) -> dict:
    blockers: list[str] = []
    symbols = [str(record.get("symbol", "")) for record in records]
    if len(symbols) != len(set(symbols)):
        _append_once(blockers, "MAIN_NET_FLOW_DUPLICATE_SYMBOL")
    if len(records) != FORMAL_SYMBOL_N:
        _append_once(blockers, "MAIN_NET_FLOW_FORMAL_SYMBOL_COVERAGE_INCOMPLETE")

    pass_n = sum(record.get("symbol_pass") is True for record in records)
    fail_n = len(records) - pass_n
    if pass_n != FORMAL_SYMBOL_N or fail_n != 0:
        _append_once(blockers, "MAIN_NET_FLOW_SYMBOL_AUDIT_FAILURES")

    observed_rows = sum(int(record.get("row_n") or 0) for record in records)
    if observed_rows != expected_trade_rows:
        _append_once(blockers, "MAIN_NET_FLOW_TOTAL_ROW_COVERAGE_MISMATCH")

    return {
        "artifact": "GP12_MAIN_NET_FLOW_FULL_AUDIT_V1",
        "version": "1.0",
        "formal_window": [FORMAL_START, FORMAL_END],
        "formal_symbol_n": len(records),
        "pass_n": pass_n,
        "fail_n": fail_n,
        "expected_trade_rows": expected_trade_rows,
        "observed_main_net_flow_rows": observed_rows,
        "source": SOURCE,
        "source_amount_unit": "wan_cny",
        "candidate_unit": "cny",
        "semantic_definition": "large_plus_extra_large_active_buy_minus_sell",
        "pit_scope": "SESSION_CLOSE_NO_LOOKAHEAD_POLICY",
        "same_session_main_net_flow_usable_before_close": False,
        "historical_provider_publication_timestamp_proven": False,
        "main_net_flow_candidate_pit_verified": not blockers,
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
        "blockers": blockers,
    }
