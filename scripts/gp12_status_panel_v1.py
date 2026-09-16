from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import pandas as pd

import gp12_upper_limit_rule_v1 as upper

FORMAL_START = "2020-06-01"
CENT = Decimal("0.01")


def _normalize_symbol(value: object) -> str:
    symbol = str(value).strip().upper()
    upper.board(symbol)  # fail closed on unsupported / malformed boards
    return symbol


def _normalize_date(value: object) -> str:
    text = str(value).strip()[:10]
    try:
        return pd.Timestamp(text).date().isoformat()
    except Exception as exc:
        raise ValueError(f"invalid date: {value!r}") from exc


def _decimal(value: object, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid {field}: {value!r}") from exc
    if not parsed.is_finite():
        raise ValueError(f"non-finite {field}: {value!r}")
    return parsed


def _cents_equal(left: object, right: object) -> bool:
    return _decimal(left, "left price").quantize(CENT, rounding=ROUND_HALF_UP) == _decimal(
        right, "right price"
    ).quantize(CENT, rounding=ROUND_HALF_UP)


def _prepare_lifecycle(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"symbol", "date", "isST"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing lifecycle columns: {sorted(missing)}")
    out = frame[["symbol", "date", "isST"]].copy()
    out["symbol"] = out["symbol"].map(_normalize_symbol)
    out["date"] = out["date"].map(_normalize_date)
    if out.duplicated(["symbol", "date"]).any():
        raise ValueError("duplicate lifecycle symbol-date key")
    values = pd.to_numeric(out["isST"], errors="raise")
    if not values.isin([0, 1]).all():
        raise ValueError("invalid lifecycle isST value")
    out["isST"] = values.astype(int)
    return out.sort_values(["symbol", "date"]).reset_index(drop=True)


def _prepare_trade(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"symbol", "date", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing trade columns: {sorted(missing)}")
    out = frame[["symbol", "date", "close"]].copy()
    out["symbol"] = out["symbol"].map(_normalize_symbol)
    out["date"] = out["date"].map(_normalize_date)
    out["close"] = pd.to_numeric(out["close"], errors="raise")
    if out.duplicated(["symbol", "date"]).any():
        raise ValueError("duplicate trade symbol-date key")
    if (out["close"] <= 0).any():
        raise ValueError("nonpositive trade close")
    return out.sort_values(["symbol", "date"]).reset_index(drop=True)


def _prepare_reference(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"symbol", "date", "close", "reference_close_cny"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing reference columns: {sorted(missing)}")
    out = frame[["symbol", "date", "close", "reference_close_cny"]].copy()
    out["symbol"] = out["symbol"].map(_normalize_symbol)
    out["date"] = out["date"].map(_normalize_date)
    out["close"] = pd.to_numeric(out["close"], errors="raise")
    out["reference_close_cny"] = pd.to_numeric(out["reference_close_cny"], errors="raise")
    if out.duplicated(["symbol", "date"]).any():
        raise ValueError("duplicate reference symbol-date key")
    if (out["close"] <= 0).any() or (out["reference_close_cny"] <= 0).any():
        raise ValueError("nonpositive reference price")
    return out.sort_values(["symbol", "date"]).reset_index(drop=True)


def _prepare_basics(basics: dict, lifecycle_symbols: set[str]) -> dict[str, str]:
    if not isinstance(basics, dict):
        raise ValueError("basic metadata must be a mapping")
    result: dict[str, str] = {}
    normalized_source = {str(key).strip().upper(): value for key, value in basics.items()}
    for symbol in sorted(lifecycle_symbols):
        row = normalized_source.get(symbol)
        if not isinstance(row, dict):
            raise ValueError(f"missing basic metadata for {symbol}")
        ipo = str(row.get("ipoDate") or "").strip()[:10]
        if not ipo:
            raise ValueError(f"missing basic ipoDate for {symbol}")
        ipo = _normalize_date(ipo)
        result[symbol] = ipo
    return result


def _prepare_special_keys(special_keys: set[tuple[str, str]] | list[tuple[str, str]], lifecycle_keys: set[tuple[str, str]]) -> set[tuple[str, str]]:
    normalized: set[tuple[str, str]] = set()
    for symbol, trade_date in special_keys:
        key = (_normalize_symbol(symbol), _normalize_date(trade_date))
        if key in normalized:
            raise ValueError(f"duplicate special key: {key}")
        normalized.add(key)
    outside = sorted(normalized - lifecycle_keys)
    if outside:
        raise ValueError(f"special key outside lifecycle: {outside[:20]}")
    return normalized


def build_status_panel(
    lifecycle: pd.DataFrame,
    trade: pd.DataFrame,
    reference: pd.DataFrame,
    basics: dict,
    special_no_limit_keys: set[tuple[str, str]] | list[tuple[str, str]],
) -> tuple[pd.DataFrame, dict]:
    life = _prepare_lifecycle(lifecycle)
    trades = _prepare_trade(trade)
    refs = _prepare_reference(reference)

    lifecycle_keys = set(map(tuple, life[["symbol", "date"]].itertuples(index=False, name=None)))
    trade_keys = set(map(tuple, trades[["symbol", "date"]].itertuples(index=False, name=None)))
    reference_keys = set(map(tuple, refs[["symbol", "date"]].itertuples(index=False, name=None)))

    outside_trade = sorted(trade_keys - lifecycle_keys)
    if outside_trade:
        raise ValueError(f"trade key outside lifecycle: {outside_trade[:20]}")
    if reference_keys != trade_keys:
        missing = sorted(trade_keys - reference_keys)
        extra = sorted(reference_keys - trade_keys)
        raise ValueError(f"reference key mismatch: missing={missing[:20]} extra={extra[:20]}")

    basic_ipo = _prepare_basics(basics, set(life["symbol"]))
    special = _prepare_special_keys(special_no_limit_keys, lifecycle_keys)
    special_not_trade = sorted(special - trade_keys)
    if special_not_trade:
        raise ValueError(f"special key is not tradable: {special_not_trade[:20]}")

    close_check = trades.merge(
        refs[["symbol", "date", "close"]].rename(columns={"close": "reference_source_close"}),
        on=["symbol", "date"],
        how="inner",
        validate="one_to_one",
    )
    mismatches = close_check[
        ~close_check.apply(
            lambda row: _cents_equal(row["close"], row["reference_source_close"]), axis=1
        )
    ]
    if len(mismatches):
        raise ValueError(f"close mismatch: {mismatches.head(20).to_dict('records')}")

    # Session rank is observable from this Formal panel only for IPOs whose
    # authoritative IPO date is inside the Formal window. Old listed stocks
    # must never be assigned rank 1 merely because Formal begins in 2020.
    ranked = trades.copy()
    ranked["ipo_date"] = ranked["symbol"].map(basic_ipo)
    ranked = ranked[
        (ranked["ipo_date"] >= FORMAL_START) & (ranked["date"] >= ranked["ipo_date"])
    ].sort_values(["symbol", "date"])
    ranked["listing_trade_rank"] = ranked.groupby("symbol").cumcount() + 1
    rank_map = {
        (row.symbol, row.date): int(row.listing_trade_rank)
        for row in ranked[["symbol", "date", "listing_trade_rank"]].itertuples(index=False)
    }

    trade_lookup = trades.set_index(["symbol", "date"])["close"].to_dict()
    ref_lookup = refs.set_index(["symbol", "date"])["reference_close_cny"].to_dict()

    output_rows: list[dict] = []
    upper_limit_n = 0
    no_limit_n = 0
    for row in life.itertuples(index=False):
        key = (row.symbol, row.date)
        tradable = key in trade_keys
        base = {
            "symbol": row.symbol,
            "date": row.date,
            "is_st": bool(row.isST),
            "tradable": bool(tradable),
            "special_no_limit": bool(key in special),
            "listing_trade_rank": rank_map.get(key),
            "reference_close_cny": None,
            "limit_pct_percent": None,
            "limit_price_cny": None,
            "upper_limit": False,
        }
        if not tradable:
            output_rows.append(base)
            continue

        close = trade_lookup[key]
        reference_close = ref_lookup[key]
        pct = upper.limit_percent(
            row.symbol,
            row.date,
            bool(row.isST),
            ipo_date=basic_ipo[row.symbol],
            listing_trade_rank=rank_map.get(key),
            special_no_limit=key in special,
        )
        limit_price = None if pct is None else upper.limit_price_cny(reference_close, pct)
        at_limit = upper.is_upper_limit(close, reference_close, pct)
        if pct is None:
            no_limit_n += 1
        if at_limit:
            upper_limit_n += 1
        output_rows.append(
            {
                **base,
                "reference_close_cny": float(reference_close),
                "limit_pct_percent": pct,
                "limit_price_cny": limit_price,
                "upper_limit": bool(at_limit),
            }
        )

    panel = pd.DataFrame(output_rows)
    # Preserve semantic nulls as Python None instead of float NaN in the API contract.
    for column in ["listing_trade_rank", "reference_close_cny", "limit_pct_percent", "limit_price_cny"]:
        panel[column] = pd.Series(
            [None if pd.isna(value) else value for value in panel[column].tolist()],
            dtype=object,
        )
    panel = panel.sort_values(["symbol", "date"]).reset_index(drop=True)
    audit = {
        "status": "PASS_EXACT_STATUS_PANEL",
        "lifecycle_rows": int(len(panel)),
        "lifecycle_symbols": int(panel["symbol"].nunique()),
        "tradable_rows": int(panel["tradable"].sum()),
        "nontradable_rows": int((~panel["tradable"]).sum()),
        "special_no_limit_rows": int(panel["special_no_limit"].sum()),
        "no_limit_rows": int(no_limit_n),
        "upper_limit_rows": int(upper_limit_n),
        "duplicate_symbol_dates": 0,
        "reference_key_mismatch_n": 0,
        "close_mismatch_n": 0,
    }
    return panel, audit
