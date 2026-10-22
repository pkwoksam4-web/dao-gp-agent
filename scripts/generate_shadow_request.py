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
    ap.add_argument("--now-utc")
    args = ap.parse_args()
    manifest_path = Path(args.manifest)
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    now = (datetime.fromisoformat(args.now_utc.replace("Z", "+00:00"))
           if args.now_utc else datetime.now(timezone.utc))
    request = build_shadow_request(manifest, hashlib.sha256(raw).hexdigest(), now)
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
