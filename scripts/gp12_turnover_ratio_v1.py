from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import pathlib
import time
from zoneinfo import ZoneInfo


ARTIFACT_SHARD = "GP12_TURNOVER_RATIO_SHARD_V1"
ARTIFACT_REPAIR_SHARD = "GP12_TURNOVER_RATIO_REPAIR_SHARD_V1"
ARTIFACT_AUDIT = "GP12_TURNOVER_RATIO_FULL_AUDIT_V1"
ARTIFACT_REPAIR_AUDIT = "GP12_TURNOVER_RATIO_REPAIR_AUDIT_V1"
VERSION = "1.0"
FORMAL_START = "2020-06-01"
FORMAL_END = "2026-04-17"
UNIVERSE_N = 847
FORMAL_SYMBOL_N = 844
EXPECTED_TRADE_ROWS = 1_011_607
NA_SYMBOLS = ["600074.SH", "600485.SH", "600677.SH"]
SHANGHAI = ZoneInfo("Asia/Shanghai")
KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
EASTMONEY_UT = "7eea3edcaed734bea9cbfc24409ed989"


def canonical_json_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def symbol_to_secid(symbol: str) -> str:
    code, exchange = normalize_symbol(symbol).split(".")
    return f"{'0' if exchange == 'SZ' else '1'}.{code}"


def close_known_at(date_value: str) -> dt.datetime:
    day = dt.date.fromisoformat(date_value)
    return dt.datetime.combine(day, dt.time(15, 0), tzinfo=SHANGHAI)


def _finite(value: object, label: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(out):
        raise ValueError(f"{label} must be finite")
    return out


def parse_turnover_payload(symbol: str, payload: object) -> tuple[list[dict], dict]:
    symbol = normalize_symbol(symbol)
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise ValueError("Eastmoney turnover payload has no data object")
    data = payload["data"]
    klines = data.get("klines")
    if not isinstance(klines, list):
        raise ValueError("Eastmoney turnover payload has no klines list")
    if not klines:
        raise ValueError("Eastmoney turnover payload has no historical klines")

    rows: list[dict] = []
    for index, line in enumerate(klines):
        if not isinstance(line, str):
            raise ValueError(f"turnover row {index} is not text")
        parts = line.split(",")
        if len(parts) < 11:
            raise ValueError(f"turnover row {index} has fewer than 11 fields")
        date_value = parts[0].strip()[:10]
        dt.date.fromisoformat(date_value)
        turnover_pct = _finite(parts[10], f"turnover row {index} f61")
        rows.append({"date": date_value, "turnover_ratio": turnover_pct / 100.0})

    meta = {
        "provider": "Eastmoney",
        "secid": symbol_to_secid(symbol),
        "payload_code": str(data.get("code", "")),
        "payload_name": str(data.get("name", "")),
        "field": "f61",
        "source_unit": "percent",
        "candidate_unit": "decimal_ratio",
        "klt": 101,
        "fqt": 0,
        "historical_provider_publication_timestamp_proven": False,
    }
    return rows, meta


def audit_symbol_rows(symbol: str, expected_dates: list[str], rows: list[dict]) -> dict:
    symbol = normalize_symbol(symbol)
    blockers: list[str] = []
    observed_dates: list[str] = []
    invalid_value = False
    invalid_date = False
    for row in rows:
        date_value = str(row.get("date", "")).strip()
        try:
            dt.date.fromisoformat(date_value)
        except ValueError:
            invalid_date = True
        observed_dates.append(date_value)
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
    coverage_exact = not any(b in blockers for b in (
        "TURNOVER_INVALID_DATE", "TURNOVER_DUPLICATE_DATE", "TURNOVER_DATE_ORDER_INVALID",
        "TURNOVER_DATE_GAP", "TURNOVER_EXTRA_DATE",
    ))
    pit_policy_valid = not invalid_date
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
        "pit_policy_valid": pit_policy_valid,
        "pit_scope": "SESSION_CLOSE_NO_LOOKAHEAD_POLICY",
        "known_at_first": close_known_at(first).isoformat() if first and not invalid_date else None,
        "known_at_last": close_known_at(last).isoformat() if last and not invalid_date else None,
        "same_session_turnover_usable_before_close": False,
        "historical_provider_publication_timestamp_proven": False,
        "symbol_pass": not blockers,
        "blockers": blockers,
    }


