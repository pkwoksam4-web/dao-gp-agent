from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.request
import zipfile

EXPERIMENT_ID = "BTC-FLOW-SUCCESSOR-20261008-A"
RELEASE_ZIP_SHA256 = "b6f952c783009b7642720e06d8f5f1781e080497f91b98521aea545cbcb2d86d"
BASE = "https://data.binance.vision/data/futures/um/daily"
START_DATE = date(2026, 8, 13)
END_DATE = date(2026, 10, 4)
FAMILIES = ("klines", "markPriceKlines", "indexPriceKlines", "metrics")
MAX_BODY = 64 * 1024 * 1024
USER_AGENT = "BTCQ-Shadow2-GitHub-archive-capture/1"
_CHECKSUM_RE = re.compile(r"^([0-9a-fA-F]{64})\s+\*?(.+?)\s*$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dates():
    d = START_DATE
    while d <= END_DATE:
        yield d.isoformat()
        d += timedelta(days=1)


def frozen_objects() -> list[dict]:
    out = []
    for family in FAMILIES:
        for day in _dates():
            if family == "metrics":
                filename = f"BTCUSDT-metrics-{day}.zip"
                member = f"BTCUSDT-metrics-{day}.csv"
                url = f"{BASE}/metrics/BTCUSDT/{filename}"
            else:
                filename = f"BTCUSDT-5m-{day}.zip"
                member = f"BTCUSDT-5m-{day}.csv"
                url = f"{BASE}/{family}/BTCUSDT/5m/{filename}"
            out.append({
                "family": family,
                "date": day,
                "filename": filename,
                "member": member,
                "url": url,
                "checksum_url": url + ".CHECKSUM",
            })
    return out


def https_get(url: str) -> tuple[bytes, dict]:
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


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _parse_checksum(sidecar: bytes, expected_filename: str) -> tuple[str | None, list[str]]:
    reasons = []
    try:
        text = sidecar.decode("utf-8").strip()
    except Exception:
        return None, ["CHECKSUM_UTF8_INVALID"]
    m = _CHECKSUM_RE.match(text)
    if not m:
        return None, ["CHECKSUM_FORMAT_INVALID"]
    expected_sha, declared_filename = m.group(1).lower(), m.group(2)
    if declared_filename != expected_filename:
        reasons.append("CHECKSUM_FILENAME_MISMATCH")
    return expected_sha, reasons


def capture_one(obj: dict, root: Path, *, fetcher=https_get) -> dict:
    root = Path(root)
    target = root / obj["family"] / obj["date"]
    target.mkdir(parents=True, exist_ok=True)
    reasons = []
    checksum_transport = None
    zip_transport = None
    sidecar = None
    body = None

    try:
        sidecar, checksum_transport = fetcher(obj["checksum_url"])
        (target / (obj["filename"] + ".CHECKSUM")).write_bytes(sidecar)
    except Exception as exc:
        reasons.append("CHECKSUM_TRANSPORT_ERROR")
        _write_json(target / "checksum_transport_error.json", {
            "url": obj["checksum_url"], "error_type": type(exc).__name__, "error": str(exc), "at_utc": _now()
        })

    try:
        body, zip_transport = fetcher(obj["url"])
        (target / obj["filename"]).write_bytes(body)
    except Exception as exc:
        reasons.append("ZIP_TRANSPORT_ERROR")
        _write_json(target / "zip_transport_error.json", {
            "url": obj["url"], "error_type": type(exc).__name__, "error": str(exc), "at_utc": _now()
        })

    expected_sha = None
    checksum_match = False
    zip_sha = hashlib.sha256(body).hexdigest() if body is not None else None
    if sidecar is not None:
        expected_sha, parse_reasons = _parse_checksum(sidecar, obj["filename"])
        reasons.extend(parse_reasons)
    if expected_sha is not None and zip_sha is not None:
        checksum_match = expected_sha == zip_sha
        if not checksum_match:
            reasons.append("CHECKSUM_MISMATCH")
    elif sidecar is not None and body is not None:
        reasons.append("CHECKSUM_UNPROVEN")

    zip_integrity_ok = False
    member_identity_ok = False
    members = []
    if body is not None:
        try:
            with zipfile.ZipFile(io.BytesIO(body), "r") as zf:
                members = zf.namelist()
                zip_integrity_ok = zf.testzip() is None
                member_identity_ok = members == [obj["member"]]
            if not zip_integrity_ok:
                reasons.append("ZIP_INTEGRITY_FAIL")
            if not member_identity_ok:
                reasons.append("ZIP_MEMBER_IDENTITY_FAIL")
        except Exception as exc:
            reasons.append("ZIP_INVALID")
            _write_json(target / "zip_validation_error.json", {
                "error_type": type(exc).__name__, "error": str(exc), "at_utc": _now()
            })

    passed = (
        sidecar is not None and body is not None and expected_sha is not None and
        checksum_match and zip_integrity_ok and member_identity_ok and not reasons
    )
    result = {
        "family": obj["family"],
        "date": obj["date"],
        "filename": obj["filename"],
        "expected_member": obj["member"],
        "url": obj["url"],
        "checksum_url": obj["checksum_url"],
        "official_checksum_sha256": expected_sha,
        "zip_sha256": zip_sha,
        "checksum_match": checksum_match,
        "zip_integrity_ok": zip_integrity_ok,
        "member_identity_ok": member_identity_ok,
        "members": members,
        "checksum_transport": checksum_transport,
        "zip_transport": zip_transport,
        "pass": passed,
        "reasons": sorted(set(reasons)),
    }
    _write_json(target / "object_report.json", result)
    return result


def capture_all(root: Path, *, objects=None, fetcher=https_get, workers: int = 8) -> dict:
    root = Path(root)
    objects = list(frozen_objects() if objects is None else objects)
    workers = max(1, min(int(workers), 16))

    def work(obj):
        return capture_one(obj, root, fetcher=fetcher)

    if workers == 1 or len(objects) <= 1:
        results = [work(o) for o in objects]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(work, objects))

    passed = sum(1 for r in results if r["pass"])
    failed = [r for r in results if not r["pass"]]
    report = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "release_zip_sha256": RELEASE_ZIP_SHA256,
        "status": "BINANCE_ARCHIVES_CAPTURED_PENDING_OFFLINE_GRID_AND_REST_SEMANTICS" if passed == len(results) else "BINANCE_ARCHIVE_CAPTURE_INCOMPLETE",
        "pass": passed == len(results),
        "objects_expected": len(results),
        "objects_passed": passed,
        "objects_failed": len(results) - passed,
        "zip_count_expected": len(results),
        "checksum_count_expected": len(results),
        "families": list(FAMILIES),
        "date_start": START_DATE.isoformat(),
        "date_end": END_DATE.isoformat(),
        "failed_objects": [
            {"family": r["family"], "date": r["date"], "reasons": r["reasons"]}
            for r in failed
        ],
        "binance_archive_capture_complete": passed == len(results),
        "raw_capture_integrity_ready": False,
        "dataset_coverage_proven": False,
        "oi_semantics_selected": False,
        "basis_semantics_selected": False,
        "flow_alpha_allowed": False,
        "mainnet_authorized": False,
        "order_capability_created": False,
        "requires_offline_grid_audit": True,
        "requires_rest_semantics_evidence": True,
    }
    _write_json(root / "ARCHIVE_CAPTURE_REPORT.json", report)
    _write_json(root / "ARCHIVE_SHA256_LEDGER.json", [
        {
            "family": r["family"], "date": r["date"], "filename": r["filename"],
            "zip_sha256": r["zip_sha256"], "official_checksum_sha256": r["official_checksum_sha256"],
            "pass": r["pass"]
        } for r in results
    ])
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="BTC Shadow2 frozen Binance Data Vision archive capture")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    report = capture_all(Path(args.out), workers=args.workers)
    print(json.dumps({k: report[k] for k in ("status", "pass", "objects_expected", "objects_passed", "objects_failed", "flow_alpha_allowed")}, indent=2, sort_keys=True))
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
