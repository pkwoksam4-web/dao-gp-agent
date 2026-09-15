from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import pathlib
from zoneinfo import ZoneInfo


STRATEGY_ID = "GP12_REBUILD_CANDIDATE_V1"
FORMAL_START = "2020-06-01"
FORMAL_END = "2026-04-17"
SUPPORTED_PARAMETERS_SHA256 = "22f054d0068c2c1d7bed3c17e586eca1b22d7b3888547de36e6e754578ceb204"
SUPPORTED_FACTORS_SHA256 = "b52f394fb13417e6f0323f7175a50a7d950dba8af09f63a97e739c6a4c70160e"
FROZEN_CALENDAR_LEGACY_SHA256 = "0bfa32175dfccbd24d30eb7ceb0605f6cde2ed0bcc31ac2cac61479ba812add0"
FROZEN_CALENDAR_N = 1426
SHANGHAI = ZoneInfo("Asia/Shanghai")
EASTMONEY_BASE = "https://push2his.eastmoney.com/api/qt/stock/kline/get"


def canonical_json_bytes(obj: object) -> bytes:
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_json_sha256(obj: object) -> str:
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


def _append_once(blockers: list[str], value: str) -> None:
    if value not in blockers:
        blockers.append(value)


def validate_binding(binding: dict, factors: dict, parameters: dict) -> dict:
    blockers: list[str] = []
    benchmark = binding.get("benchmark") if isinstance(binding, dict) else None
    formal = binding.get("formal_window") if isinstance(binding, dict) else None
    pit = binding.get("pit_policy") if isinstance(binding, dict) else None
    pins = binding.get("pins") if isinstance(binding, dict) else None
    claims = binding.get("claims") if isinstance(binding, dict) else None

    if binding.get("artifact") != "GP12_CANDIDATE_BENCHMARK_BINDING_V1":
        _append_once(blockers, "BINDING_ARTIFACT_INVALID")
    if binding.get("strategy_id") != STRATEGY_ID:
        _append_once(blockers, "BINDING_STRATEGY_ID_INVALID")
    if binding.get("status") != "CANDIDATE_ONLY_UNAPPROVED":
        _append_once(blockers, "BINDING_STATUS_NOT_CANDIDATE_ONLY")
    if binding.get("definition_origin") != "NEW_RECONSTRUCTION_CANDIDATE":
        _append_once(blockers, "BINDING_ORIGIN_INVALID")

    if not isinstance(benchmark, dict):
        _append_once(blockers, "BENCHMARK_BINDING_MISSING")
        benchmark = {}
    if benchmark.get("name") != "CSI All Share":
        _append_once(blockers, "BENCHMARK_NAME_INVALID")
    if benchmark.get("code") != "000985":
        _append_once(blockers, "BENCHMARK_CODE_INVALID")
    if benchmark.get("eastmoney_secid") != "1.000985":
        _append_once(blockers, "BENCHMARK_SECID_INVALID")
    if benchmark.get("series") != "daily_close":
        _append_once(blockers, "BENCHMARK_SERIES_INVALID")

    if formal != {"start": FORMAL_START, "end": FORMAL_END}:
        _append_once(blockers, "FORMAL_WINDOW_INVALID")

    if not isinstance(pit, dict):
        _append_once(blockers, "PIT_POLICY_MISSING")
        pit = {}
    if pit.get("timezone") != "Asia/Shanghai":
        _append_once(blockers, "PIT_TIMEZONE_INVALID")
    if pit.get("session_close") != "15:00:00":
        _append_once(blockers, "PIT_SESSION_CLOSE_INVALID")
    if pit.get("same_session_close_usable_before_close") is not False:
        _append_once(blockers, "PIT_PRE_CLOSE_USE_NOT_FORBIDDEN")

    factor_sha = canonical_json_sha256(factors)
    parameter_sha = canonical_json_sha256(parameters)
    if factor_sha != SUPPORTED_FACTORS_SHA256:
        _append_once(blockers, "FACTORS_HASH_DRIFT")
    if parameter_sha != SUPPORTED_PARAMETERS_SHA256:
        _append_once(blockers, "PARAMETERS_HASH_DRIFT")

    if not isinstance(pins, dict):
        _append_once(blockers, "BINDING_PINS_MISSING")
        pins = {}
    if pins.get("factors_sha256") != SUPPORTED_FACTORS_SHA256:
        _append_once(blockers, "BINDING_FACTORS_PIN_MISMATCH")
    if pins.get("parameters_sha256") != SUPPORTED_PARAMETERS_SHA256:
        _append_once(blockers, "BINDING_PARAMETERS_PIN_MISMATCH")
    if pins.get("frozen_calendar_legacy_sha256") != FROZEN_CALENDAR_LEGACY_SHA256:
        _append_once(blockers, "BINDING_CALENDAR_PIN_MISMATCH")
    if pins.get("frozen_calendar_n") != FROZEN_CALENDAR_N:
        _append_once(blockers, "BINDING_CALENDAR_COUNT_MISMATCH")

    if not isinstance(claims, dict):
        _append_once(blockers, "BINDING_CLAIMS_MISSING")
        claims = {}
    if claims.get("gp_v11_benchmark_recovered") is not False:
        _append_once(blockers, "HISTORICAL_RECOVERY_CLAIM_FORBIDDEN")
    if claims.get("historical_recovery_claim_allowed") is not False:
        _append_once(blockers, "HISTORICAL_RECOVERY_CLAIM_FORBIDDEN")

    return {
        "candidate_binding_valid": not blockers,
        "factors_sha256": factor_sha,
        "parameters_sha256": parameter_sha,
        "binding_sha256": canonical_json_sha256(binding),
        "gp_v11_benchmark_recovered": False,
        "historical_recovery_claim_allowed": False,
        "blockers": blockers,
    }