def summarize_formal_audit(records: list[dict], *, universe_n: int, na_symbols: list[str], expected_trade_rows: int) -> dict:
    blockers: list[str] = []
    symbols = [str(record.get("symbol", "")) for record in records]
    if len(symbols) != len(set(symbols)):
        _append_once(blockers, "TURNOVER_DUPLICATE_SYMBOL")
    if universe_n != UNIVERSE_N:
        _append_once(blockers, "TURNOVER_UNIVERSE_IDENTITY_MISMATCH")
    if na_symbols != NA_SYMBOLS:
        _append_once(blockers, "TURNOVER_NA_PARTITION_MISMATCH")
    if len(records) != FORMAL_SYMBOL_N:
        _append_once(blockers, "TURNOVER_FORMAL_SYMBOL_COVERAGE_INCOMPLETE")
    pass_n = sum(record.get("symbol_pass") is True for record in records)
    fail_n = len(records) - pass_n
    if pass_n != FORMAL_SYMBOL_N or fail_n != 0:
        _append_once(blockers, "TURNOVER_SYMBOL_AUDIT_FAILURES")
    observed_rows = sum(int(record.get("row_n") or 0) for record in records)
    if observed_rows != expected_trade_rows:
        _append_once(blockers, "TURNOVER_TOTAL_ROW_COVERAGE_MISMATCH")
    return {
        "artifact": ARTIFACT_AUDIT,
        "version": VERSION,
        "formal_window": [FORMAL_START, FORMAL_END],
        "universe_n": universe_n,
        "formal_symbol_n": len(records),
        "na_symbols": list(na_symbols),
        "pass_n": pass_n,
        "fail_n": fail_n,
        "expected_trade_rows": expected_trade_rows,
        "observed_turnover_rows": observed_rows,
        "field": "f61",
        "source_unit": "percent",
        "candidate_unit": "decimal_ratio",
        "pit_scope": "SESSION_CLOSE_NO_LOOKAHEAD_POLICY",
        "same_session_turnover_usable_before_close": False,
        "historical_provider_publication_timestamp_proven": False,
        "turnover_ratio_candidate_pit_verified": not blockers,
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
        "blockers": blockers,
    }


def merge_repair_records(base_records: list[dict], repair_records: list[dict]) -> dict:
    base_symbols = [str(record.get("symbol", "")) for record in base_records]
    if len(base_symbols) != len(set(base_symbols)):
        raise ValueError("duplicate base symbol")
    base_map = {str(record["symbol"]): record for record in base_records}
    repair_symbols = [str(record.get("symbol", "")) for record in repair_records]
    if len(repair_symbols) != len(set(repair_symbols)):
        raise ValueError("duplicate repair symbol")
    unknown = sorted(set(repair_symbols) - set(base_map))
    if unknown:
        raise ValueError(f"unknown repair symbol: {unknown[0]}")
    repair_map = {str(record["symbol"]): record for record in repair_records}
    merged: list[dict] = []
    repaired_n = 0
    protected_pass_n = 0
    for symbol in base_symbols:
        base = base_map[symbol]
        retry = repair_map.get(symbol)
        if base.get("symbol_pass") is True:
            merged.append(base)
            protected_pass_n += 1
        elif retry is not None and retry.get("symbol_pass") is True:
            merged.append(retry)
            repaired_n += 1
        elif retry is not None:
            merged.append(retry)
        else:
            merged.append(base)
    unresolved = sorted(str(record["symbol"]) for record in merged if record.get("symbol_pass") is not True)
    return {
        "records": merged,
        "repaired_n": repaired_n,
        "protected_pass_n": protected_pass_n,
        "unresolved_symbols": unresolved,
    }


