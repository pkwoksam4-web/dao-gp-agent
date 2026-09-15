from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import pathlib
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo


ARTIFACT_SHARD = "GP12_TURNOVER_RATIO_SHARD_V1"
ARTIFACT_AUDIT = "GP12_TURNOVER_RATIO_FULL_AUDIT_V1"
VERSION = "1.0"
FORMAL_START = "2020-06-01"
FORMAL_END = "2026-04-17"
UNIVERSE_N = 847
FORMAL_SYMBOL_N = 844
EXPECTED_TRADE_ROWS = 1_011_607
NA_SYMBOLS = ["600074.SH", "600485.SH", "600677.SH"]
SHANGHAI = ZoneInfo("Asia/Shanghai")
KLINE_URLS = (
    "https://push2his.eastmoney.com/api/qt/stock/kline/get",
    "https://push2.eastmoney.com/api/qt/stock/kline/get",
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
        rows.append({
            "date": date_value,
            "turnover_ratio": turnover_pct / 100.0,
        })

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

    coverage_exact = not any(
        b in blockers for b in (
            "TURNOVER_INVALID_DATE",
            "TURNOVER_DUPLICATE_DATE",
            "TURNOVER_DATE_ORDER_INVALID",
            "TURNOVER_DATE_GAP",
            "TURNOVER_EXTRA_DATE",
        )
    )
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


def summarize_formal_audit(
    records: list[dict],
    *,
    universe_n: int,
    na_symbols: list[str],
    expected_trade_rows: int,
) -> dict:
    blockers: list[str] = []
    symbols = [str(r.get("symbol", "")) for r in records]
    if len(symbols) != len(set(symbols)):
        _append_once(blockers, "TURNOVER_DUPLICATE_SYMBOL")
    if universe_n != UNIVERSE_N:
        _append_once(blockers, "TURNOVER_UNIVERSE_IDENTITY_MISMATCH")
    if na_symbols != NA_SYMBOLS:
        _append_once(blockers, "TURNOVER_NA_PARTITION_MISMATCH")
    if len(records) != FORMAL_SYMBOL_N:
        _append_once(blockers, "TURNOVER_FORMAL_SYMBOL_COVERAGE_INCOMPLETE")

    pass_n = sum(r.get("symbol_pass") is True for r in records)
    fail_n = len(records) - pass_n
    if pass_n != FORMAL_SYMBOL_N or fail_n != 0:
        _append_once(blockers, "TURNOVER_SYMBOL_AUDIT_FAILURES")

    observed_rows = sum(int(r.get("row_n") or 0) for r in records)
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


def _get_json(url: str, params: dict, timeout: int) -> object:
    request = urllib.request.Request(
        f"{url}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": "Mozilla/5.0 GP12-Turnover-Ratio-V1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_turnover(symbol: str, *, timeout: int = 20, retries: int = 3) -> tuple[list[dict], dict]:
    symbol = normalize_symbol(symbol)
    params = {
        "secid": symbol_to_secid(symbol),
        "klt": "101",
        "fqt": "0",
        "beg": FORMAL_START.replace("-", ""),
        "end": FORMAL_END.replace("-", ""),
        "lmt": "1000000",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
    }
    last_error: Exception | None = None
    for attempt in range(retries):
        for url in KLINE_URLS:
            try:
                rows, meta = parse_turnover_payload(symbol, _get_json(url, params, timeout))
                meta["endpoint"] = url
                expected_code = symbol.split(".", 1)[0]
                if meta["payload_code"] != expected_code:
                    raise RuntimeError(
                        f"payload code mismatch for {symbol}: {meta['payload_code']!r}"
                    )
                return rows, meta
            except Exception as exc:
                last_error = exc
        if attempt + 1 < retries:
            time.sleep(0.25 * (attempt + 1))
    raise RuntimeError(f"turnover fetch failed for {symbol}: {last_error}") from last_error


def _load_scope(path: pathlib.Path) -> list[str]:
    values = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    normalized = [normalize_symbol(v) for v in values]
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
        dates = [str(v)[:10] for v in part["date"].tolist()]
        if dates != sorted(dates) or len(dates) != len(set(dates)):
            raise ValueError(f"RAW date order invalid for {symbol}")
        result[str(symbol)] = dates
    return result


def run_shard(
    scope_path: pathlib.Path,
    raw_parquet: pathlib.Path,
    *,
    shard_index: int,
    shard_count: int,
    timeout: int,
) -> dict:
    if shard_count < 1 or shard_index < 0 or shard_index >= shard_count:
        raise ValueError("invalid shard coordinates")
    scope = _load_scope(scope_path)
    formal_symbols = [s for s in scope if s not in NA_SYMBOLS]
    shard_symbols = [s for i, s in enumerate(formal_symbols) if i % shard_count == shard_index]
    expected = _load_expected_dates(raw_parquet, shard_symbols)
    records: list[dict] = []
    for symbol in shard_symbols:
        expected_dates = expected.get(symbol, [])
        try:
            rows, source = fetch_turnover(symbol, timeout=timeout)
            audited = audit_symbol_rows(symbol, expected_dates, rows)
            audited["source"] = source
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

    failures = [r for r in records if not r["symbol_pass"]]
    return {
        "artifact": ARTIFACT_SHARD,
        "version": VERSION,
        "formal_window": [FORMAL_START, FORMAL_END],
        "shard_index": shard_index,
        "shard_count": shard_count,
        "symbol_n": len(records),
        "pass_n": len(records) - len(failures),
        "fail_n": len(failures),
        "expected_trade_rows": sum(int(r["expected_row_n"]) for r in records),
        "observed_turnover_rows": sum(int(r["row_n"]) for r in records),
        "records": records,
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
    }


def aggregate_shards(shard_reports: list[dict]) -> dict:
    records: list[dict] = []
    for report in shard_reports:
        if report.get("artifact") != ARTIFACT_SHARD or report.get("version") != VERSION:
            raise ValueError("turnover shard identity mismatch")
        records.extend(report.get("records") or [])
    out = summarize_formal_audit(
        records,
        universe_n=UNIVERSE_N,
        na_symbols=NA_SYMBOLS,
        expected_trade_rows=EXPECTED_TRADE_ROWS,
    )
    out["records"] = records
    out["source"] = {
        "provider": "Eastmoney",
        "field": "f61",
        "klt": 101,
        "fqt": 0,
        "series": "historical_daily_turnover_ratio",
    }
    out["amount_evidence"] = {
        "provider": "Sohu RAW / frozen liquidity lineage",
        "raw_artifact_id": 10042614517,
        "raw_artifact_zip_sha256": "cee7e91f1fda605f7c3bdf41c3f4a7796feeae83f8c3702e50900e6af3fa9550",
        "liquidity_artifact_id": 10042615093,
        "liquidity_artifact_zip_sha256": "a041d50ab2c9bbbe5f129d9afae87e817de0b1d8073c86cf829427f031bbc37b",
        "raw_trade_rows": EXPECTED_TRADE_ROWS,
        "bad_amount_rows": 0,
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="GP12 candidate turnover-ratio evidence audit")
    sub = parser.add_subparsers(dest="command", required=True)

    shard = sub.add_parser("shard")
    shard.add_argument("--scope", required=True)
    shard.add_argument("--raw-parquet", required=True)
    shard.add_argument("--shard-index", type=int, required=True)
    shard.add_argument("--shard-count", type=int, required=True)
    shard.add_argument("--timeout", type=int, default=20)
    shard.add_argument("--out", required=True)

    aggregate = sub.add_parser("aggregate")
    aggregate.add_argument("--shard-dir", required=True)
    aggregate.add_argument("--out", required=True)

    args = parser.parse_args()
    if args.command == "shard":
        report = run_shard(
            pathlib.Path(args.scope),
            pathlib.Path(args.raw_parquet),
            shard_index=args.shard_index,
            shard_count=args.shard_count,
            timeout=args.timeout,
        )
        rc = 0 if report["fail_n"] == 0 else 2
    else:
        paths = sorted(pathlib.Path(args.shard_dir).rglob("TURNOVER_SHARD_*.json"))
        if not paths:
            raise ValueError("no turnover shard reports found")
        reports = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
        report = aggregate_shards(reports)
        rc = 0 if report["turnover_ratio_candidate_pit_verified"] else 2

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    summary = {k: report.get(k) for k in (
        "artifact", "shard_index", "shard_count", "symbol_n", "formal_symbol_n",
        "pass_n", "fail_n", "expected_trade_rows", "observed_turnover_rows",
        "turnover_ratio_candidate_pit_verified", "blockers",
    ) if k in report}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
