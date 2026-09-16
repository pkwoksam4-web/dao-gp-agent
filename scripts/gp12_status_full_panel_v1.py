from __future__ import annotations

from collections.abc import Mapping, Set

import pandas as pd

import gp12_upper_limit_rule_v1 as rule

FORMAL_START = "2020-06-01"
FORMAL_END = "2026-04-17"


def _normalized_frame(frame: pd.DataFrame, *, label: str) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise ValueError(f"{label} must be a DataFrame")
    if "symbol" not in frame.columns or "date" not in frame.columns:
        raise ValueError(f"{label} requires symbol/date")
    out = frame.copy()
    out["symbol"] = out["symbol"].astype(str).str.strip().str.upper()
    out["date"] = out["date"].astype(str).str[:10]
    if (out["symbol"] == "").any() or (out["date"] == "").any():
        raise ValueError(f"{label} contains blank key")
    if out.duplicated(["symbol", "date"]).any():
        raise ValueError(f"{label} contains duplicate symbol-date")
    return out


def _normalize_special_dates(values: Set[tuple[str, str]] | set[tuple[str, str]]) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    for symbol, trade_date in values:
        result.add((str(symbol).strip().upper(), str(trade_date)[:10]))
    return result


def build_status_panel(
    lifecycle: pd.DataFrame,
    reference: pd.DataFrame,
    ipo_map: Mapping[str, str],
    special_no_limit_dates: Set[tuple[str, str]] | set[tuple[str, str]],
    *,
    formal_start: str = FORMAL_START,
    formal_end: str = FORMAL_END,
) -> tuple[pd.DataFrame, dict]:
    """Build lifecycle-aligned strict boolean candidate status rows.

    ``tradable`` is true exactly when the independently materialized Sohu
    reference panel contains that lifecycle symbol-date. ``upper_limit`` is
    defined only at session close. Non-trading lifecycle rows are always false.
    Explicit exchange-evidenced no-limit dates override the ordinary board/ST
    rule and remain false even when their close happens to equal a normal cap.
    """
    life = _normalized_frame(lifecycle, label="lifecycle")
    ref = _normalized_frame(reference, label="reference")
    if "isST" not in life.columns:
        raise ValueError("lifecycle requires isST")
    for field in ("close", "reference_close_cny"):
        if field not in ref.columns:
            raise ValueError(f"reference requires {field}")
        ref[field] = pd.to_numeric(ref[field], errors="raise")

    life["isST"] = pd.to_numeric(life["isST"], errors="raise").astype(int)
    if not life["isST"].isin([0, 1]).all():
        raise ValueError("lifecycle isST must be 0/1")
    if (life["date"] < formal_start).any() or (life["date"] > formal_end).any():
        raise ValueError("lifecycle outside Formal window")

    life_keys = set(zip(life["symbol"], life["date"]))
    ref_keys = set(zip(ref["symbol"], ref["date"]))
    outside = ref_keys - life_keys
    if outside:
        raise ValueError(f"reference contains keys outside lifecycle: {len(outside)}")

    normalized_ipo = {
        str(symbol).strip().upper(): str(value or "")[:10]
        for symbol, value in dict(ipo_map).items()
    }
    missing_ipo = sorted(set(life["symbol"]) - set(normalized_ipo))
    if missing_ipo:
        raise ValueError(f"missing IPO metadata for {len(missing_ipo)} symbols")
    specials = _normalize_special_dates(special_no_limit_dates)
    unknown_specials = specials - life_keys
    if unknown_specials:
        raise ValueError(f"special no-limit key outside lifecycle: {len(unknown_specials)}")

    merge_fields = ["symbol", "date", "close", "reference_close_cny"]
    panel = life[["symbol", "date", "isST"]].merge(
        ref[merge_fields], on=["symbol", "date"], how="left", validate="one_to_one"
    )
    panel["tradable"] = panel["close"].notna() & panel["reference_close_cny"].notna()
    if (panel["close"].notna() != panel["reference_close_cny"].notna()).any():
        raise ValueError("partial reference row")
    panel["ipo_date"] = panel["symbol"].map(normalized_ipo)
    if panel["ipo_date"].isna().any():
        raise ValueError("IPO metadata merge failure")

    panel = panel.sort_values(["symbol", "date"]).reset_index(drop=True)
    panel["listing_trade_rank"] = pd.Series(pd.NA, index=panel.index, dtype="Int64")
    rank_mask = (
        panel["tradable"]
        & (panel["ipo_date"] >= formal_start)
        & (panel["date"] >= panel["ipo_date"])
    )
    ranked = panel.loc[rank_mask, ["symbol", "date"]].copy()
    ranked["listing_trade_rank"] = ranked.groupby("symbol").cumcount() + 1
    panel.loc[ranked.index, "listing_trade_rank"] = ranked["listing_trade_rank"].astype("Int64")

    upper_values: list[bool] = []
    candidate_pct_values: list[float | None] = []
    for row in panel[[
        "symbol", "date", "isST", "tradable", "close", "reference_close_cny",
        "ipo_date", "listing_trade_rank",
    ]].itertuples(index=False):
        if not bool(row.tradable):
            candidate_pct_values.append(None)
            upper_values.append(False)
            continue
        rank = None if pd.isna(row.listing_trade_rank) else int(row.listing_trade_rank)
        special = (row.symbol, row.date) in specials
        pct = rule.limit_percent(
            row.symbol,
            row.date,
            bool(row.isST),
            ipo_date=row.ipo_date,
            listing_trade_rank=rank,
            special_no_limit=special,
        )
        candidate_pct_values.append(pct)
        upper_values.append(
            False if pct is None else rule.is_upper_limit(
                row.close, row.reference_close_cny, pct
            )
        )

    panel["candidate_limit_pct"] = candidate_pct_values
    panel["is_st"] = panel["isST"].astype(bool)
    panel["tradable"] = panel["tradable"].astype(bool)
    panel["upper_limit"] = pd.Series(upper_values, dtype=bool)

    if panel.loc[~panel["tradable"], "upper_limit"].any():
        raise ValueError("nontradable row cannot be upper limit")

    audit = {
        "artifact": "GP12_STATUS_FULL_PANEL_V1",
        "status": "PASS_FULL_STATUS_PANEL",
        "formal_window": [formal_start, formal_end],
        "lifecycle_rows": int(len(panel)),
        "symbols": int(panel["symbol"].nunique()),
        "tradable_rows": int(panel["tradable"].sum()),
        "nontradable_rows": int((~panel["tradable"]).sum()),
        "upper_limit_true_rows": int(panel["upper_limit"].sum()),
        "special_no_limit_dates_n": int(len(specials)),
        "duplicate_symbol_date_n": int(panel.duplicated(["symbol", "date"]).sum()),
        "historical_gp_v11_source_recovered": False,
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
    }
    columns = [
        "symbol", "date", "is_st", "tradable", "upper_limit", "ipo_date",
        "listing_trade_rank", "candidate_limit_pct",
    ]
    return panel[columns].copy(), audit
