from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import pathlib
from zoneinfo import ZoneInfo


ARTIFACT_SHARD = "GP12_BAOSTOCK_TURNOVER_SHARD_V1"
ARTIFACT_AUDIT = "GP12_BAOSTOCK_TURNOVER_FULL_AUDIT_V1"
VERSION = "1.0"
FORMAL_START = "2020-06-01"
FORMAL_END = "2026-04-17"
UNIVERSE_N = 847
FORMAL_SYMBOL_N = 844
EXPECTED_TRADE_ROWS = 1_011_607
NA_SYMBOLS = ["600074.SH", "600485.SH", "600677.SH"]
SOURCE_ID = "BAOSTOCK_TURN_DAILY_UNADJUSTED"
RESIDUAL_SOURCE_ID = "BAOSTOCK_TURN_RESIDUAL_DENOMINATOR_RECONSTRUCTION"
BAOSTOCK_QUERY_FIELDS = "date,code,volume,amount,turn,tradestatus"
RESIDUAL_BINDING_ARTIFACT = "GP12_CANDIDATE_TURNOVER_RESIDUAL_DENOMINATORS_V1"
RESIDUAL_PRECISION_PERCENTAGE_POINTS = 0.0001
RESIDUAL_EXPECTED = {
    "300216.SZ": {
        "coverage_start": "2020-08-05",
        "coverage_end": "2020-09-15",
        "floating_shares": 291_684_518,
        "source_publication_date": "2020-06-30",
        "source_url": "https://static.cninfo.com.cn/finalpage/2020-06-30/1207967627.PDF",
    },
    "002604.SZ": {
        "coverage_start": "2020-06-01",
        "coverage_end": "2020-07-14",
        "floating_shares": 512_281_847,
        "source_publication_date": "2020-04-29",
        "source_url": "https://static.cninfo.com.cn/finalpage/2020-04-29/1207665018.PDF",
    },
}
SHANGHAI = ZoneInfo("Asia/Shanghai")


def _append_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def normalize_symbol(symbol: str) -> str:
    value = str(symbol).strip().upper()
    if "." not in value:
        raise ValueError(f"exchange-qualified symbol required: {symbol!r}")
    code, exchange = value.split(".", 1)
    if len(code) != 6 or not code.isdigit() or exchange not in {"SZ", "SH"}:
        raise ValueError(f"unsupported symbol: {symbol!r}")
    return f"{code}.{exchange}"


def symbol_to_baostock_code(symbol: str) -> str:
    code, exchange = normalize_symbol(symbol).split(".")
    return f"{'sz' if exchange == 'SZ' else 'sh'}.{code}"


def close_known_at(date_value: str) -> dt.datetime:
    day = dt.date.fromisoformat(date_value)
    return dt.datetime.combine(day, dt.time(15, 0), tzinfo=SHANGHAI)


def _positive_finite(value: object, label: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(out) or out <= 0:
        raise ValueError(f"{label} must be positive and finite")
    return out


def _positive_finite_or_none(value: object) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out) or out <= 0:
        return None
    return out


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def provider_metadata() -> dict:
    return {
        "provider": "BaoStock",
        "field": "turn",
        "query_fields": BAOSTOCK_QUERY_FIELDS,
        "source_unit": "percent",
        "candidate_unit": "decimal_ratio",
        "frequency": "d",
        "adjustflag": "3",
        "series": "historical_daily_turnover_ratio",
        "origin": "NEW_RECONSTRUCTION_CANDIDATE",
        "status": "CANDIDATE_ONLY_UNAPPROVED",
        "status_override_rule": (
            "tradestatus=0 may be retained only when volume, amount, and turn "
            "are all strictly positive finite values"
        ),
        "precision_zero_reconstruction_rule": (
            "tradestatus=1 and source turn=0 may be reconstructed only from a "
            "PIT-bound exact floating-share denominator after positive-turn "
            "neighbors reproduce the source within half a 0.0001 percentage-point unit"
        ),
        "historical_gp_v11_source_recovered": False,
        "historical_provider_publication_timestamp_proven": False,
    }


