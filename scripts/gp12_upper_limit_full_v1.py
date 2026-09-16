from __future__ import annotations

from typing import Mapping, Iterable

import pandas as pd

import gp12_upper_limit_rule_v1 as rule

FORMAL_START = "2020-06-01"


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
    try:
        return pd.Timestamp(text).date().isoformat()
    except Exception as exc:
        raise ValueError(f"invalid date: {value!r}") from exc


def _normalize_reference(reference: pd.DataFrame) -> pd.DataFrame:
    required = {"symbol", "date", "close", "reference_close_cny"}
    missing = required - set(reference.columns)
    if missing:
        raise ValueError(f"missing reference columns: {sorted(missing)}")
    frame = reference.copy()
    frame["symbol"] = frame["symbol"].astype(str).map(_normalize_symbol)
    frame["date"] = frame["date"].astype(str).map(_normalize_date)
    frame["close"] = pd.to_numeric(frame["close"], errors="raise")
    frame["reference_close_cny"] = pd.to_numeric(frame["reference_close_cny"], errors="raise")
    duplicate_n = int(frame.duplicated(["symbol", "date"]).sum())
    if duplicate_n:
        raise ValueError(f"duplicate reference symbol-date rows: {duplicate_n}")
    if bool((frame["close"] <= 0).any()) or bool((frame["reference_close_cny"] <= 0).any()):
        raise ValueError("reference panel contains nonpositive prices")
    return frame.sort_values(["symbol", "date"]).reset_index(drop=True)