def close_known_at(date_value: str, binding: dict) -> dt.datetime:
    day = dt.date.fromisoformat(date_value)
    policy = binding["pit_policy"]
    zone = ZoneInfo(policy["timezone"])
    close_time = dt.time.fromisoformat(policy["session_close"])
    return dt.datetime.combine(day, close_time, tzinfo=zone)


def close_available_at(date_value: str, as_of: dt.datetime, binding: dict) -> bool:
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    known_at = close_known_at(date_value, binding)
    return as_of.astimezone(known_at.tzinfo) >= known_at


def validate_close_series(rows: list[dict], expected_dates: list[str], binding: dict) -> dict:
    blockers: list[str] = []
    dates: list[str] = []
    invalid_date = False
    invalid_close = False

    for row in rows:
        value = str(row.get("date", "")).strip()
        try:
            dt.date.fromisoformat(value)
        except ValueError:
            invalid_date = True
        dates.append(value)
        try:
            close = float(row.get("close"))
            if not math.isfinite(close) or close <= 0:
                invalid_close = True
        except (TypeError, ValueError):
            invalid_close = True

    if invalid_date:
        _append_once(blockers, "BENCHMARK_INVALID_DATE")
    if invalid_close:
        _append_once(blockers, "BENCHMARK_INVALID_CLOSE")
    if len(dates) != len(set(dates)):
        _append_once(blockers, "BENCHMARK_DUPLICATE_DATE")
    if dates != sorted(dates):
        _append_once(blockers, "BENCHMARK_DATE_ORDER_INVALID")

    expected_set = set(expected_dates)
    observed_set = set(dates)
    missing = sorted(expected_set - observed_set)
    extra = sorted(observed_set - expected_set)
    if missing:
        _append_once(blockers, "BENCHMARK_CALENDAR_GAP")
    if extra:
        _append_once(blockers, "BENCHMARK_OUT_OF_CALENDAR_DATE")

    policy = binding.get("pit_policy", {})
    pit_policy_valid = (
        policy.get("timezone") == "Asia/Shanghai"
        and policy.get("session_close") == "15:00:00"
        and policy.get("same_session_close_usable_before_close") is False
        and not invalid_date
    )
    if not pit_policy_valid:
        _append_once(blockers, "BENCHMARK_PIT_POLICY_INVALID")

    calendar_full = not any(
        b in blockers
        for b in (
            "BENCHMARK_INVALID_DATE",
            "BENCHMARK_INVALID_CLOSE",
            "BENCHMARK_DUPLICATE_DATE",
            "BENCHMARK_DATE_ORDER_INVALID",
            "BENCHMARK_CALENDAR_GAP",
            "BENCHMARK_OUT_OF_CALENDAR_DATE",
        )
    )
    first = dates[0] if dates else None
    last = dates[-1] if dates else None
    return {
        "row_n": len(rows),
        "first": first,
        "last": last,
        "missing_dates": missing,
        "extra_dates": extra,
        "calendar_full_coverage": calendar_full,
        "pit_policy_valid": pit_policy_valid,
        "known_at_first": close_known_at(first, binding).isoformat() if first and not invalid_date else None,
        "known_at_last": close_known_at(last, binding).isoformat() if last and not invalid_date else None,
        "pit_scope": "SESSION_CLOSE_NO_LOOKAHEAD_POLICY",
        "historical_provider_publication_timestamp_proven": False,
        "candidate_benchmark_blocker_closed": not blockers,
        "blockers": blockers,
    }