def _validate_residual_entry(entry: dict, *, expected_symbol: str | None = None) -> dict:
    if not isinstance(entry, dict):
        raise ValueError("residual denominator entry must be an object")
    symbol = normalize_symbol(entry.get("symbol", ""))
    if expected_symbol is not None and symbol != normalize_symbol(expected_symbol):
        raise ValueError("residual denominator symbol mismatch")
    start = str(entry.get("coverage_start", ""))
    end = str(entry.get("coverage_end", ""))
    publication = str(entry.get("source_publication_date", ""))
    start_date = dt.date.fromisoformat(start)
    end_date = dt.date.fromisoformat(end)
    publication_date = dt.date.fromisoformat(publication)
    if start_date > end_date:
        raise ValueError("residual denominator coverage window invalid")
    if publication_date >= start_date:
        raise ValueError("residual denominator is not PIT-public before coverage")
    shares = entry.get("floating_shares")
    if isinstance(shares, bool) or not isinstance(shares, int) or shares <= 0:
        raise ValueError("residual floating_shares must be a positive integer")
    return entry


def validate_residual_denominator_binding(binding: dict) -> dict[str, dict]:
    if not isinstance(binding, dict):
        raise ValueError("residual denominator binding must be an object")
    if binding.get("artifact") != RESIDUAL_BINDING_ARTIFACT:
        raise ValueError("residual denominator artifact mismatch")
    if binding.get("version") != "1.0":
        raise ValueError("residual denominator version mismatch")
    if binding.get("strategy_id") != "GP12_REBUILD_CANDIDATE_V1":
        raise ValueError("residual denominator strategy mismatch")
    if binding.get("status") != "CANDIDATE_ONLY_UNAPPROVED":
        raise ValueError("residual denominator status mismatch")
    if binding.get("origin") != "NEW_RECONSTRUCTION_CANDIDATE":
        raise ValueError("residual denominator origin mismatch")
    if float(binding.get("source_turn_precision_percentage_points")) != RESIDUAL_PRECISION_PERCENTAGE_POINTS:
        raise ValueError("residual source precision mismatch")
    if binding.get("historical_gp_v11_source_recovered") is not False:
        raise ValueError("residual binding cannot claim GP V1.1 recovery")
    if binding.get("model_freeze_allowed") is not False or binding.get("oos_metrics_allowed") is not False:
        raise ValueError("residual binding cannot open freeze/OOS gates")

    entries = binding.get("entries")
    if not isinstance(entries, list):
        raise ValueError("residual denominator entries must be a list")
    index: dict[str, dict] = {}
    for entry in entries:
        checked = _validate_residual_entry(entry)
        symbol = checked["symbol"]
        if symbol in index:
            raise ValueError("duplicate residual denominator symbol")
        index[symbol] = checked
    if set(index) != set(RESIDUAL_EXPECTED):
        raise ValueError("residual denominator scope mismatch")
    for symbol, expected in RESIDUAL_EXPECTED.items():
        entry = index[symbol]
        for key, value in expected.items():
            if entry.get(key) != value:
                raise ValueError(f"residual denominator identity mismatch for {symbol}: {key}")
        if entry.get("pit_before_coverage") is not True:
            raise ValueError(f"residual denominator PIT flag missing for {symbol}")
    return index


def _entry_applies(symbol: str, date_value: str, entry: dict) -> dict:
    entry = _validate_residual_entry(entry, expected_symbol=symbol)
    date = dt.date.fromisoformat(date_value)
    start = dt.date.fromisoformat(str(entry["coverage_start"]))
    end = dt.date.fromisoformat(str(entry["coverage_end"]))
    if not (start <= date <= end):
        raise ValueError("residual denominator row outside bound coverage window")
    return entry


