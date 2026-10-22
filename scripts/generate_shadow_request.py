#!/usr/bin/env python3
"""Create one immutable, auditable Shadow request after a successful PIT ingest."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from shadow_contract_gates import ContractGateError, build_shadow_request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--ingest-report", required=True)
    ap.add_argument("--now-utc")
    args = ap.parse_args()
    manifest_path = Path(args.manifest)
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    report_path = Path(args.ingest_report)
    report_raw = report_path.read_bytes()
    report = json.loads(report_raw)
    manifest_sha = hashlib.sha256(raw).hexdigest()
    if report.get("status") != "PASS" or report.get("manifest_sha256") != manifest_sha:
        raise ContractGateError("ingest report must PASS for the exact manifest")
    coverage = report.get("verified_coverage")
    if coverage != {"bars": 13, "features": 13}:
        raise ContractGateError("ingest report must verify 13 bars and 13 features")
    ingest_evidence = {
        "status": report["status"],
        "manifest_sha256": manifest_sha,
        "ingest_report_sha256": hashlib.sha256(report_raw).hexdigest(),
        "verified_rows": coverage,
    }
    now = (datetime.fromisoformat(args.now_utc.replace("Z", "+00:00"))
           if args.now_utc else datetime.now(timezone.utc))
    request = build_shadow_request(manifest, manifest_sha, now, ingest_evidence)
    out = Path("runtime/shadow_requests") / f"{manifest['trade_date_cn']}.json"
    if out.exists():
        existing = json.loads(out.read_text(encoding="utf-8"))
        old_key = existing.get("trigger", {}).get("idempotency_key")
        new_key = request["trigger"]["idempotency_key"]
        if old_key == new_key:
            print("SHADOW_REQUEST_NOOP_ALREADY_EXISTS")
            return
        raise ContractGateError(f"immutable shadow request conflict: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"SHADOW_REQUEST_CREATED={out}")
    print(f"idempotency_key={request['trigger']['idempotency_key']}")


if __name__ == "__main__":
    main()