def verify_frozen_calendar_csv(csv_text: str) -> dict:
    reader = csv.DictReader(csv_text.lstrip("\ufeff").splitlines())
    fields = list(reader.fieldnames or [])
    date_field = "trade_date" if "trade_date" in fields else ("date" if "date" in fields else None)
    if date_field is None:
        raise ValueError("calendar CSV missing date field")
    dates = [str(row.get(date_field, "")).strip() for row in reader]
    if any(not value for value in dates):
        raise ValueError("calendar has blank date")
    try:
        for value in dates:
            dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("calendar has invalid date") from exc
    if dates != sorted(dates) or len(set(dates)) != len(dates):
        raise ValueError("calendar dates not strictly increasing")
    if len(dates) != FROZEN_CALENDAR_N:
        raise ValueError(f"calendar count mismatch: {len(dates)} != {FROZEN_CALENDAR_N}")
    if dates[0] != FORMAL_START or dates[-1] != FORMAL_END:
        raise ValueError(f"calendar bounds mismatch: {dates[:1]}..{dates[-1:]}")
    legacy_payload = "".join(value + "\n" for value in dates).encode("ascii")
    legacy_sha = hashlib.sha256(legacy_payload).hexdigest()
    if legacy_sha != FROZEN_CALENDAR_LEGACY_SHA256:
        raise ValueError(f"calendar legacy hash mismatch: {legacy_sha}")
    semantic_sha = hashlib.sha256("\n".join(dates).encode("ascii")).hexdigest()
    return {
        "dates": dates,
        "expected_n": len(dates),
        "first": dates[0],
        "last": dates[-1],
        "legacy_sha256": legacy_sha,
        "semantic_sha256": semantic_sha,
    }


