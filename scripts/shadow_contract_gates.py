#!/usr/bin/env python3
"""Pure, fail-closed gates for prospective PIT, Shadow and settlement."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

CORE13 = [
    "000636.SZ","002138.SZ","002156.SZ","600392.SH","600487.SH",
    "600522.SH","600667.SH","600703.SH","601991.SH","605358.SH",
    "000977.SZ","000938.SZ","000063.SZ",
]
SHANGHAI = ZoneInfo("Asia/Shanghai")


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
            raise ContractGateError(
                f"PIT_PREV_CLOSE_CONTINUITY_FAILED: MISSING_PREVIOUS_SESSION symbol={symbol}"
            )
        if prior.get("trade_date") != expected_previous_trade_date:
            raise ContractGateError(
                "PIT_PREV_CLOSE_CONTINUITY_FAILED: UNEXPECTED_PREVIOUS_SESSION "
                f"symbol={symbol} expected={expected_previous_trade_date} observed={prior.get('trade_date')}"
            )
        qn = by_symbol[symbol].get("quote", {}).get("normalized", {})
        observed = qn.get("prev_close")
        if observed is None:
            raise ContractGateError(
                f"PIT_PREV_CLOSE_CONTINUITY_FAILED: MISSING_MANIFEST_PREV_CLOSE symbol={symbol}"
            )
        expected = float(prior["close"])
        observed = float(observed)
        if observed != expected:
            raise ContractGateError(
                "PIT_PREV_CLOSE_CONTINUITY_FAILED: PREV_CLOSE_MISMATCH "
                f"symbol={symbol} expected_prev_close={expected} manifest_prev_close={observed}"
            )
        checked.append({
            "symbol": symbol,
            "previous_trade_date": prior.get("trade_date"),
            "expected_prev_close": expected,
            "manifest_prev_close": observed,
        })
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
        raise ContractGateError(
            f"FEATURE_WINDOW_CONTINUITY_FAILED: INVALID_EXPECTED_SESSIONS symbol={symbol}"
        )
    if len(observed) != len(set(observed)):
        raise ContractGateError(
            f"FEATURE_WINDOW_CONTINUITY_FAILED: DUPLICATE_OBSERVED_SESSIONS symbol={symbol}"
        )
    expected_set = set(expected)
    observed_set = set(observed)
    missing = [d for d in expected if d not in observed_set]
    extra = [d for d in observed if d not in expected_set]
    if missing or extra or observed != expected:
        reason = (
            "MISSING_EXCHANGE_SESSIONS" if missing else
            "EXTRA_OBSERVED_SESSIONS" if extra else
            "EXCHANGE_SESSION_ORDER_MISMATCH"
        )
        raise ContractGateError(
            f"FEATURE_WINDOW_CONTINUITY_FAILED: {reason} "
            f"symbol={symbol} missing={missing} extra={extra} observed_order_matches={observed == expected}"
        )
    return {"status": "PASS", "symbol": symbol, "sessions": len(expected),
            "start_date": expected[0], "end_date": expected[-1]}


def source_is_live_pit(metadata):
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            return False
    return bool(
        isinstance(metadata, dict)
        and metadata.get("mode") == "LIVE_PIT"
        and metadata.get("live_shadow_eligible") is True
    )


def maturity_targets(eligible_dates):
    dates = sorted(set(eligible_dates))
    return {
        "eligible_future_sessions": len(dates),
        "5d": dates[4] if len(dates) >= 5 else None,
        "20d": dates[19] if len(dates) >= 20 else None,
    }


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


def maturity_targets_from_exchange_calendar(anchor, exchange_trading_dates):
    try:
        date.fromisoformat(anchor)
    except Exception as exc:
        raise ContractGateError("EXCHANGE_CALENDAR_ANCHOR_INVALID") from exc
    dates = sorted(set(exchange_trading_dates))
    try:
        for d in dates:
            date.fromisoformat(d)
    except Exception as exc:
        raise ContractGateError("EXCHANGE_CALENDAR_DATE_FORMAT_INVALID") from exc
    future = [d for d in dates if d > anchor]
    targets = maturity_targets(future)
    targets["calendar_anchor"] = anchor
    targets["calendar_last_session"] = dates[-1] if dates else None
    return targets


def target_is_due(target, as_of_date):
    try:
        target_date = date.fromisoformat(target)
        observed_date = date.fromisoformat(as_of_date)
    except Exception as exc:
        raise ContractGateError("SETTLEMENT_DUE_DATE_INVALID") from exc
    return target_date <= observed_date


def load_quarantine_registry(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = data.get("quarantined_strategy_ids")
    if data.get("schema") != "agent-brain-prospective-quarantine-registry/v1":
        raise ContractGateError("QUARANTINE_REGISTRY_SCHEMA_INVALID")
    if not isinstance(ids, list) or not all(isinstance(x, str) and x for x in ids):
        raise ContractGateError("QUARANTINE_REGISTRY_IDS_INVALID")
    return frozenset(ids)


def validate_event_order(events):
    required = ["LIVE_PIT_INGEST_PASS", "SHADOW_RANKING_OBSERVATION_PASS",
                "RANKING_ATTESTATION_PASS", "SETTLEMENT_START"]
    pos = []
    for event in required:
        if event not in events:
            raise ContractGateError(f"SETTLEMENT_ORDER_FAILED: MISSING_{event}")
        pos.append(events.index(event))
    if pos != sorted(pos) or len(set(pos)) != len(pos):
        raise ContractGateError("SETTLEMENT_ORDER_FAILED: OUT_OF_ORDER")
    return True


def build_shadow_request(manifest, manifest_sha256, requested_at):
    if requested_at.tzinfo is None:
        raise ContractGateError("SHADOW_REQUEST_TIME_MUST_BE_TIMEZONE_AWARE")
    local = requested_at.astimezone(SHANGHAI)
    if (local.hour, local.minute) < (17, 30):
        raise ContractGateError("SHADOW_REQUEST_BEFORE_1730_ASIA_SHANGHAI")
    trade_date = manifest["trade_date_cn"]
    if local.date().isoformat() != trade_date:
        raise ContractGateError("SHADOW_REQUEST_NOT_SAME_CHINA_DATE")
    if manifest.get("universe_id") != "WAT-core13-observation-v1":
        raise ContractGateError("SHADOW_REQUEST_WRONG_UNIVERSE")
    key_src = f"{trade_date}|{manifest['universe_id']}|{manifest_sha256}"
    key = hashlib.sha256(key_src.encode()).hexdigest()
    return {
        "schema": "agent-brain-shadow-request/v1",
        "trade_date_cn": trade_date,
        "requested_at": requested_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "pit_manifest_path": f"runtime/pit_manifests/{trade_date}.json",
        "modes": ["CORE10_RANKING_ONLY", "CORE13_OBSERVATION_ONLY"],
        "probability_forecast_allowed": False,
        "probability_blocker": "PROBABILITY_V1_6_EXECUTABLE_MISSING",
        "trigger": {
            "source": "LIVE_PIT_INGEST_PASS",
            "manifest_sha256": manifest_sha256,
            "idempotency_key": key,
        },
    }