def validate_residual_precision_neighbors(entry: dict, rows: list[dict]) -> dict:
    entry = _validate_residual_entry(entry)
    symbol = normalize_symbol(entry["symbol"])
    shares = int(entry["floating_shares"])
    start = dt.date.fromisoformat(str(entry["coverage_start"]))
    end = dt.date.fromisoformat(str(entry["coverage_end"]))
    tolerance = RESIDUAL_PRECISION_PERCENTAGE_POINTS / 2.0
    errors: list[dict] = []
    checked_n = 0
    max_error = 0.0
    for row in rows:
        if str(row.get("tradestatus", "")) != "1":
            continue
        date_value = str(row.get("date", ""))[:10]
        try:
            date = dt.date.fromisoformat(date_value)
        except ValueError:
            continue
        if not (start <= date <= end):
            continue
        try:
            turn_percent = float(row.get("turn"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(turn_percent) or turn_percent <= 0:
            continue
        volume = _positive_finite_or_none(row.get("volume"))
        amount = _positive_finite_or_none(row.get("amount"))
        if volume is None or amount is None:
            errors.append({"date": date_value, "reason": "positive neighbor lacks trade evidence"})
            continue
        reconstructed_percent = volume / shares * 100.0
        error = abs(reconstructed_percent - turn_percent)
        checked_n += 1
        max_error = max(max_error, error)
        if error > tolerance + 1e-12:
            errors.append({
                "date": date_value,
                "source_turn_percent": turn_percent,
                "reconstructed_turn_percent": reconstructed_percent,
                "abs_percentage_point_error": error,
            })
    return {
        "symbol": symbol,
        "checked_n": checked_n,
        "max_abs_percentage_point_error": max_error,
        "tolerance_percentage_points": tolerance,
        "valid": checked_n > 0 and not errors,
        "errors": errors,
    }


def parse_baostock_row(
    symbol: str,
    row: dict,
    *,
    residual_denominator: dict | None = None,
) -> dict | None:
    symbol = normalize_symbol(symbol)
    if not isinstance(row, dict):
        raise ValueError("BaoStock row must be an object")

    expected_code = symbol_to_baostock_code(symbol)
    actual_code = str(row.get("code", "")).strip().lower()
    if actual_code != expected_code:
        raise ValueError(f"BaoStock code mismatch for {symbol}: {actual_code!r}")
    date_value = str(row.get("date", "")).strip()[:10]
    dt.date.fromisoformat(date_value)

    status = str(row.get("tradestatus", ""))
    if status == "1":
        try:
            turn_percent = float(row.get("turn"))
        except (TypeError, ValueError) as exc:
            raise ValueError("BaoStock turn must be numeric") from exc
        if not math.isfinite(turn_percent) or turn_percent < 0:
            raise ValueError("BaoStock turn must be nonnegative and finite")
        if turn_percent > 0:
            return {"date": date_value, "turnover_ratio": turn_percent / 100.0}
        if residual_denominator is None:
            raise ValueError("BaoStock turn must be positive and finite")
        entry = _entry_applies(symbol, date_value, residual_denominator)
        volume = _positive_finite(row.get("volume"), "BaoStock volume")
        _positive_finite(row.get("amount"), "BaoStock amount")
        shares = int(entry["floating_shares"])
        turnover_ratio = volume / shares
        true_percent = turnover_ratio * 100.0
        if true_percent >= RESIDUAL_PRECISION_PERCENTAGE_POINTS / 2.0:
            raise ValueError("BaoStock precision zero inconsistent with bound denominator")
        return {
            "date": date_value,
            "turnover_ratio": turnover_ratio,
            "turnover_precision_reconstruction": True,
            "residual_denominator_shares": shares,
            "residual_binding_symbol": symbol,
        }

    if status == "0":
        volume = _positive_finite_or_none(row.get("volume"))
        amount = _positive_finite_or_none(row.get("amount"))
        turn_percent = _positive_finite_or_none(row.get("turn"))
        if volume is not None and amount is not None and turn_percent is not None:
            return {
                "date": date_value,
                "turnover_ratio": turn_percent / 100.0,
                "provider_status_override": True,
            }
    return None


def audit_symbol_rows(symbol: str, expected_dates: list[str], rows: list[dict]) -> dict:
    symbol = normalize_symbol(symbol)
    blockers: list[str] = []
    observed_dates: list[str] = []
    invalid_value = False
    invalid_date = False
    provider_status_override_dates: list[str] = []
    precision_reconstruction_dates: list[str] = []
    precision_reconstruction_denominators: set[int] = set()
    for row in rows:
        date_value = str(row.get("date", "")).strip()
        try:
            dt.date.fromisoformat(date_value)
        except ValueError:
            invalid_date = True
        observed_dates.append(date_value)
        if row.get("provider_status_override") is True:
            provider_status_override_dates.append(date_value)
        if row.get("turnover_precision_reconstruction") is True:
            precision_reconstruction_dates.append(date_value)
            try:
                precision_reconstruction_denominators.add(int(row["residual_denominator_shares"]))
            except (KeyError, TypeError, ValueError):
                invalid_value = True
        try:
            turnover = float(row.get("turnover_ratio"))
            if not math.isfinite(turnover) or turnover <= 0:
                invalid_value = True
        except (TypeError, ValueError):
            invalid_value = True

    if invalid_date:
        _append_once(blockers, "TURNOVER_INVALID_DATE")
    if invalid_value:
        _append_once(blockers, "TURNOVER_INVALID_VALUE")
    if len(observed_dates) != len(set(observed_dates)):
        _append_once(blockers, "TURNOVER_DUPLICATE_DATE")
    if observed_dates != sorted(observed_dates):
        _append_once(blockers, "TURNOVER_DATE_ORDER_INVALID")

    expected_set = set(expected_dates)
    observed_set = set(observed_dates)
    missing = sorted(expected_set - observed_set)
    extra = sorted(observed_set - expected_set)
    if missing:
        _append_once(blockers, "TURNOVER_DATE_GAP")
    if extra:
        _append_once(blockers, "TURNOVER_EXTRA_DATE")

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
        "provider_status_override_n": len(provider_status_override_dates),
        "provider_status_override_dates": provider_status_override_dates,
        "turnover_precision_reconstruction_n": len(precision_reconstruction_dates),
        "turnover_precision_reconstruction_dates": precision_reconstruction_dates,
        "turnover_precision_reconstruction_denominators": sorted(precision_reconstruction_denominators),
        "coverage_exact": not any(
            b in blockers
            for b in (
                "TURNOVER_INVALID_DATE",
                "TURNOVER_DUPLICATE_DATE",
                "TURNOVER_DATE_ORDER_INVALID",
                "TURNOVER_DATE_GAP",
                "TURNOVER_EXTRA_DATE",
            )
        ),
        "pit_policy_valid": not invalid_date,
        "pit_scope": "SESSION_CLOSE_NO_LOOKAHEAD_POLICY",
        "known_at_first": close_known_at(first).isoformat() if first and not invalid_date else None,
        "known_at_last": close_known_at(last).isoformat() if last and not invalid_date else None,
        "same_session_turnover_usable_before_close": False,
        "historical_provider_publication_timestamp_proven": False,
        "symbol_pass": not blockers,
        "blockers": blockers,
    }


def materialize_rows(symbol: str, rows: list[dict]) -> list[dict]:
    symbol = normalize_symbol(symbol)
    result: list[dict] = []
    for row in rows:
        date_value = str(row["date"])
        turnover = _positive_finite(row["turnover_ratio"], "turnover_ratio")
        source = RESIDUAL_SOURCE_ID if row.get("turnover_precision_reconstruction") is True else SOURCE_ID
        result.append(
            {
                "symbol": symbol,
                "date": date_value,
                "turnover_ratio": turnover,
                "known_at": close_known_at(date_value).isoformat(),
                "source": source,
            }
        )
    return result


def summarize_full_audit(
    records: list[dict], *, expected_trade_rows: int, materialized_rows: int
) -> dict:
    blockers: list[str] = []
    symbols = [str(record.get("symbol", "")) for record in records]
    if len(symbols) != len(set(symbols)):
        _append_once(blockers, "TURNOVER_DUPLICATE_SYMBOL")
    if len(records) != FORMAL_SYMBOL_N:
        _append_once(blockers, "TURNOVER_FORMAL_SYMBOL_COVERAGE_INCOMPLETE")
    pass_n = sum(record.get("symbol_pass") is True for record in records)
    fail_n = len(records) - pass_n
    if pass_n != FORMAL_SYMBOL_N or fail_n != 0:
        _append_once(blockers, "TURNOVER_SYMBOL_AUDIT_FAILURES")
    observed_rows = sum(int(record.get("row_n") or 0) for record in records)
    if observed_rows != expected_trade_rows:
        _append_once(blockers, "TURNOVER_TOTAL_ROW_COVERAGE_MISMATCH")
    panel_complete = materialized_rows == expected_trade_rows == observed_rows
    if not panel_complete:
        _append_once(blockers, "TURNOVER_PANEL_ROW_COVERAGE_MISMATCH")
    override_records = [
        {"symbol": str(record.get("symbol")), "dates": list(record.get("provider_status_override_dates") or [])}
        for record in records
        if int(record.get("provider_status_override_n") or 0) > 0
    ]
    reconstruction_records = [
        {
            "symbol": str(record.get("symbol")),
            "dates": list(record.get("turnover_precision_reconstruction_dates") or []),
            "denominators": list(record.get("turnover_precision_reconstruction_denominators") or []),
        }
        for record in records
        if int(record.get("turnover_precision_reconstruction_n") or 0) > 0
    ]
    return {
        "artifact": ARTIFACT_AUDIT,
        "version": VERSION,
        "formal_window": [FORMAL_START, FORMAL_END],
        "universe_n": UNIVERSE_N,
        "formal_symbol_n": len(records),
        "na_symbols": list(NA_SYMBOLS),
        "pass_n": pass_n,
        "fail_n": fail_n,
        "expected_trade_rows": expected_trade_rows,
        "observed_turnover_rows": observed_rows,
        "materialized_rows": materialized_rows,
        "provider_status_override_n": sum(int(record.get("provider_status_override_n") or 0) for record in records),
        "provider_status_override_symbol_n": len(override_records),
        "provider_status_overrides": override_records,
        "turnover_precision_reconstruction_n": sum(int(record.get("turnover_precision_reconstruction_n") or 0) for record in records),
        "turnover_precision_reconstruction_symbol_n": len(reconstruction_records),
        "turnover_precision_reconstructions": reconstruction_records,
        "panel_complete": panel_complete,
        "turnover_ratio_candidate_pit_verified": not blockers,
        "provider": provider_metadata(),
        "same_session_turnover_usable_before_close": False,
        "historical_provider_publication_timestamp_proven": False,
        "historical_gp_v11_source_recovered": False,
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
        "blockers": blockers,
    }


def _load_scope(path: pathlib.Path) -> list[str]:
    values = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    normalized = [normalize_symbol(value) for value in values]
    if len(normalized) != UNIVERSE_N or len(set(normalized)) != UNIVERSE_N:
        raise ValueError("Formal847 scope identity mismatch")
    if any(symbol not in normalized for symbol in NA_SYMBOLS):
        raise ValueError("Formal N/A partition not present in scope")
    return normalized


def _load_expected_dates(raw_parquet: pathlib.Path, symbols: list[str]) -> dict[str, list[str]]:
    import pandas as pd

    frame = pd.read_parquet(raw_parquet, columns=["symbol", "date", "amount"])
    frame = frame[frame["symbol"].isin(symbols)].copy()
    if frame.duplicated(["symbol", "date"]).any():
        raise ValueError("RAW panel has duplicate symbol-date rows")
    if frame["amount"].isna().any() or (frame["amount"] <= 0).any():
        raise ValueError("RAW amount evidence has nonpositive or missing values")
    result: dict[str, list[str]] = {}
    for symbol, part in frame.groupby("symbol", sort=False):
        dates = [str(value)[:10] for value in part["date"].tolist()]
        if dates != sorted(dates) or len(dates) != len(set(dates)):
            raise ValueError(f"RAW date order invalid for {symbol}")
        result[str(symbol)] = dates
    return result


def _query_symbol(bs, symbol: str, residual_denominator: dict | None = None) -> tuple[list[dict], dict]:
    code = symbol_to_baostock_code(symbol)
    rs = bs.query_history_k_data_plus(
        code,
        BAOSTOCK_QUERY_FIELDS,
        start_date=FORMAL_START,
        end_date=FORMAL_END,
        frequency="d",
        adjustflag="3",
    )
    if rs.error_code != "0":
        raise RuntimeError(f"BaoStock query failed for {symbol}: {rs.error_code} {rs.error_msg}")
    raw_rows: list[dict] = []
    while rs.next():
        raw_rows.append(dict(zip(rs.fields, rs.get_row_data())))

    precision_validation = None
    if residual_denominator is not None:
        precision_validation = validate_residual_precision_neighbors(residual_denominator, raw_rows)
        if not precision_validation["valid"]:
            raise RuntimeError(f"residual denominator precision validation failed for {symbol}: {precision_validation['errors']}")

    rows: list[dict] = []
    for raw in raw_rows:
        parsed = parse_baostock_row(symbol, raw, residual_denominator=residual_denominator)
        if parsed is not None:
            rows.append(parsed)
    if not rows:
        raise RuntimeError(f"BaoStock returned no active turnover rows for {symbol}")
    source = {"provider": "BaoStock", "code": code, "error_code": rs.error_code}
    if precision_validation is not None:
        source["residual_precision_validation"] = precision_validation
    return rows, source


def run_shard(
    scope_path: pathlib.Path,
    raw_parquet: pathlib.Path,
    *,
    shard_index: int,
    shard_count: int,
    residual_binding: dict | None = None,
) -> tuple[dict, list[dict]]:
    if shard_count < 1 or shard_index < 0 or shard_index >= shard_count:
        raise ValueError("invalid shard coordinates")
    scope = _load_scope(scope_path)
    formal_symbols = [symbol for symbol in scope if symbol not in NA_SYMBOLS]
    shard_symbols = [symbol for index, symbol in enumerate(formal_symbols) if index % shard_count == shard_index]
    expected = _load_expected_dates(raw_parquet, shard_symbols)
    residual_index = validate_residual_denominator_binding(residual_binding) if residual_binding is not None else {}
    residual_binding_sha = _canonical_json_sha256(residual_binding) if residual_binding is not None else None

    import baostock as bs

    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"BaoStock login failed: {login.error_code} {login.error_msg}")
    records: list[dict] = []
    materialized: list[dict] = []
    try:
        for symbol in shard_symbols:
            expected_dates = expected.get(symbol, [])
            try:
                rows, source = _query_symbol(bs, symbol, residual_index.get(symbol))
                audited = audit_symbol_rows(symbol, expected_dates, rows)
                audited["source"] = source
                if audited["symbol_pass"]:
                    materialized.extend(materialize_rows(symbol, rows))
            except Exception as exc:
                audited = {
                    "symbol": symbol,
                    "expected_row_n": len(expected_dates),
                    "row_n": 0,
                    "first": None,
                    "last": None,
                    "missing_date_n": len(expected_dates),
                    "extra_date_n": 0,
                    "missing_dates_sample": expected_dates[:20],
                    "extra_dates_sample": [],
                    "provider_status_override_n": 0,
                    "provider_status_override_dates": [],
                    "turnover_precision_reconstruction_n": 0,
                    "turnover_precision_reconstruction_dates": [],
                    "turnover_precision_reconstruction_denominators": [],
                    "coverage_exact": False,
                    "pit_policy_valid": False,
                    "pit_scope": "SESSION_CLOSE_NO_LOOKAHEAD_POLICY",
                    "known_at_first": None,
                    "known_at_last": None,
                    "same_session_turnover_usable_before_close": False,
                    "historical_provider_publication_timestamp_proven": False,
                    "symbol_pass": False,
                    "blockers": ["TURNOVER_SOURCE_FETCH_FAILED"],
                    "source_error": f"{type(exc).__name__}: {exc}",
                }
            records.append(audited)
    finally:
        bs.logout()

    failures = [record for record in records if not record["symbol_pass"]]
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
        "observed_turnover_rows": sum(int(record["row_n"]) for record in records),
        "materialized_rows": len(materialized),
        "provider_status_override_n": sum(int(record.get("provider_status_override_n") or 0) for record in records),
        "turnover_precision_reconstruction_n": sum(int(record.get("turnover_precision_reconstruction_n") or 0) for record in records),
        "residual_denominator_binding_artifact": RESIDUAL_BINDING_ARTIFACT if residual_binding is not None else None,
        "residual_denominator_binding_sha256": residual_binding_sha,
        "provider": provider_metadata(),
        "records": records,
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
    }
    return report, materialized