def _normalize_ipo_dates(ipo_dates: Mapping[str, object]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for symbol, ipo_date in ipo_dates.items():
        key = _normalize_symbol(symbol)
        value = _normalize_date(ipo_date)
        if key in normalized and normalized[key] != value:
            raise ValueError(f"conflicting IPO date for {key}")
        normalized[key] = value
    return normalized


def attach_listing_trade_rank(
    reference: pd.DataFrame,
    ipo_dates: Mapping[str, object],
    *,
    formal_start: str = FORMAL_START,
) -> pd.DataFrame:
    """Attach authoritative IPO date and one-based positive-trade rank.

    The pinned reference panel is itself the bound positive-trade axis.  Ranking is
    therefore computed only for IPOs whose authoritative IPO date is observable
    inside the Formal window.  Pre-Formal listings intentionally receive no rank;
    they are mature listings for all ordinary Formal sessions unless an exact
    source-backed special-date override applies.
    """
    frame = _normalize_reference(reference)
    ipo_map = _normalize_ipo_dates(ipo_dates)
    start = _normalize_date(formal_start)
    frame["ipo_date"] = frame["symbol"].map(ipo_map)
    missing_symbols = sorted(frame.loc[frame["ipo_date"].isna(), "symbol"].unique().tolist())
    if missing_symbols:
        raise ValueError(f"missing IPO date for symbols: {missing_symbols[:20]}")
    before_ipo = frame[frame["date"] < frame["ipo_date"]]
    if len(before_ipo):
        raise ValueError(f"positive trade before IPO date: {before_ipo[['symbol','date','ipo_date']].head(20).to_dict('records')}")

    frame["listing_trade_rank"] = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    eligible = (frame["ipo_date"] >= start) & (frame["date"] >= frame["ipo_date"])
    if bool(eligible.any()):
        ranks = frame.loc[eligible].groupby("symbol", sort=False).cumcount() + 1
        frame.loc[eligible, "listing_trade_rank"] = pd.array(ranks, dtype="Int64")
    return frame


def _normalize_special_keys(keys: Iterable[tuple[object, object]]) -> set[tuple[str, str]]:
    normalized: set[tuple[str, str]] = set()
    for symbol, trade_date in keys:
        key = (_normalize_symbol(symbol), _normalize_date(trade_date))
        if key in normalized:
            raise ValueError(f"duplicate special no-limit key: {key}")
        normalized.add(key)
    return normalized


def _normalize_pit_status(pit_status: pd.DataFrame) -> pd.DataFrame:
    required = {"symbol", "date", "isST"}
    missing = required - set(pit_status.columns)
    if missing:
        raise ValueError(f"missing PIT status columns: {sorted(missing)}")
    pit = pit_status[["symbol", "date", "isST"]].copy()
    pit["symbol"] = pit["symbol"].astype(str).map(_normalize_symbol)
    pit["date"] = pit["date"].astype(str).map(_normalize_date)
    duplicate_n = int(pit.duplicated(["symbol", "date"]).sum())
    if duplicate_n:
        raise ValueError(f"duplicate PIT status symbol-date rows: {duplicate_n}")
    pit["isST"] = pd.to_numeric(pit["isST"], errors="coerce")
    invalid = pit[~pit["isST"].isin([0, 1])]
    if len(invalid):
        raise ValueError(f"invalid PIT isST rows: {invalid.head(20).to_dict('records')}")
    pit["isST"] = pit["isST"].astype(int)
    return pit


def materialize_upper_limit_panel(
    reference: pd.DataFrame,
    pit_status: pd.DataFrame,
    ipo_dates: Mapping[str, object],
    *,
    special_keys: Iterable[tuple[object, object]],
    formal_start: str = FORMAL_START,
) -> tuple[pd.DataFrame, dict]:
    ranked = attach_listing_trade_rank(reference, ipo_dates, formal_start=formal_start)
    pit = _normalize_pit_status(pit_status)
    frame = ranked.merge(pit, on=["symbol", "date"], how="left", validate="one_to_one")
    missing_status = frame[frame["isST"].isna()]
    if len(missing_status):
        raise ValueError(
            f"missing PIT status rows: {missing_status[['symbol','date']].head(20).to_dict('records')}"
        )
    frame["isST"] = frame["isST"].astype(int)

    exact_special = _normalize_special_keys(special_keys)
    frame["special_no_limit"] = [
        (symbol, trade_date) in exact_special
        for symbol, trade_date in zip(frame["symbol"], frame["date"])
    ]

    limit_pcts: list[float | None] = []
    for row in frame[["symbol", "date", "isST", "ipo_date", "listing_trade_rank", "special_no_limit"]].itertuples(index=False):
        rank = None if pd.isna(row.listing_trade_rank) else int(row.listing_trade_rank)
        limit_pcts.append(
            rule.limit_percent(
                row.symbol,
                row.date,
                bool(row.isST),
                ipo_date=row.ipo_date,
                listing_trade_rank=rank,
                special_no_limit=bool(row.special_no_limit),
            )
        )
    frame["limit_pct_percent"] = limit_pcts

    limit_prices: list[float | None] = []
    upper_limit: list[bool] = []
    for close, reference_close, pct in zip(
        frame["close"], frame["reference_close_cny"], frame["limit_pct_percent"]
    ):
        if pd.isna(pct):
            limit_prices.append(None)
            upper_limit.append(False)
        else:
            pct_value = float(pct)
            limit_prices.append(rule.limit_price_cny(reference_close, pct_value))
            upper_limit.append(rule.is_upper_limit(close, reference_close, pct_value))
    frame["limit_price_cny"] = limit_prices
    frame["upper_limit"] = upper_limit

    frame = frame.sort_values(["symbol", "date"]).reset_index(drop=True)
    audit = {
        "artifact": "GP12_UPPER_LIMIT_PANEL_V1",
        "status": "PASS_UPPER_LIMIT_PANEL",
        "rows": int(len(frame)),
        "symbol_n": int(frame["symbol"].nunique()),
        "duplicate_symbol_dates": int(frame.duplicated(["symbol", "date"]).sum()),
        "missing_status_rows": 0,
        "special_no_limit_rows": int(frame["special_no_limit"].sum()),
        "no_limit_rows": int(frame["limit_pct_percent"].isna().sum()),
        "upper_limit_rows": int(frame["upper_limit"].sum()),
        "historical_gp_v11_source_recovered": False,
        "formal_binding_allowed": False,
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
    }
    return frame, audit
