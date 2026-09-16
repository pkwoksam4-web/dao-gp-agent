from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

DEFAULT_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "GP12_UPPER_LIMIT_SPECIAL_NO_LIMIT_V1.json"
)

REQUIRED_FIELDS = {
    "symbol",
    "date",
    "event_type",
    "source_authority",
    "evidence_url",
    "evidence_statement",
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


def load_evidence(path: str | Path = DEFAULT_EVIDENCE_PATH) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("artifact") != "GP12_UPPER_LIMIT_SPECIAL_NO_LIMIT_V1":
        raise ValueError("special no-limit evidence artifact identity mismatch")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("special no-limit evidence rows must be a list")
    return validate_evidence(rows)


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