def write_panel(path: pathlib.Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda row: (row["symbol"], row["date"]))
    fields = ["symbol", "date", "turnover_ratio", "known_at", "source"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: pathlib.Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def aggregate_shards(shard_reports: list[dict], panel_paths: list[pathlib.Path]) -> tuple[dict, list[dict]]:
    records: list[dict] = []
    residual_artifacts: set[str] = set()
    residual_hashes: set[str] = set()
    for report in shard_reports:
        if report.get("artifact") != ARTIFACT_SHARD or report.get("version") != VERSION:
            raise ValueError("BaoStock turnover shard identity mismatch")
        if report.get("provider") != provider_metadata():
            raise ValueError("BaoStock provider metadata mismatch")
        artifact = report.get("residual_denominator_binding_artifact")
        digest = report.get("residual_denominator_binding_sha256")
        if artifact:
            residual_artifacts.add(str(artifact))
        if digest:
            residual_hashes.add(str(digest))
        records.extend(report.get("records") or [])
    if len(residual_artifacts) > 1 or len(residual_hashes) > 1:
        raise ValueError("residual denominator binding lineage mismatch across shards")

    panel: list[dict] = []
    for path in panel_paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            panel.extend(dict(row) for row in csv.DictReader(handle))

    panel_keys = [(row.get("symbol"), row.get("date")) for row in panel]
    panel_blockers: list[str] = []
    if len(panel_keys) != len(set(panel_keys)):
        _append_once(panel_blockers, "TURNOVER_PANEL_DUPLICATE_SYMBOL_DATE")
    allowed_sources = {SOURCE_ID, RESIDUAL_SOURCE_ID}
    for row in panel:
        try:
            symbol = normalize_symbol(str(row.get("symbol", "")))
            date_value = str(row.get("date", ""))
            ratio = _positive_finite(row.get("turnover_ratio"), "panel turnover_ratio")
            expected_known_at = close_known_at(date_value).isoformat()
            if row.get("known_at") != expected_known_at or row.get("source") not in allowed_sources:
                raise ValueError("panel provenance/known_at mismatch")
            if not symbol or not ratio:
                raise ValueError("invalid panel row")
        except Exception:
            _append_once(panel_blockers, "TURNOVER_PANEL_INVALID_ROW")
            break

    out = summarize_full_audit(records, expected_trade_rows=EXPECTED_TRADE_ROWS, materialized_rows=len(panel))
    out["residual_denominator_binding_artifact"] = next(iter(residual_artifacts)) if residual_artifacts else None
    out["residual_denominator_binding_sha256"] = next(iter(residual_hashes)) if residual_hashes else None
    for blocker in panel_blockers:
        _append_once(out["blockers"], blocker)
    out["panel_complete"] = not any(blocker.startswith("TURNOVER_PANEL_") for blocker in out["blockers"])
    out["turnover_ratio_candidate_pit_verified"] = not out["blockers"]
    out["records"] = records
    return out, panel


def main() -> int:
    parser = argparse.ArgumentParser(description="GP12 BaoStock candidate turnover-ratio audit")
    sub = parser.add_subparsers(dest="command", required=True)

    shard = sub.add_parser("shard")
    shard.add_argument("--scope", required=True)
    shard.add_argument("--raw-parquet", required=True)
    shard.add_argument("--residual-denominators")
    shard.add_argument("--shard-index", type=int, required=True)
    shard.add_argument("--shard-count", type=int, required=True)
    shard.add_argument("--out", required=True)
    shard.add_argument("--data-out", required=True)

    aggregate = sub.add_parser("aggregate")
    aggregate.add_argument("--shard-dir", required=True)
    aggregate.add_argument("--out", required=True)
    aggregate.add_argument("--data-out", required=True)

    args = parser.parse_args()
    if args.command == "shard":
        residual_binding = _load_json(pathlib.Path(args.residual_denominators)) if args.residual_denominators else None
        report, panel = run_shard(
            pathlib.Path(args.scope),
            pathlib.Path(args.raw_parquet),
            shard_index=args.shard_index,
            shard_count=args.shard_count,
            residual_binding=residual_binding,
        )
        write_panel(pathlib.Path(args.data_out), panel)
        report["materialized_csv"] = pathlib.Path(args.data_out).name
        report["materialized_csv_sha256"] = sha256_file(pathlib.Path(args.data_out))
        rc = 0 if report["fail_n"] == 0 else 2
    else:
        shard_dir = pathlib.Path(args.shard_dir)
        reports = sorted(shard_dir.rglob("BAOSTOCK_TURNOVER_SHARD_*.json"))
        panels = sorted(shard_dir.rglob("BAOSTOCK_TURNOVER_SHARD_*.csv"))
        if not reports or not panels:
            raise ValueError("BaoStock turnover shard reports/panels missing")
        report, panel = aggregate_shards([_load_json(path) for path in reports], panels)
        write_panel(pathlib.Path(args.data_out), panel)
        report["panel_csv"] = pathlib.Path(args.data_out).name
        report["panel_csv_sha256"] = sha256_file(pathlib.Path(args.data_out))
        rc = 0 if report["turnover_ratio_candidate_pit_verified"] else 2

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    summary = {
        key: report.get(key)
        for key in (
            "artifact", "shard_index", "shard_count", "symbol_n", "formal_symbol_n",
            "pass_n", "fail_n", "expected_trade_rows", "observed_turnover_rows",
            "materialized_rows", "provider_status_override_n", "turnover_precision_reconstruction_n",
            "residual_denominator_binding_artifact", "residual_denominator_binding_sha256",
            "panel_complete", "panel_csv_sha256", "turnover_ratio_candidate_pit_verified", "blockers",
        )
        if key in report
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
