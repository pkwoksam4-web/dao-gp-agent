from __future__ import annotations

import csv
import datetime as dt
import math
import pathlib
import time
from zoneinfo import ZoneInfo


FORMAL_START = "2020-06-01"
FORMAL_END = "2026-04-17"
UNIVERSE_N = 847
FORMAL_SYMBOL_N = 844
EXPECTED_TRADE_ROWS = 1_011_607
NA_SYMBOLS = ("600074.SH", "600485.SH", "600677.SH")
VERSION = "1.0"
ARTIFACT_SHARD = "GP12_MAIN_NET_FLOW_SHARD_V1"
ARTIFACT_FULL = "GP12_MAIN_NET_FLOW_FULL_AUDIT_V1"
SOURCE = "TUSHARE_MONEYFLOW_LG_ELG_ACTIVE_BUY_MINUS_SELL"
SHANGHAI = ZoneInfo("Asia/Shanghai")
MONEYFLOW_FIELDS = (
    "ts_code",
    "trade_date",
    "buy_sm_vol",
    "buy_sm_amount",
    "sell_sm_vol",
    "sell_sm_amount",
    "buy_md_vol",
    "buy_md_amount",
    "sell_md_vol",
    "sell_md_amount",
    "buy_lg_vol",
    "buy_lg_amount",
    "sell_lg_vol",
    "sell_lg_amount",
    "buy_elg_vol",
    "buy_elg_amount",
    "sell_elg_vol",
    "sell_elg_amount",
    "net_mf_vol",
    "net_mf_amount",
)
PANEL_FIELDS = (
    "symbol",
    "date",
    "main_net_flow_cny",
    "known_at",
    "source",
)


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


def formal_symbols_from_scope(scope: list[str]) -> list[str]:
    normalized = [normalize_symbol(symbol) for symbol in scope]
    if len(normalized) != UNIVERSE_N or len(set(normalized)) != UNIVERSE_N:
        raise ValueError("Formal847 scope identity mismatch")
    if any(symbol not in normalized for symbol in NA_SYMBOLS):
        raise ValueError("Formal N/A partition not present in scope")
    formal = [symbol for symbol in normalized if symbol not in NA_SYMBOLS]
    if len(formal) != FORMAL_SYMBOL_N:
        raise ValueError("Formal844 scope partition mismatch")
    return formal


def load_scope(path: pathlib.Path | str) -> list[str]:
    values = [
        line.strip()
        for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return formal_symbols_from_scope(values)


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


def _trade_date_to_api(value: object) -> str:
    return _trade_date_to_iso(value).replace("-", "")


def close_known_at(date_value: str) -> str:
    day = dt.date.fromisoformat(date_value)
    return dt.datetime.combine(day, dt.time(15, 0), tzinfo=SHANGHAI).isoformat()


def expected_dates_from_records(records: list[dict], symbols: list[str]) -> dict[str, list[str]]:
    normalized_symbols = [normalize_symbol(symbol) for symbol in symbols]
    if len(normalized_symbols) != len(set(normalized_symbols)):
        raise ValueError("RAW expected-date symbol list contains duplicates")
    target = set(normalized_symbols)
    result = {symbol: [] for symbol in normalized_symbols}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"RAW row {index} must be an object")
        symbol = normalize_symbol(record.get("symbol", ""))
        if symbol not in target:
            continue
        amount = _finite_nonnegative(record.get("amount"), f"RAW row {index} amount")
        if amount <= 0:
            raise ValueError("RAW amount evidence has nonpositive or missing values")
        result[symbol].append(_trade_date_to_iso(record.get("date", "")))
    for symbol, dates in result.items():
        if not dates:
            raise ValueError(f"RAW expected-date coverage missing for {symbol}")
        if dates != sorted(dates) or len(dates) != len(set(dates)):
            raise ValueError(f"RAW date order invalid for {symbol}")
    return result


def load_expected_dates(raw_parquet: pathlib.Path | str, symbols: list[str]) -> dict[str, list[str]]:
    import pandas as pd

    frame = pd.read_parquet(raw_parquet, columns=["symbol", "date", "amount"])
    return expected_dates_from_records(frame.to_dict("records"), symbols)


def fetch_moneyflow_records(
    api: object,
    symbol: str,
    *,
    start_date: str = FORMAL_START,
    end_date: str = FORMAL_END,
) -> list[dict]:
    symbol = normalize_symbol(symbol)
    frame = api.moneyflow(
        ts_code=symbol,
        start_date=_trade_date_to_api(start_date),
        end_date=_trade_date_to_api(end_date),
        fields=",".join(MONEYFLOW_FIELDS),
    )
    to_dict = getattr(frame, "to_dict", None)
    if not callable(to_dict):
        raise ValueError("Tushare moneyflow response does not support to_dict")
    records = to_dict("records")
    if not isinstance(records, list):
        raise ValueError("Tushare moneyflow response did not produce a records list")
    return records


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


