#!/usr/bin/env python3
"""Evidence-only Binance USDⓈ-M funding history capture for BTC Shadow2."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

BASE_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
SYMBOL = "BTCUSDT"
UTC = timezone.utc


def utc_midnight(day: date) -> int:
    return int(datetime.combine(day, time.min, tzinfo=UTC).timestamp() * 1000)


def capture(start: date, end_exclusive: date, out_dir: Path, opener=urlopen) -> dict:
    if end_exclusive <= start:
        raise ValueError("end-exclusive date must be after start date")

    start_ms = utc_midnight(start)
    end_exclusive_ms = utc_midnight(end_exclusive)
    params = {
        "symbol": SYMBOL,
        "startTime": start_ms,
        "endTime": end_exclusive_ms - 1,
        "limit": 1000,
    }
    request_url = f"{BASE_URL}?{urlencode(params)}"
    retrieved_at = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    status = None
    error = None
    raw = b""

    try:
        with opener(request_url, timeout=30) as response:
            status = response.status
            raw = response.read()
    except HTTPError as exc:
        status = exc.code
        raw = exc.read()
        error = f"HTTP_ERROR_{exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        error = f"TRANSPORT_ERROR:{type(exc).__name__}:{exc}"

    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "funding_history_raw.json"
    raw_path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()

    rows = None
    errors = []
    if status != 200:
        errors.append(error or f"HTTP_STATUS_{status}")
    try:
        decoded = json.loads(raw)
        if not isinstance(decoded, list):
            errors.append("RESPONSE_NOT_ARRAY")
        else:
            rows = decoded
    except (UnicodeDecodeError, json.JSONDecodeError):
        errors.append("INVALID_JSON")

    timestamps = []
    if rows is not None:
        if not rows:
            errors.append("EMPTY_RESULT")
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append(f"ROW_{index}_NOT_OBJECT")
                continue
            if row.get("symbol") != SYMBOL:
                errors.append(f"ROW_{index}_SYMBOL_MISMATCH")
            if "fundingRate" not in row or "fundingTime" not in row:
                errors.append(f"ROW_{index}_REQUIRED_FIELD_MISSING")
                continue
            try:
                ts = int(row["fundingTime"])
            except (TypeError, ValueError):
                errors.append(f"ROW_{index}_INVALID_FUNDING_TIME")
                continue
            timestamps.append(ts)
            if not start_ms <= ts < end_exclusive_ms:
                errors.append(f"ROW_{index}_OUT_OF_RANGE")

    if len(set(timestamps)) != len(timestamps):
        errors.append("DUPLICATE_FUNDING_TIME")

    metadata = {
        "artifact": "BTC_SHADOW2_BINANCE_FUNDING_REST_CAPTURE",
        "version": "1.0",
        "mode": "EVIDENCE_ONLY_NOT_PROMOTING",
        "source": BASE_URL,
        "request_url": request_url,
        "request_params": params,
        "retrieved_at_utc": retrieved_at,
        "http_status": status,
        "raw_file": raw_path.name,
        "raw_bytes": len(raw),
        "raw_sha256": digest,
        "row_count": len(rows) if rows is not None else None,
        "funding_times_ms_sorted": sorted(timestamps),
        "unique_funding_times": len(set(timestamps)),
        "range_start_ms_inclusive": start_ms,
        "range_end_ms_exclusive": end_exclusive_ms,
        "capture_validation": "PASS" if not errors else "FAIL",
        "validation_errors": errors,
        "coverage_claim": False,
        "alpha_allowed": False,
        "paper_trading_allowed": False,
        "mainnet_authorized": False,
        "next_gate": "compare exact observed timestamps and source fields with frozen preregistration and ledger expected events",
    }
    (out_dir / "capture_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2026-10-01", help="UTC start date, inclusive")
    parser.add_argument("--end-exclusive", default="2026-10-05", help="UTC end date, exclusive")
    parser.add_argument("--out", default="artifacts/btc-shadow2-funding-rest")
    args = parser.parse_args()
    try:
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end_exclusive)
        metadata = capture(start, end, Path(args.out))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(metadata, ensure_ascii=False, sort_keys=True))
    return 0 if metadata["capture_validation"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
