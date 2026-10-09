from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

EXPERIMENT_ID = "BTC-FLOW-SUCCESSOR-20261008-A"
RELEASE_ZIP_SHA256 = "b6f952c783009b7642720e06d8f5f1781e080497f91b98521aea545cbcb2d86d"
STEP_MS = 300_000
MAX_BODY = 16 * 1024 * 1024
USER_AGENT = "BTCQ-Shadow2-GitHub-REST-rescue/1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def frozen_specs() -> dict:
    return {
        "oi": {
            "endpoint": "https://fapi.binance.com/futures/data/openInterestHist",
            "fixed": {"symbol": "BTCUSDT", "period": "5m", "limit": 500},
            "start_ms": 1790726400000,
            "end_exclusive_ms": 1791158400000,
            "timestamp_field": "timestamp",
            "min_rows": 1000,
        },
        "basis": {
            "endpoint": "https://fapi.binance.com/futures/data/basis",
            "fixed": {"pair": "BTCUSDT", "contractType": "PERPETUAL", "period": "5m", "limit": 500},
            "start_ms": 1791072000000,
            "end_exclusive_ms": 1791158400000,
            "timestamp_field": "timestamp",
            "min_rows": 288,
        },
        "funding": {
            "endpoint": "https://fapi.binance.com/fapi/v1/fundingRate",
            "fixed": {"symbol": "BTCUSDT", "limit": 1000},
            "start_ms": 1786650900000,
            "end_exclusive_ms": 1791158400000,
            "timestamp_field": "fundingTime",
            "min_rows": 1,
        },
    }


def _url(endpoint: str, params: dict) -> str:
    return endpoint + "?" + urllib.parse.urlencode(params)


