from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")
MAINBOARD_REGISTRATION_FIRST_LIST_DATE = "2023-04-10"
CHINEXT_REFORM_DATE = "2020-08-24"


def _decimal(value: object, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid {field}: {value!r}") from exc
    if not parsed.is_finite():
        raise ValueError(f"non-finite {field}: {value!r}")
    return parsed


def _iso(value: str, field: str) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError as exc:
        raise ValueError(f"invalid {field}: {value!r}") from exc


def board(symbol: str) -> str:
    value = str(symbol).strip().upper()
    if "." not in value:
        raise ValueError(f"exchange-qualified symbol required: {symbol!r}")
    code, exchange = value.split(".", 1)
    if exchange == "SZ" and code.startswith(("000", "001", "002", "003")):
        return "SZ_MAIN"
    if exchange == "SZ" and code.startswith(("300", "301")):
        return "CHINEXT"
    if exchange == "SH" and code.startswith(("600", "601", "603", "605")):
        return "SH_MAIN"
    if exchange == "SH" and code.startswith("688"):
        return "STAR"
    raise ValueError(f"unsupported board for {symbol}")


def limit_percent(
    symbol: str,
    trade_date: str,
    is_st: bool,
    *,
    ipo_date: str,
    listing_trade_rank: int | None,
    special_no_limit: bool = False,
) -> float | None:
    """Return the applicable upper price-limit percentage, or ``None`` for no limit.

    ``listing_trade_rank`` is one-based and must count actual trading sessions from
    the authoritative IPO date. Relisting, delisting-arrangement first days, and
    other exchange-designated no-limit sessions are deliberately *not* inferred;
    callers must supply them through ``special_no_limit=True`` from explicit evidence.
    """
    trade = _iso(trade_date, "trade_date")
    ipo = _iso(ipo_date, "ipo_date") if str(ipo_date or "").strip() else ""
    venue = board(symbol)

    if special_no_limit:
        return None

    rank = None if listing_trade_rank is None else int(listing_trade_rank)
    if rank is not None and rank < 1:
        raise ValueError(f"invalid listing_trade_rank: {listing_trade_rank!r}")
    if ipo and trade < ipo:
        raise ValueError(f"trade_date {trade} precedes ipo_date {ipo}")

    if venue == "STAR":
        if rank is not None and 1 <= rank <= 5:
            return None
        return 20.0

    if venue == "CHINEXT":
        if ipo and ipo >= CHINEXT_REFORM_DATE and rank is not None and 1 <= rank <= 5:
            return None
        if ipo and ipo < CHINEXT_REFORM_DATE and rank == 1:
            return 44.0
        if trade >= CHINEXT_REFORM_DATE:
            return 20.0
        return 5.0 if bool(is_st) else 10.0

    if venue in {"SZ_MAIN", "SH_MAIN"}:
        if ipo and ipo >= MAINBOARD_REGISTRATION_FIRST_LIST_DATE and rank is not None and 1 <= rank <= 5:
            return None
        if ipo and ipo < MAINBOARD_REGISTRATION_FIRST_LIST_DATE and rank == 1:
            return 44.0
        return 5.0 if bool(is_st) else 10.0

    raise AssertionError(f"unhandled board: {venue}")


def limit_price_cny(reference_close: object, limit_pct_percent: object) -> float:
    reference = _decimal(reference_close, "reference_close")
    pct = _decimal(limit_pct_percent, "limit_pct_percent")
    value = reference * (Decimal("1") + pct / Decimal("100"))
    return float(value.quantize(CENT, rounding=ROUND_HALF_UP))


def is_upper_limit(
    close: object,
    reference_close: object,
    limit_pct_percent: float | None,
) -> bool:
    if limit_pct_percent is None:
        return False
    close_cny = _decimal(close, "close").quantize(CENT, rounding=ROUND_HALF_UP)
    limit_cny = _decimal(
        limit_price_cny(reference_close, limit_pct_percent), "limit_price"
    ).quantize(CENT, rounding=ROUND_HALF_UP)
    return close_cny == limit_cny
