#!/usr/bin/env python3
"""Pure, fail-closed calendar gates for prospective PIT features."""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path

CORE13 = [
    "000636.SZ","002138.SZ","002156.SZ","600392.SH","600487.SH",
    "600522.SH","600667.SH","600703.SH","601991.SH","605358.SH",
    "000977.SZ","000938.SZ","000063.SZ",
]


class ContractGateError(RuntimeError):
    pass


def validate_prev_close_continuity(rows, latest_by_symbol, *, expected_previous_trade_date):
    try:
        date.fromisoformat(expected_previous_trade_date)
    except Exception as exc:
        raise ContractGateError("PIT_PREV_CLOSE_CONTINUITY_FAILED: EXPECTED_PREVIOUS_SESSION_INVALID") from exc
    by_symbol = {x["symbol"]: x for x in rows}
    if sorted(by_symbol) != sorted(CORE13):
        raise ContractGateError("PIT_PREV_CLOSE_CONTINUITY_FAILED: CORE13_NOT_13_OF_13")
    checked = []
    for symbol in CORE13:
        prior = latest_by_symbol.get(symbol)
        if not prior or prior.get("close") is None:
            raise ContractGateError(f"PIT_PREV_CLOSE_CONTINUITY_FAILED: MISSING_PREVIOUS_SESSION symbol={symbol}")
        if prior.get("trade_date") != expected_previous_trade_date:
            raise ContractGateError(
                "PIT_PREV_CLOSE_CONTINUITY_FAILED: UNEXPECTED_PREVIOUS_SESSION "
                f"symbol={symbol} expected={expected_previous_trade_date} observed={prior.get('trade_date')}"
            )
        observed = by_symbol[symbol].get("quote", {}).get("normalized", {}).get("prev_close")
        if observed is None:
            raise ContractGateError(f"PIT_PREV_CLOSE_CONTINUITY_FAILED: MISSING_MANIFEST_PREV_CLOSE symbol={symbol}")
        expected = float(prior["close"])
        observed = float(observed)
        if observed != expected:
            raise ContractGateError(
                "PIT_PREV_CLOSE_CONTINUITY_FAILED: PREV_CLOSE_MISMATCH "
                f"symbol={symbol} expected_prev_close={expected} manifest_prev_close={observed}"
            )
        checked.append({"symbol": symbol, "previous_trade_date": prior.get("trade_date"),
                        "expected_prev_close": expected, "manifest_prev_close": observed})
    return {"status": "PASS", "matched": 13, "required": 13, "symbols": checked}


def feature_window_dates(anchor, exchange_trading_dates, *, required_sessions):
    try:
        date.fromisoformat(anchor)
        for trading_date in exchange_trading_dates:
            date.fromisoformat(trading_date)
    except Exception as exc:
        raise ContractGateError("FEATURE_WINDOW_CALENDAR_DATE_INVALID") from exc
    if not isinstance(required_sessions, int) or required_sessions < 1:
        raise ContractGateError("FEATURE_WINDOW_REQUIRED_SESSIONS_INVALID")
    if exchange_trading_dates != sorted(set(exchange_trading_dates)):
        raise ContractGateError("FEATURE_WINDOW_CALENDAR_NOT_SORTED_UNIQUE")
    try:
        anchor_index = exchange_trading_dates.index(anchor)
    except ValueError as exc:
        raise ContractGateError("FEATURE_WINDOW_ANCHOR_NOT_IN_EXCHANGE_CALENDAR") from exc
    start_index = anchor_index - required_sessions + 1
    if start_index < 0:
        raise ContractGateError("FEATURE_WINDOW_CALENDAR_HISTORY_INSUFFICIENT")
    return exchange_trading_dates[start_index:anchor_index + 1]


def validate_feature_window_continuity(symbol, expected_dates, observed_dates):
    expected = list(expected_dates)
    observed = list(observed_dates)
    if not expected or expected != sorted(set(expected)):
        raise ContractGateError(f"FEATURE_WINDOW_CONTINUITY_FAILED: INVALID_EXPECTED_SESSIONS symbol={symbol}")
    if len(observed) != len(set(observed)):
        raise ContractGateError(f"FEATURE_WINDOW_CONTINUITY_FAILED: DUPLICATE_OBSERVED_SESSIONS symbol={symbol}")
    missing = [d for d in expected if d not in set(observed)]
    extra = [d for d in observed if d not in set(expected)]
    if missing or extra or observed != expected:
        reason = ("MISSING_EXCHANGE_SESSIONS" if missing else
                  "EXTRA_OBSERVED_SESSIONS" if extra else "EXCHANGE_SESSION_ORDER_MISMATCH")
        raise ContractGateError(
            f"FEATURE_WINDOW_CONTINUITY_FAILED: {reason} symbol={symbol} "
            f"missing={missing} extra={extra} observed_order_matches={observed == expected}"
        )
    return {"status": "PASS", "symbol": symbol, "sessions": len(expected),
            "start_date": expected[0], "end_date": expected[-1]}


def load_exchange_trading_calendar(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != "agent-brain-cn-exchange-calendar/v1":
        raise ContractGateError("EXCHANGE_CALENDAR_SCHEMA_INVALID")
    dates = data.get("trading_days")
    if not isinstance(dates, list) or not dates:
        raise ContractGateError("EXCHANGE_CALENDAR_DATES_INVALID")
    if len(dates) != len(set(dates)) or dates != sorted(dates):
        raise ContractGateError("EXCHANGE_CALENDAR_DATES_NOT_SORTED_UNIQUE")
    try:
        parsed = [date.fromisoformat(x) for x in dates]
    except Exception as exc:
        raise ContractGateError("EXCHANGE_CALENDAR_DATE_FORMAT_INVALID") from exc
    if any(d.weekday() >= 5 for d in parsed):
        raise ContractGateError("EXCHANGE_CALENDAR_CONTAINS_WEEKEND")
    if data.get("trading_day_count") != len(dates):
        raise ContractGateError("EXCHANGE_CALENDAR_COUNT_MISMATCH")
    return dates


def historical_bar_available_by_cutoff(ingested_at, decision_cutoff):
    """A historical lookback bar is usable only if persisted by the decision cutoff."""
    def parse(value):
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ContractGateError("LOOKBACK_CUTOFF_TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
        return value.astimezone(timezone.utc)
    return parse(ingested_at) <= parse(decision_cutoff)