def https_get(endpoint: str, params: dict) -> tuple[bytes, dict]:
    url = _url(endpoint, params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    started = _now()
    with urllib.request.urlopen(req, timeout=30) as resp:
        status = int(resp.status)
        if status != 200:
            raise RuntimeError(f"HTTP_STATUS_{status}")
        body = resp.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            raise RuntimeError("RESPONSE_TOO_LARGE")
        return body, {
            "request_url": url,
            "http_status": status,
            "started_at_utc": started,
            "retrieved_at_utc": _now(),
            "content_type": resp.headers.get("Content-Type"),
            "content_length": resp.headers.get("Content-Length"),
            "response_size_bytes": len(body),
            "response_sha256": hashlib.sha256(body).hexdigest(),
            "ca_verification_enabled": True,
        }


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def capture_kind(kind: str, spec: dict, outdir: Path, *, fetcher=https_get) -> dict:
    if kind not in ("oi", "basis", "funding"):
        raise ValueError("unsupported kind")
    page_dir = Path(outdir) / "rest" / kind
    page_dir.mkdir(parents=True, exist_ok=True)
    end_time = spec["end_exclusive_ms"] - (1 if kind == "funding" else STEP_MS)
    params = dict(spec["fixed"])
    params.update({"startTime": spec["start_ms"], "endTime": end_time})
    limit = int(spec["fixed"]["limit"])
    total_rows = 0
    pages = 0
    first_ts = None
    last_ts = None
    errors = []
    terminal_proven = False

    for page_index in range(16):
        request_url = _url(spec["endpoint"], params)
        try:
            body, transport = fetcher(spec["endpoint"], dict(params))
        except Exception as exc:
            _write_json(page_dir / f"transport_error_{page_index:03d}.meta.json", {
                "request_url": request_url,
                "request_params": dict(params),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "captured_pages_before_error": pages,
                "retrieved_at_utc": _now(),
            })
            errors.append("REST_TRANSPORT_ERROR")
            break

        sha = hashlib.sha256(body).hexdigest()
        retrieved = str(transport.get("retrieved_at_utc") or _now())
        raw_path = page_dir / f"page_{page_index:03d}.json"
        raw_path.write_bytes(body)
        meta = {
            "request_url": request_url,
            "request_params": dict(params),
            "raw_body_sha256": sha,
            "retrieved_at_utc": retrieved,
            "transport": transport,
        }

        try:
            rows = json.loads(body.decode("utf-8"))
            if not isinstance(rows, list):
                raise ValueError("response is not a JSON array")
        except Exception as exc:
            meta["parse_error"] = f"{type(exc).__name__}: {exc}"
            _write_json(page_dir / f"page_{page_index:03d}.meta.json", meta)
            errors.append("REST_JSON_INVALID")
            pages += 1
            break

        timestamps = []
        try:
            for row in rows:
                timestamps.append(int(row[spec["timestamp_field"]]))
        except Exception as exc:
            meta["timestamp_error"] = f"{type(exc).__name__}: {exc}"
            _write_json(page_dir / f"page_{page_index:03d}.meta.json", meta)
            errors.append("REST_TIMESTAMP_INVALID")
            pages += 1
            total_rows += len(rows)
            break

        meta["row_count"] = len(rows)
        meta["first_timestamp_ms"] = timestamps[0] if timestamps else None
        meta["last_timestamp_ms"] = timestamps[-1] if timestamps else None
        _write_json(page_dir / f"page_{page_index:03d}.meta.json", meta)

        pages += 1
        total_rows += len(rows)
        if timestamps:
            first_ts = timestamps[0] if first_ts is None else first_ts
            last_ts = timestamps[-1]

        if kind == "basis":
            terminal_proven = len(rows) < limit
            break
        if not rows:
            terminal_proven = True
            break
        if len(rows) < limit:
            terminal_proven = True
            break
        if last_ts is None or last_ts >= end_time:
            terminal_proven = True
            break
        params = dict(spec["fixed"])
        params.update({
            "startTime": last_ts + (STEP_MS if kind == "oi" else 1),
            "endTime": end_time,
        })
    else:
        errors.append("REST_MAX_PAGES_EXCEEDED")

    rows_min_ok = total_rows >= int(spec["min_rows"])
    if not rows_min_ok:
        errors.append("REST_MIN_ROWS_NOT_MET")
    transport_complete = not any(e in errors for e in ("REST_TRANSPORT_ERROR", "REST_JSON_INVALID", "REST_TIMESTAMP_INVALID", "REST_MAX_PAGES_EXCEEDED"))
    return {
        "kind": kind,
        "transport_complete": transport_complete,
        "terminal_page_proven": terminal_proven,
        "pages": pages,
        "rows": total_rows,
        "minimum_rows": int(spec["min_rows"]),
        "minimum_rows_present": rows_min_ok,
        "first_timestamp_ms": first_ts,
        "last_timestamp_ms": last_ts,
        "reasons": sorted(set(errors)),
    }


def capture_all(outdir: Path, *, fetcher=https_get) -> dict:
    outdir = Path(outdir)
    reports = {}
    reasons = []
    for kind, spec in frozen_specs().items():
        report = capture_kind(kind, spec, outdir, fetcher=fetcher)
        reports[kind] = report
        reasons.extend(report["reasons"])

    passed = all(r["transport_complete"] and r["minimum_rows_present"] for r in reports.values())
    report = {
        "schema_version": 1,
        "status": "REST_BYTES_CAPTURED_PENDING_V4_VALIDATION" if passed else "REST_TRANSPORT_INCOMPLETE",
        "pass": bool(passed),
        "experiment_id": EXPERIMENT_ID,
        "release_zip_sha256": RELEASE_ZIP_SHA256,
        "rest": reports,
        "reasons": sorted(set(reasons)),
        "rest_capture_integrity_ready": False,
        "raw_capture_integrity_ready": False,
        "dataset_coverage_proven": False,
        "oi_semantics_selected": False,
        "basis_semantics_selected": False,
        "flow_alpha_allowed": False,
        "mainnet_authorized": False,
        "order_capability_created": False,
        "requires_offline_v4_validation": True,
    }
    _write_json(outdir / "REST_CAPTURE_REPORT.json", report)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="BTC Shadow2 frozen REST evidence rescue; public market GET only")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    report = capture_all(Path(args.out))
    print(json.dumps({k: report[k] for k in ("status", "pass", "experiment_id", "reasons", "flow_alpha_allowed")}, indent=2, sort_keys=True))
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
