from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

DEFAULT_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "GP12_STATUS_SPECIAL_NO_LIMIT_EVIDENCE_V1.json"
)

REQUIRED_FIELDS = {
    "symbol",
    "date",
    "event_type",
    "source_authority",
    "evidence_url",
    "evidence_statement",
}

_EVENT_MAP = {
    "RESTORED_LISTING_FIRST_TRADING_DAY": "RESTORED_LISTING_FIRST_DAY",
    "RELISTING_FIRST_TRADING_DAY": "RELISTING_FIRST_DAY",
    "ABSORPTION_MERGER_A_SHARE_LISTING_FIRST_DAY": "MERGER_LISTING_FIRST_DAY",
    "DELISTING_ARRANGEMENT_FIRST_TRADING_DAY": "DELISTING_ARRANGEMENT_FIRST_DAY",
}


def _normalize_symbol(value: object) -> str:
    symbol = str(value).strip().upper()
    if "." not in symbol:
        raise ValueError(f"exchange-qualified symbol required: {value!r}")
    code, exchange = symbol.split(".", 1)
    if exchange not in {"SZ", "SH"} or not code.isdigit():
        raise ValueError(f"unsupported symbol: {value!r}")
    return f"{code.zfill(6)}.{exchange}"


def _normalize_date(value: object) -> str:
    text = str(value).strip()[:10]
    parts = text.split("-")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise ValueError(f"invalid date: {value!r}")
    year, month, day = map(int, parts)
    if year < 1900 or not 1 <= month <= 12 or not 1 <= day <= 31:
        raise ValueError(f"invalid date: {value!r}")
    return f"{year:04d}-{month:02d}-{day:02d}"


def _source_authority(source: object) -> str:
    value = str(source).strip().lower()
    if "cninfo" in value:
        return "CNINFO"
    if "shenzhen" in value:
        return "SZSE"
    if "shanghai" in value:
        return "SSE"
    raise ValueError(f"unsupported evidence source: {source!r}")


def validate_evidence(rows: Iterable[dict]) -> list[dict]:
    validated: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for original in rows:
        if not isinstance(original, dict):
            raise ValueError(f"evidence row must be object: {original!r}")
        missing = REQUIRED_FIELDS - set(original)
        if missing:
            raise ValueError(f"missing evidence fields: {sorted(missing)}")
        row = dict(original)
        row["symbol"] = _normalize_symbol(row["symbol"])
        row["date"] = _normalize_date(row["date"])
        for field in ("event_type", "source_authority", "evidence_url", "evidence_statement"):
            row[field] = str(row[field]).strip()
            if not row[field]:
                raise ValueError(f"empty evidence field: {field}")
        if not row["evidence_url"].startswith("https://"):
            raise ValueError(f"non-https evidence_url: {row['evidence_url']!r}")
        key = (row["symbol"], row["date"])
        if key in seen:
            raise ValueError(f"duplicate special no-limit evidence key: {key}")
        seen.add(key)
        validated.append(row)
    validated.sort(key=lambda row: (row["symbol"], row["date"]))
    return validated


def _adapt_canonical_entry(entry: dict) -> dict:
    if entry.get("no_price_limit") is not True:
        raise ValueError(f"canonical special evidence must assert no_price_limit: {entry!r}")
    canonical_event = str(entry.get("event_type") or "").strip()
    if canonical_event not in _EVENT_MAP:
        raise ValueError(f"unsupported canonical event_type: {canonical_event!r}")
    return {
        "symbol": entry.get("symbol"),
        "date": entry.get("date"),
        "event_type": _EVENT_MAP[canonical_event],
        "source_authority": _source_authority(entry.get("source")),
        "evidence_url": entry.get("source_url"),
        "evidence_statement": entry.get("evidence"),
    }


def load_evidence(path: str | Path = DEFAULT_EVIDENCE_PATH) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("artifact") != "GP12_STATUS_SPECIAL_NO_LIMIT_EVIDENCE_V1":
        raise ValueError("special no-limit evidence artifact identity mismatch")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("special no-limit evidence entries must be a list")
    if payload.get("entry_count") != len(entries):
        raise ValueError("special no-limit evidence entry_count mismatch")
    return validate_evidence(_adapt_canonical_entry(entry) for entry in entries)


def is_special_no_limit(
    symbol: str,
    trade_date: str,
    *,
    evidence: Iterable[dict] | None = None,
) -> bool:
    normalized_symbol = _normalize_symbol(symbol)
    normalized_date = _normalize_date(trade_date)
    rows = load_evidence() if evidence is None else validate_evidence(evidence)
    return any(
        row["symbol"] == normalized_symbol and row["date"] == normalized_date
        for row in rows
    )
