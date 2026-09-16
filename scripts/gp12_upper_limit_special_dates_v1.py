from __future__ import annotations

import json
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "GP12_UPPER_LIMIT_SPECIAL_DATES_V1.json"


def _normalize_symbol(symbol: str) -> str:
    value = str(symbol).strip().upper()
    if "." not in value:
        raise ValueError(f"exchange-qualified symbol required: {symbol!r}")
    code, exchange = value.split(".", 1)
    if exchange not in {"SZ", "SH"} or not code.isdigit():
        raise ValueError(f"unsupported symbol: {symbol!r}")
    return f"{code.zfill(6)}.{exchange}"


def _normalize_date(value: str) -> str:
    text = str(value).strip()[:10]
    if len(text) != 10 or text[4] != "-" or text[7] != "-":
        raise ValueError(f"invalid date: {value!r}")
    return text


def _load() -> dict:
    payload = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    if payload.get("artifact") != "GP12_UPPER_LIMIT_SPECIAL_DATES_V1":
        raise RuntimeError("special-date registry artifact mismatch")
    rows = payload.get("evidence")
    if not isinstance(rows, list):
        raise RuntimeError("special-date registry evidence must be a list")
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (_normalize_symbol(row["symbol"]), _normalize_date(row["date"]))
        if key in seen:
            raise RuntimeError(f"duplicate special-date evidence: {key}")
        seen.add(key)
        if row.get("evidence_status") != "PRIMARY_SOURCE_VERIFIED":
            raise RuntimeError(f"unverified special-date evidence: {key}")
        source_url = str(row.get("source_url") or "")
        if not source_url.startswith("https://"):
            raise RuntimeError(f"invalid primary-source URL for {key}")
    return payload


def special_no_limit_registry() -> list[dict]:
    return [dict(row) for row in _load()["evidence"]]


def special_no_limit_keys() -> set[tuple[str, str]]:
    return {
        (_normalize_symbol(row["symbol"]), _normalize_date(row["date"]))
        for row in _load()["evidence"]
    }


def is_special_no_limit(symbol: str, trade_date: str) -> bool:
    key = (_normalize_symbol(symbol), _normalize_date(trade_date))
    return key in special_no_limit_keys()


def special_no_limit_evidence(symbol: str, trade_date: str) -> dict:
    key = (_normalize_symbol(symbol), _normalize_date(trade_date))
    for row in _load()["evidence"]:
        row_key = (_normalize_symbol(row["symbol"]), _normalize_date(row["date"]))
        if row_key == key:
            return dict(row)
    raise KeyError(key)
