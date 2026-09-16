from __future__ import annotations

import json
import re
import time
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CENT = Decimal("0.01")
HUNDRED = Decimal("100")
BASES = ("https://q.stock.sohu.com/hisHq", "http://q.stock.sohu.com/hisHq")


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
        trade_date = str(source_row[0])[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", trade_date):
            raise ValueError(f"invalid Sohu date: {source_row[0]!r}")
        close = _decimal(source_row[2], "close")
        change = _decimal(source_row[3], "change_cny")
        pct = _percent(source_row[4], "pct_percent")
        turnover = _percent(source_row[9], "turnover_percent")
        reference = _money_cents(close - change)
        rows.append(
            {
                "symbol": normalized,
                "date": trade_date,
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


def plan_chunks(start: str, end: str, max_calendar_days: int = 90) -> list[tuple[str, str]]:
    if max_calendar_days < 1:
        raise ValueError("max_calendar_days must be positive")
    first = date.fromisoformat(start)
    last = date.fromisoformat(end)
    if last < first:
        raise ValueError("end before start")
    chunks: list[tuple[str, str]] = []
    cursor = first
    while cursor <= last:
        stop = min(last, cursor + timedelta(days=max_calendar_days - 1))
        chunks.append((cursor.isoformat(), stop.isoformat()))
        cursor = stop + timedelta(days=1)
    return chunks


def select_shard(symbols: list[str], shard_index: int, shard_count: int) -> list[str]:
    if shard_count <= 0 or not 0 <= shard_index < shard_count:
        raise ValueError("invalid shard index/count")
    return list(symbols)[shard_index::shard_count]


def audit_expected_dates(symbol: str, expected_dates: list[str], rows: list[dict]) -> dict:
    normalized = normalize_symbol(symbol)
    expected = sorted(set(str(value)[:10] for value in expected_dates))
    observed_rows = [row for row in rows if row.get("date")]
    wrong_symbol_n = sum(
        normalize_symbol(row.get("symbol")) != normalized for row in observed_rows
    )
    observed = [str(row["date"])[:10] for row in observed_rows]
    observed_unique = sorted(set(observed))
    duplicate_dates_n = len(observed) - len(observed_unique)
    missing = sorted(set(expected) - set(observed_unique))
    extra = sorted(set(observed_unique) - set(expected))
    passed = (
        wrong_symbol_n == 0
        and duplicate_dates_n == 0
        and not missing
        and not extra
        and len(observed_rows) == len(expected)
    )
    return {
        "symbol": normalized,
        "expected_rows": len(expected),
        "observed_rows": len(observed_rows),
        "duplicate_dates_n": duplicate_dates_n,
        "wrong_symbol_n": wrong_symbol_n,
        "missing_dates_n": len(missing),
        "extra_dates_n": len(extra),
        "missing_dates": missing,
        "extra_dates": extra,
        "status": "PASS_EXACT_DATES" if passed else "REVIEW_DATE_AXIS",
    }


def _request_bytes(symbol: str, start: str, end: str, timeout: int, base: str) -> bytes:
    normalized = normalize_symbol(symbol)
    code = normalized.split(".", 1)[0]
    query = urlencode(
        {
            "code": f"cn_{code}",
            "start": start.replace("-", ""),
            "end": end.replace("-", ""),
            "stat": "1",
            "order": "A",
            "period": "d",
            "callback": "historySearchHandler",
            "rt": "jsonp",
        }
    )
    request = Request(
        f"{base}?{query}",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
            "Referer": f"https://q.stock.sohu.com/cn/{code}/lshq.shtml",
            "Accept": "*/*",
            "Connection": "close",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_chunk_reference(
    symbol: str,
    start: str,
    end: str,
    *,
    timeout: int = 20,
    retries: int = 3,
) -> list[dict]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        for base in BASES:
            try:
                return parse_hishq_reference_bytes(
                    symbol, _request_bytes(symbol, start, end, timeout, base)
                )
            except Exception as exc:
                last_error = exc
        if attempt < retries:
            time.sleep(0.8 * attempt)
    raise RuntimeError(
        f"Sohu reference fetch failed for {normalize_symbol(symbol)} {start}..{end}: {last_error}"
    ) from last_error


def _merge_reference_rows_unique(symbol: str, *parts: list[dict]) -> list[dict]:
    normalized = normalize_symbol(symbol)
    by_date: dict[str, dict] = {}
    for rows in parts:
        for row in rows:
            if normalize_symbol(row.get("symbol")) != normalized:
                raise RuntimeError(f"wrong-symbol Sohu reference row for {normalized}: {row!r}")
            trade_date = str(row.get("date") or "")[:10]
            if not trade_date:
                raise RuntimeError(f"missing-date Sohu reference row for {normalized}: {row!r}")
            if trade_date in by_date and by_date[trade_date] != row:
                raise RuntimeError(
                    f"conflicting duplicate Sohu reference row {normalized} {trade_date}"
                )
            by_date[trade_date] = row
    return [by_date[trade_date] for trade_date in sorted(by_date)]


def fetch_chunk_reference_resilient(
    symbol: str,
    start: str,
    end: str,
    *,
    timeout: int = 20,
    retries: int = 3,
    min_calendar_days: int = 1,
) -> tuple[list[dict], dict]:
    first = date.fromisoformat(start)
    last = date.fromisoformat(end)
    if last < first:
        raise ValueError("end before start")
    try:
        rows = fetch_chunk_reference(
            symbol, start, end, timeout=timeout, retries=retries
        )
        return rows, {
            "split_recovery_n": 0,
            "leaf_chunk_n": 1,
            "leaf_nonempty_n": int(bool(rows)),
            "max_leaf_rows": len(rows),
        }
    except RuntimeError:
        calendar_days = (last - first).days + 1
        if calendar_days <= min_calendar_days:
            raise
        midpoint = first + timedelta(days=(calendar_days // 2) - 1)
        right_start = midpoint + timedelta(days=1)
        time.sleep(0.25)
        left_rows, left_meta = fetch_chunk_reference_resilient(
            symbol,
            first.isoformat(),
            midpoint.isoformat(),
            timeout=timeout,
            retries=retries,
            min_calendar_days=min_calendar_days,
        )
        right_rows, right_meta = fetch_chunk_reference_resilient(
            symbol,
            right_start.isoformat(),
            last.isoformat(),
            timeout=timeout,
            retries=retries,
            min_calendar_days=min_calendar_days,
        )
        rows = _merge_reference_rows_unique(symbol, left_rows, right_rows)
        return rows, {
            "split_recovery_n": 1 + left_meta["split_recovery_n"] + right_meta["split_recovery_n"],
            "leaf_chunk_n": left_meta["leaf_chunk_n"] + right_meta["leaf_chunk_n"],
            "leaf_nonempty_n": left_meta["leaf_nonempty_n"] + right_meta["leaf_nonempty_n"],
            "max_leaf_rows": max(left_meta["max_leaf_rows"], right_meta["max_leaf_rows"]),
        }


def fetch_symbol_reference(
    symbol: str,
    start: str,
    end: str,
    *,
    max_calendar_days: int = 90,
    timeout: int = 20,
    retries: int = 3,
    delay: float = 0.05,
) -> list[dict]:
    normalized = normalize_symbol(symbol)
    parts: list[list[dict]] = []
    for chunk_start, chunk_end in plan_chunks(start, end, max_calendar_days):
        rows, _ = fetch_chunk_reference_resilient(
            normalized,
            chunk_start,
            chunk_end,
            timeout=timeout,
            retries=retries,
        )
        if len(rows) >= 80:
            raise RuntimeError(
                f"Sohu reference chunk may be truncated ({len(rows)} rows) {normalized} {chunk_start}..{chunk_end}"
            )
        parts.append(rows)
        if delay > 0:
            time.sleep(delay)
    return _merge_reference_rows_unique(normalized, *parts)