def fetch_benchmark_close(binding: dict, timeout: int = 30) -> tuple[list[dict], dict]:
    import requests

    benchmark = binding["benchmark"]
    window = binding["formal_window"]
    params = {
        "secid": benchmark["eastmoney_secid"],
        "klt": "101",
        "fqt": "0",
        "beg": window["start"].replace("-", ""),
        "end": window["end"].replace("-", ""),
        "lmt": "1000000",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
    }
    response = requests.get(
        EASTMONEY_BASE,
        params=params,
        headers={"User-Agent": "Mozilla/5.0 GP12-Candidate-Benchmark-V1"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise RuntimeError("Eastmoney benchmark payload has no data object")
    klines = data.get("klines")
    if not isinstance(klines, list) or not klines:
        raise RuntimeError("Eastmoney benchmark payload has no daily klines")

    rows: list[dict] = []
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 3:
            continue
        try:
            rows.append({"date": parts[0], "close": float(parts[2])})
        except (TypeError, ValueError):
            rows.append({"date": parts[0] if parts else "", "close": None})

    meta = {
        "provider": "Eastmoney",
        "endpoint": EASTMONEY_BASE,
        "secid": benchmark["eastmoney_secid"],
        "payload_code": str(data.get("code", "")),
        "payload_name": str(data.get("name", "")),
        "klt": 101,
        "fqt": 0,
        "series_construction": benchmark.get("series_construction"),
    }
    return rows, meta


def write_close_csv(path: pathlib.Path, rows: list[dict], binding: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "close", "known_at", "source"])
        writer.writeheader()
        for row in rows:
            date_value = str(row.get("date", ""))
            try:
                known_at = close_known_at(date_value, binding).isoformat()
            except ValueError:
                known_at = ""
            writer.writerow(
                {
                    "date": date_value,
                    "close": row.get("close"),
                    "known_at": known_at,
                    "source": "EASTMONEY_INDEX_OWN_DAILY_CLOSE_FQT0",
                }
            )


def _load_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_validation(
    binding_path: pathlib.Path,
    factors_path: pathlib.Path,
    parameters_path: pathlib.Path,
    calendar_csv_path: pathlib.Path,
    out_dir: pathlib.Path,
    timeout: int = 30,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    binding = _load_json(binding_path)
    factors = _load_json(factors_path)
    parameters = _load_json(parameters_path)
    binding_check = validate_binding(binding, factors, parameters)
    blockers = list(binding_check["blockers"])

    calendar: dict = {
        "expected_n": FROZEN_CALENDAR_N,
        "observed_n": None,
        "first": None,
        "last": None,
        "legacy_sha256": None,
        "semantic_sha256": None,
        "full_coverage": False,
    }
    expected_dates: list[str] = []
    try:
        verified = verify_frozen_calendar_csv(calendar_csv_path.read_text(encoding="utf-8"))
        expected_dates = verified.pop("dates")
        calendar.update(verified)
    except Exception as exc:
        _append_once(blockers, "FROZEN_CALENDAR_VERIFICATION_FAILED")
        calendar["error"] = f"{type(exc).__name__}: {exc}"

    rows: list[dict] = []
    source: dict = {
        "provider": "Eastmoney",
        "secid": binding.get("benchmark", {}).get("eastmoney_secid"),
        "identity_valid": False,
    }
    try:
        rows, source = fetch_benchmark_close(binding, timeout=timeout)
        source["identity_valid"] = (
            source.get("secid") == "1.000985" and source.get("payload_code") == "000985"
        )
        if not source["identity_valid"]:
            _append_once(blockers, "BENCHMARK_SOURCE_IDENTITY_MISMATCH")
    except Exception as exc:
        _append_once(blockers, "BENCHMARK_SOURCE_FETCH_FAILED")
        source["error"] = f"{type(exc).__name__}: {exc}"

    series_check = validate_close_series(rows, expected_dates, binding) if expected_dates else {
        "row_n": len(rows),
        "first": None,
        "last": None,
        "missing_dates": [],
        "extra_dates": [],
        "calendar_full_coverage": False,
        "pit_policy_valid": False,
        "known_at_first": None,
        "known_at_last": None,
        "pit_scope": "SESSION_CLOSE_NO_LOOKAHEAD_POLICY",
        "historical_provider_publication_timestamp_proven": False,
        "candidate_benchmark_blocker_closed": False,
        "blockers": ["FROZEN_CALENDAR_UNAVAILABLE_FOR_SERIES_CHECK"],
    }
    for blocker in series_check["blockers"]:
        _append_once(blockers, blocker)

    calendar["observed_n"] = series_check["row_n"]
    calendar["first"] = series_check["first"] or calendar.get("first")
    calendar["last"] = series_check["last"] or calendar.get("last")
    calendar["full_coverage"] = series_check["calendar_full_coverage"]

    close_csv = out_dir / "CSI_ALL_SHARE_000985_DAILY_CLOSE_20200601_20260417.csv"
    if rows:
        write_close_csv(close_csv, rows, binding)

    candidate_closed = not blockers
    report = {
        "artifact": "GP12_CANDIDATE_BENCHMARK_VALIDATION_V1",
        "status": "PASS_CANDIDATE_BENCHMARK_V1" if candidate_closed else "BLOCKED_CANDIDATE_BENCHMARK_V1",
        "strategy_id": STRATEGY_ID,
        "binding_status": binding.get("status"),
        "definition_origin": binding.get("definition_origin"),
        "benchmark": binding.get("benchmark"),
        "formal_window": [FORMAL_START, FORMAL_END],
        "binding_sha256": binding_check["binding_sha256"],
        "factors_sha256": binding_check["factors_sha256"],
        "parameters_sha256": binding_check["parameters_sha256"],
        "factors_parameters_hashes_unchanged": (
            binding_check["factors_sha256"] == SUPPORTED_FACTORS_SHA256
            and binding_check["parameters_sha256"] == SUPPORTED_PARAMETERS_SHA256
        ),
        "calendar": calendar,
        "pit": {
            "policy_valid": series_check["pit_policy_valid"],
            "scope": series_check["pit_scope"],
            "known_at_first": series_check["known_at_first"],
            "known_at_last": series_check["known_at_last"],
            "same_session_close_usable_before_close": False,
            "historical_provider_publication_timestamp_proven": False,
            "note": "PIT result proves the candidate no-lookahead session-close policy; it does not claim archival proof of provider publication timestamps.",
        },
        "source": source,
        "close_series_sha256": canonical_json_sha256(rows) if rows else None,
        "close_csv": close_csv.name if rows else None,
        "candidate_benchmark_blocker_closed": candidate_closed,
        "gp_v11_benchmark_recovered": False,
        "historical_recovery_claim_allowed": False,
        "blockers": blockers,
    }
    report_path = out_dir / "GP12_CANDIDATE_BENCHMARK_VALIDATION_V1.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", required=True)
    parser.add_argument("--factors", required=True)
    parser.add_argument("--parameters", required=True)
    parser.add_argument("--calendar-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    report = run_validation(
        pathlib.Path(args.binding),
        pathlib.Path(args.factors),
        pathlib.Path(args.parameters),
        pathlib.Path(args.calendar_csv),
        pathlib.Path(args.out_dir),
        timeout=args.timeout,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["candidate_benchmark_blocker_closed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