def _get_json(url: str, params: dict, timeout: int) -> object:
    import requests
    response = requests.get(
        url,
        params=params,
        headers={
            "User-Agent": "Mozilla/5.0 GP12-Turnover-Ratio-V1",
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://quote.eastmoney.com/",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def fetch_turnover(symbol: str, *, timeout: int = 20, retries: int = 5) -> tuple[list[dict], dict]:
    symbol = normalize_symbol(symbol)
    params = {
        "secid": symbol_to_secid(symbol), "klt": "101", "fqt": "0",
        "beg": FORMAL_START.replace("-", ""), "end": FORMAL_END.replace("-", ""),
        "lmt": "1000000", "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "ut": EASTMONEY_UT, "rtntype": "6",
    }
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            rows, meta = parse_turnover_payload(symbol, _get_json(KLINE_URL, params, timeout))
            meta["endpoint"] = KLINE_URL
            meta["request_attempt"] = attempt + 1
            expected_code = symbol.split(".", 1)[0]
            if meta["payload_code"] != expected_code:
                raise RuntimeError(f"payload code mismatch for {symbol}: {meta['payload_code']!r}")
            return rows, meta
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(min(4.0, 0.75 * (2 ** attempt)))
    raise RuntimeError(f"turnover fetch failed for {symbol} after {retries} attempts: {last_error}") from last_error


def _load_scope(path: pathlib.Path) -> list[str]:
    values = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    normalized = [normalize_symbol(value) for value in values]
    if len(normalized) != UNIVERSE_N or len(set(normalized)) != UNIVERSE_N:
        raise ValueError("Formal847 scope identity mismatch")
    for symbol in NA_SYMBOLS:
        if symbol not in normalized:
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


def _failure_record(symbol: str, expected_dates: list[str], exc: Exception) -> dict:
    return {
        "symbol": symbol,
        "expected_row_n": len(expected_dates), "row_n": 0,
        "first": None, "last": None,
        "missing_date_n": len(expected_dates), "extra_date_n": 0,
        "missing_dates_sample": expected_dates[:20], "extra_dates_sample": [],
        "coverage_exact": False, "pit_policy_valid": False,
        "pit_scope": "SESSION_CLOSE_NO_LOOKAHEAD_POLICY",
        "known_at_first": None, "known_at_last": None,
        "same_session_turnover_usable_before_close": False,
        "historical_provider_publication_timestamp_proven": False,
        "symbol_pass": False,
        "blockers": ["TURNOVER_SOURCE_FETCH_FAILED"],
        "source_error": f"{type(exc).__name__}: {exc}",
    }


def _materialized_rows(symbol: str, rows: list[dict], source: dict) -> list[dict]:
    return [{
        "symbol": symbol,
        "date": row["date"],
        "turnover_ratio": row["turnover_ratio"],
        "known_at": close_known_at(row["date"]).isoformat(),
        "source": "EASTMONEY_F61_FQT0",
        "source_endpoint": source.get("endpoint"),
    } for row in rows]


def write_turnover_csv(path: pathlib.Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["symbol", "date", "turnover_ratio", "known_at", "source", "source_endpoint"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _run_symbols(symbols: list[str], raw_parquet: pathlib.Path, *, artifact: str, shard_index: int, shard_count: int, timeout: int, retries: int, inter_symbol_delay: float) -> tuple[dict, list[dict]]:
    expected = _load_expected_dates(raw_parquet, symbols)
    records: list[dict] = []
    materialized: list[dict] = []
    for symbol in symbols:
        expected_dates = expected.get(symbol, [])
        try:
            rows, source = fetch_turnover(symbol, timeout=timeout, retries=retries)
            audited = audit_symbol_rows(symbol, expected_dates, rows)
            audited["source"] = source
            if audited["symbol_pass"]:
                materialized.extend(_materialized_rows(symbol, rows, source))
        except Exception as exc:
            audited = _failure_record(symbol, expected_dates, exc)
        records.append(audited)
        if inter_symbol_delay > 0:
            time.sleep(inter_symbol_delay)
    failures = [record for record in records if not record["symbol_pass"]]
    report = {
        "artifact": artifact, "version": VERSION,
        "formal_window": [FORMAL_START, FORMAL_END],
        "shard_index": shard_index, "shard_count": shard_count,
        "symbol_n": len(records), "pass_n": len(records) - len(failures), "fail_n": len(failures),
        "expected_trade_rows": sum(int(record["expected_row_n"]) for record in records),
        "observed_turnover_rows": sum(int(record["row_n"]) for record in records),
        "materialized_rows": len(materialized), "records": records,
        "model_freeze_allowed": False, "oos_metrics_allowed": False,
    }
    return report, materialized


def run_shard(scope_path: pathlib.Path, raw_parquet: pathlib.Path, *, shard_index: int, shard_count: int, timeout: int, retries: int = 5, inter_symbol_delay: float = 0.1) -> tuple[dict, list[dict]]:
    if shard_count < 1 or shard_index < 0 or shard_index >= shard_count:
        raise ValueError("invalid shard coordinates")
    scope = _load_scope(scope_path)
    formal_symbols = [symbol for symbol in scope if symbol not in NA_SYMBOLS]
    shard_symbols = [symbol for index, symbol in enumerate(formal_symbols) if index % shard_count == shard_index]
    return _run_symbols(shard_symbols, raw_parquet, artifact=ARTIFACT_SHARD, shard_index=shard_index, shard_count=shard_count, timeout=timeout, retries=retries, inter_symbol_delay=inter_symbol_delay)


def run_repair_shard(base_audit: dict, raw_parquet: pathlib.Path, *, shard_index: int, shard_count: int, timeout: int, retries: int, inter_symbol_delay: float) -> tuple[dict, list[dict]]:
    if base_audit.get("artifact") != ARTIFACT_AUDIT:
        raise ValueError("repair base audit identity mismatch")
    base_records = base_audit.get("records")
    if not isinstance(base_records, list) or len(base_records) != FORMAL_SYMBOL_N:
        raise ValueError("repair base audit record coverage mismatch")
    unresolved = [str(record["symbol"]) for record in base_records if record.get("symbol_pass") is not True]
    shard_symbols = [symbol for index, symbol in enumerate(unresolved) if index % shard_count == shard_index]
    report, materialized = _run_symbols(shard_symbols, raw_parquet, artifact=ARTIFACT_REPAIR_SHARD, shard_index=shard_index, shard_count=shard_count, timeout=timeout, retries=retries, inter_symbol_delay=inter_symbol_delay)
    report["base_audit_sha256"] = canonical_json_sha256(base_audit)
    report["base_pass_n"] = sum(record.get("symbol_pass") is True for record in base_records)
    report["base_unresolved_n"] = len(unresolved)
    return report, materialized


def amount_evidence() -> dict:
    return {
        "provider": "Sohu RAW / frozen liquidity lineage",
        "raw_artifact_id": 10042614517,
        "raw_artifact_zip_sha256": "cee7e91f1fda605f7c3bdf41c3f4a7796feeae83f8c3702e50900e6af3fa9550",
        "liquidity_artifact_id": 10042615093,
        "liquidity_artifact_zip_sha256": "a041d50ab2c9bbbe5f129d9afae87e817de0b1d8073c86cf829427f031bbc37b",
        "raw_trade_rows": EXPECTED_TRADE_ROWS,
        "bad_amount_rows": 0,
    }


def aggregate_shards(shard_reports: list[dict]) -> dict:
    records: list[dict] = []
    for report in shard_reports:
        if report.get("artifact") != ARTIFACT_SHARD or report.get("version") != VERSION:
            raise ValueError("turnover shard identity mismatch")
        records.extend(report.get("records") or [])
    out = summarize_formal_audit(records, universe_n=UNIVERSE_N, na_symbols=NA_SYMBOLS, expected_trade_rows=EXPECTED_TRADE_ROWS)
    out["records"] = records
    out["source"] = {"provider": "Eastmoney", "endpoint": KLINE_URL, "field": "f61", "klt": 101, "fqt": 0, "series": "historical_daily_turnover_ratio"}
    out["amount_evidence"] = amount_evidence()
    return out


def aggregate_repair(base_audit: dict, repair_reports: list[dict], repair_data_paths: list[pathlib.Path]) -> tuple[dict, list[dict]]:
    if base_audit.get("artifact") != ARTIFACT_AUDIT:
        raise ValueError("repair base audit identity mismatch")
    base_records = base_audit.get("records")
    if not isinstance(base_records, list) or len(base_records) != FORMAL_SYMBOL_N:
        raise ValueError("repair base audit record coverage mismatch")
    repair_records: list[dict] = []
    base_sha = canonical_json_sha256(base_audit)
    for report in repair_reports:
        if report.get("artifact") != ARTIFACT_REPAIR_SHARD or report.get("version") != VERSION:
            raise ValueError("repair shard identity mismatch")
        if report.get("base_audit_sha256") != base_sha:
            raise ValueError("repair shard base hash mismatch")
        repair_records.extend(report.get("records") or [])
    merged = merge_repair_records(base_records, repair_records)
    summary = summarize_formal_audit(merged["records"], universe_n=UNIVERSE_N, na_symbols=NA_SYMBOLS, expected_trade_rows=EXPECTED_TRADE_ROWS)
    materialized: list[dict] = []
    for path in repair_data_paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8", newline="") as handle:
            materialized.extend(dict(row) for row in csv.DictReader(handle))
    materialized_symbols = sorted({row["symbol"] for row in materialized})
    out = {
        **summary,
        "artifact": ARTIFACT_REPAIR_AUDIT,
        "base_artifact": ARTIFACT_AUDIT,
        "base_audit_sha256": base_sha,
        "base_pass_n": sum(record.get("symbol_pass") is True for record in base_records),
        "base_fail_n": sum(record.get("symbol_pass") is not True for record in base_records),
        "repair_attempted_n": len(repair_records),
        "repair_recovered_n": merged["repaired_n"],
        "unresolved_symbol_n": len(merged["unresolved_symbols"]),
        "unresolved_symbols": merged["unresolved_symbols"],
        "materialized_repair_symbol_n": len(materialized_symbols),
        "materialized_repair_rows": len(materialized),
        "materialized_repair_symbols": materialized_symbols,
        "panel_complete": False,
        "records": merged["records"],
        "source": {"provider": "Eastmoney", "endpoint": KLINE_URL, "field": "f61", "klt": 101, "fqt": 0, "series": "historical_daily_turnover_ratio"},
        "amount_evidence": amount_evidence(),
    }
    out["audit_exact_after_repair"] = not summary["blockers"]
    out["turnover_ratio_candidate_pit_verified"] = False
    _append_once(out["blockers"], "TURNOVER_PANEL_NOT_MATERIALIZED")
    return out, materialized


def _load_json(path: pathlib.Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="GP12 candidate turnover-ratio evidence audit")
    sub = parser.add_subparsers(dest="command", required=True)
    shard = sub.add_parser("shard")
    shard.add_argument("--scope", required=True); shard.add_argument("--raw-parquet", required=True)
    shard.add_argument("--shard-index", type=int, required=True); shard.add_argument("--shard-count", type=int, required=True)
    shard.add_argument("--timeout", type=int, default=20); shard.add_argument("--retries", type=int, default=5)
    shard.add_argument("--inter-symbol-delay", type=float, default=0.1); shard.add_argument("--out", required=True); shard.add_argument("--data-out")
    aggregate = sub.add_parser("aggregate")
    aggregate.add_argument("--shard-dir", required=True); aggregate.add_argument("--out", required=True)
    repair = sub.add_parser("repair-shard")
    repair.add_argument("--base-audit", required=True); repair.add_argument("--raw-parquet", required=True)
    repair.add_argument("--shard-index", type=int, required=True); repair.add_argument("--shard-count", type=int, required=True)
    repair.add_argument("--timeout", type=int, default=20); repair.add_argument("--retries", type=int, default=5)
    repair.add_argument("--inter-symbol-delay", type=float, default=0.4); repair.add_argument("--out", required=True); repair.add_argument("--data-out", required=True)
    repair_aggregate = sub.add_parser("repair-aggregate")
    repair_aggregate.add_argument("--base-audit", required=True); repair_aggregate.add_argument("--repair-dir", required=True)
    repair_aggregate.add_argument("--out", required=True); repair_aggregate.add_argument("--data-out", required=True)
    args = parser.parse_args()

    if args.command == "shard":
        report, materialized = run_shard(pathlib.Path(args.scope), pathlib.Path(args.raw_parquet), shard_index=args.shard_index, shard_count=args.shard_count, timeout=args.timeout, retries=args.retries, inter_symbol_delay=args.inter_symbol_delay)
        if args.data_out:
            write_turnover_csv(pathlib.Path(args.data_out), materialized)
        rc = 0 if report["fail_n"] == 0 else 2
    elif args.command == "aggregate":
        paths = sorted(pathlib.Path(args.shard_dir).rglob("TURNOVER_SHARD_*.json"))
        if not paths:
            raise ValueError("no turnover shard reports found")
        report = aggregate_shards([_load_json(path) for path in paths])
        rc = 0 if report["turnover_ratio_candidate_pit_verified"] else 2
    elif args.command == "repair-shard":
        report, materialized = run_repair_shard(_load_json(pathlib.Path(args.base_audit)), pathlib.Path(args.raw_parquet), shard_index=args.shard_index, shard_count=args.shard_count, timeout=args.timeout, retries=args.retries, inter_symbol_delay=args.inter_symbol_delay)
        write_turnover_csv(pathlib.Path(args.data_out), materialized)
        rc = 0 if report["fail_n"] == 0 else 2
    else:
        repair_dir = pathlib.Path(args.repair_dir)
        report_paths = sorted(repair_dir.rglob("TURNOVER_REPAIR_SHARD_*.json"))
        data_paths = sorted(repair_dir.rglob("TURNOVER_REPAIR_SHARD_*.csv"))
        if not report_paths:
            raise ValueError("no turnover repair shard reports found")
        report, materialized = aggregate_repair(_load_json(pathlib.Path(args.base_audit)), [_load_json(path) for path in report_paths], data_paths)
        write_turnover_csv(pathlib.Path(args.data_out), materialized)
        report["materialized_repair_csv"] = pathlib.Path(args.data_out).name
        report["materialized_repair_csv_sha256"] = sha256_file(pathlib.Path(args.data_out))
        rc = 0 if report["audit_exact_after_repair"] else 2

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    summary = {key: report.get(key) for key in (
        "artifact", "shard_index", "shard_count", "symbol_n", "formal_symbol_n", "pass_n", "fail_n",
        "repair_recovered_n", "unresolved_symbol_n", "expected_trade_rows", "observed_turnover_rows",
        "materialized_rows", "materialized_repair_rows", "audit_exact_after_repair",
        "turnover_ratio_candidate_pit_verified", "blockers",
    ) if key in report}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
