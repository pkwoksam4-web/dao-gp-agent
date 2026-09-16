from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

ARTIFACT = "GP12_UPPER_LIMIT_SPECIAL_NO_LIMIT_DATES_V1"
VERSION = "1.0"
STATUS = "NEW_RECONSTRUCTION_CANDIDATE"
SUPPORTED_EVENT_TYPES = {
    "RESTORED_LISTING_FIRST_DAY",
    "RELISTING_FIRST_DAY",
    "ABSORPTION_MERGER_LISTING_FIRST_DAY",
    "DELISTING_ARRANGEMENT_FIRST_DAY",
}
NO_LIMIT_SENTINEL_FLOOR = Decimal("99999")
_SYMBOL_RE = re.compile(r"^[0-9]{6}\.(?:SZ|SH)$")


def _iso(value: object, field: str) -> str:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(f"invalid {field}: {value!r}") from exc


def validate_manifest(manifest: dict) -> dict:
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be object")
    if manifest.get("artifact") != ARTIFACT:
        raise ValueError(f"unexpected artifact: {manifest.get('artifact')!r}")
    if str(manifest.get("version")) != VERSION:
        raise ValueError(f"unexpected version: {manifest.get('version')!r}")
    if manifest.get("status") != STATUS:
        raise ValueError(f"unexpected status: {manifest.get('status')!r}")
    for flag in (
        "historical_gp_v11_source_recovered",
        "model_freeze_allowed",
        "oos_metrics_allowed",
    ):
        if manifest.get(flag) is not False:
            raise ValueError(f"{flag} must remain false")

    events = manifest.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("events must be non-empty list")
    seen: set[tuple[str, str]] = set()
    for row in events:
        if not isinstance(row, dict):
            raise ValueError("event row must be object")
        symbol = str(row.get("symbol") or "").strip().upper()
        if not _SYMBOL_RE.fullmatch(symbol):
            raise ValueError(f"invalid symbol: {row.get('symbol')!r}")
        trade_date = _iso(row.get("date"), "date")
        key = (symbol, trade_date)
        if key in seen:
            raise ValueError(f"duplicate special date: {symbol} {trade_date}")
        seen.add(key)
        event_type = str(row.get("event_type") or "").strip()
        if event_type not in SUPPORTED_EVENT_TYPES:
            raise ValueError(f"unsupported event_type: {event_type!r}")
        if row.get("no_price_limit") is not True:
            raise ValueError(f"no_price_limit must be true for {symbol} {trade_date}")
        evidence_url = str(row.get("evidence_url") or "").strip()
        if not evidence_url.startswith("https://"):
            raise ValueError(f"https evidence_url required for {symbol} {trade_date}")
    return manifest


def load_manifest(path: str | Path) -> dict:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_manifest(manifest)


def special_no_limit_dates(manifest: dict) -> set[tuple[str, str]]:
    validate_manifest(manifest)
    return {
        (str(row["symbol"]).strip().upper(), _iso(row["date"], "date"))
        for row in manifest["events"]
    }


def is_no_limit_sentinel(value: object) -> bool:
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid high_limit sentinel value: {value!r}") from exc
    if not parsed.is_finite():
        raise ValueError(f"non-finite high_limit sentinel value: {value!r}")
    return parsed >= NO_LIMIT_SENTINEL_FLOOR