def build_symbol_evidence(
    api: object,
    symbol: str,
    expected_dates: list[str],
    *,
    start_date: str = FORMAL_START,
    end_date: str = FORMAL_END,
) -> dict:
    raw_records = fetch_moneyflow_records(
        api,
        symbol,
        start_date=start_date,
        end_date=end_date,
    )
    rows = normalize_moneyflow_records(symbol, raw_records)
    return {
        "rows": rows,
        "audit": audit_symbol_rows(symbol, expected_dates, rows),
    }


def _source_failure_record(symbol: str, expected_dates: list[str], exc: Exception) -> dict:
    return {
        "symbol": normalize_symbol(symbol),
        "expected_row_n": len(expected_dates),
        "row_n": 0,
        "first": None,
        "last": None,
        "missing_date_n": len(expected_dates),
        "extra_date_n": 0,
        "missing_dates_sample": expected_dates[:20],
        "extra_dates_sample": [],
        "coverage_exact": False,
        "pit_policy_valid": False,
        "pit_scope": "SESSION_CLOSE_NO_LOOKAHEAD_POLICY",
        "same_session_main_net_flow_usable_before_close": False,
        "historical_provider_publication_timestamp_proven": False,
        "symbol_pass": False,
        "blockers": ["MAIN_NET_FLOW_SOURCE_FETCH_FAILED"],
        "source_error": f"{type(exc).__name__}: {exc}",
    }


def run_shard(
    api: object,
    formal_symbols: list[str],
    expected_dates: dict[str, list[str]],
    *,
    shard_index: int,
    shard_count: int,
    inter_symbol_delay: float = 0.5,
) -> tuple[dict, list[dict]]:
    if shard_count < 1 or shard_index < 0 or shard_index >= shard_count:
        raise ValueError("invalid shard coordinates")
    symbols = [normalize_symbol(symbol) for symbol in formal_symbols]
    if len(symbols) != len(set(symbols)):
        raise ValueError("formal symbol list contains duplicates")
    shard_symbols = [
        symbol for index, symbol in enumerate(symbols)
        if index % shard_count == shard_index
    ]
    records: list[dict] = []
    materialized: list[dict] = []
    for symbol in shard_symbols:
        dates = expected_dates.get(symbol)
        if not dates:
            raise ValueError(f"expected-date axis missing for {symbol}")
        try:
            evidence = build_symbol_evidence(api, symbol, dates)
            audited = evidence["audit"]
            if audited["symbol_pass"]:
                materialized.extend(evidence["rows"])
        except Exception as exc:
            audited = _source_failure_record(symbol, dates, exc)
        records.append(audited)
        if inter_symbol_delay > 0:
            time.sleep(inter_symbol_delay)
    failures = [record for record in records if record.get("symbol_pass") is not True]
    report = {
        "artifact": ARTIFACT_SHARD,
        "version": VERSION,
        "formal_window": [FORMAL_START, FORMAL_END],
        "shard_index": shard_index,
        "shard_count": shard_count,
        "symbol_n": len(records),
        "pass_n": len(records) - len(failures),
        "fail_n": len(failures),
        "expected_trade_rows": sum(int(record["expected_row_n"]) for record in records),
        "observed_main_net_flow_rows": sum(int(record["row_n"]) for record in records),
        "materialized_rows": len(materialized),
        "source": SOURCE,
        "records": records,
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
    }
    return report, materialized


def write_panel_csv(path: pathlib.Path | str, rows: list[dict]) -> pathlib.Path:
    destination = pathlib.Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda row: (str(row.get("symbol", "")), str(row.get("date", ""))))
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(PANEL_FIELDS), lineterminator="\n")
        writer.writeheader()
        for row in ordered:
            writer.writerow({field: row.get(field) for field in PANEL_FIELDS})
    return destination


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
        "artifact": ARTIFACT_FULL,
        "version": VERSION,
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


def aggregate_shard_records(shards: list[list[dict]]) -> dict:
    records = [record for shard in shards for record in shard]
    symbols = [str(record.get("symbol", "")) for record in records]
    if len(symbols) != len(set(symbols)):
        raise ValueError("duplicate shard symbol")
    return {
        "records": records,
        "audit": summarize_formal_audit(records),
    }


def aggregate_shard_reports(reports: list[dict]) -> dict:
    if not reports:
        raise ValueError("shard partition incomplete")
    shard_counts = {int(report.get("shard_count", -1)) for report in reports}
    if len(shard_counts) != 1:
        raise ValueError("shard count mismatch")
    shard_count = shard_counts.pop()
    indices = [int(report.get("shard_index", -1)) for report in reports]
    if sorted(indices) != list(range(shard_count)) or len(indices) != len(set(indices)):
        raise ValueError("shard partition incomplete")
    for report in reports:
        if report.get("artifact") != ARTIFACT_SHARD or report.get("version") != VERSION:
            raise ValueError("main net flow shard identity mismatch")
    records = [record for report in reports for record in (report.get("records") or [])]
    merged = aggregate_shard_records([records])
    out = merged["audit"]
    out["records"] = merged["records"]
    out["shard_count"] = shard_count
    out["materialized_rows"] = sum(int(report.get("materialized_rows") or 0) for report in reports)
    return out
