from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")
HUNDRED = Decimal("100")


def normalize_symbol(symbol: str) -> str:
    value = str(symbol).strip().upper()
    if "." not in value:
        raise ValueError(f"exchange-qualified symbol required: {symbol!r}")
    code, exchange = value.split(".", 1)
    if exchange not in {"SZ", "SH"} or not code.isdigit():
        raise ValueError(f"unsupported symbol: {symbol!r}")
    return f"{code.zfill(6)}.{exchange}"


def _decimal(value: object, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid {field}: {value!r}") from exc
    if not parsed.is_finite():
        raise ValueError(f"non-finite {field}: {value!r}")
    return parsed


def _percent(value: object, field: str) -> Decimal:
    text = str(value).strip()
    if not text.endswith("%"):
        raise ValueError(f"invalid {field}: {value!r}")
    return _decimal(text[:-1], field)


def _money_cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def reference_close_cny(close: object, change_cny: object) -> float:
    reference = _decimal(close, "close") - _decimal(change_cny, "change_cny")
    return float(_money_cents(reference))


def limit_price_cny(reference_close: object, limit_pct_percent: object) -> float:
    reference = _decimal(reference_close, "reference_close")
    pct = _decimal(limit_pct_percent, "limit_pct_percent")
    limit = reference * (Decimal("1") + pct / HUNDRED)
    return float(_money_cents(limit))


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Sohu payload decode failed")


def parse_hishq_reference_bytes(symbol: str, raw: bytes) -> list[dict]:
    normalized = normalize_symbol(symbol)
    text = _decode(raw).strip()
    match = re.match(r"^\s*historySearchHandler\((.*)\)\s*;?\s*$", text, re.S)
    if not match:
        raise ValueError("Sohu JSONP wrapper mismatch")
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError("Sohu JSON payload invalid") from exc
    if not isinstance(payload, list) or not payload:
        return []
    block = payload[0]
    if not isinstance(block, dict):
        raise ValueError("Sohu payload block invalid")
    if int(block.get("status", -1)) != 0:
        return []
    hq = block.get("hq") or []
    if not isinstance(hq, list):
        raise ValueError("Sohu hq payload invalid")

    rows: list[dict] = []
    for source_row in hq:
        if not isinstance(source_row, list) or len(source_row) < 10:
            raise ValueError(f"Sohu hq row invalid: {source_row!r}")
        date = str(source_row[0])[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise ValueError(f"invalid Sohu date: {source_row[0]!r}")
        close = _decimal(source_row[2], "close")
        change = _decimal(source_row[3], "change_cny")
        pct = _percent(source_row[4], "pct_percent")
        turnover = _percent(source_row[9], "turnover_percent")
        reference = _money_cents(close - change)
        rows.append(
            {
                "symbol": normalized,
                "date": date,
                "close": float(close),
                "change_cny": float(change),
                "pct_percent": float(pct),
                "turnover_percent": float(turnover),
                "reference_close_cny": float(reference),
                "source": "SOHU_HISHQ_REFERENCE_V1",
            }
        )
    rows.sort(key=lambda row: row["date"])
    return rows
