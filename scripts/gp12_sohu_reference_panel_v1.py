from __future__ import annotations

from decimal import Decimal
from typing import Callable

import pandas as pd

import gp12_sohu_reference_v1 as reference

REFERENCE_COLUMNS = [
    "symbol",
    "date",
    "close",
    "change_cny",
    "pct_percent",
    "turnover_percent",
    "reference_close_cny",
    "source",
]


def _cents_equal(left: object, right: object) -> bool:
    return Decimal(str(left)).quantize(Decimal("0.01")) == Decimal(str(right)).quantize(Decimal("0.01"))


def validate_expected_axis(
    raw: pd.DataFrame,
    *,
    expected_symbol_n: int,
    expected_row_n: int,
) -> pd.DataFrame:
    required = {"symbol", "date", "close"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"missing expected-axis columns: {sorted(missing)}")
    axis = raw[["symbol", "date", "close"]].copy()
    axis["symbol"] = axis["symbol"].astype(str).map(reference.normalize_symbol)
    axis["date"] = axis["date"].astype(str).str[:10]
    axis["close"] = pd.to_numeric(axis["close"], errors="raise")
    duplicate_n = int(axis.duplicated(["symbol", "date"]).sum())
    if duplicate_n:
        raise ValueError(f"duplicate expected symbol-date rows: {duplicate_n}")
    symbol_n = int(axis["symbol"].nunique())
    if symbol_n != int(expected_symbol_n):
        raise ValueError(f"expected-axis symbol count {symbol_n} != {expected_symbol_n}")
    if len(axis) != int(expected_row_n):
        raise ValueError(f"expected-axis row count {len(axis)} != {expected_row_n}")
    if bool((axis["close"] <= 0).any()):
        raise ValueError("expected-axis contains nonpositive close")
    return axis.sort_values(["symbol", "date"]).reset_index(drop=True)


def collect_symbol(
    expected: pd.DataFrame,
    *,
    fetcher: Callable[..., list[dict]] = reference.fetch_symbol_reference,
    timeout: int = 20,
    retries: int = 3,
    delay: float = 0.05,
) -> tuple[pd.DataFrame, dict]:
    axis = expected[["symbol", "date", "close"]].copy()
    axis["symbol"] = axis["symbol"].astype(str).map(reference.normalize_symbol)
    axis["date"] = axis["date"].astype(str).str[:10]
    symbols = axis["symbol"].drop_duplicates().tolist()
    if len(symbols) != 1:
        raise ValueError(f"collect_symbol requires exactly one symbol; got {symbols}")
    symbol = symbols[0]
    axis = axis.sort_values("date").reset_index(drop=True)
    if axis.duplicated(["symbol", "date"]).any():
        raise ValueError(f"duplicate expected dates for {symbol}")
    rows = fetcher(
        symbol,
        str(axis["date"].min()),
        str(axis["date"].max()),
        timeout=timeout,
        retries=retries,
        delay=delay,
    )
    date_audit = reference.audit_expected_dates(symbol, axis["date"].tolist(), rows)
    if date_audit["status"] != "PASS_EXACT_DATES":
        raise ValueError(f"date axis mismatch for {symbol}: {date_audit}")
    frame = pd.DataFrame(rows, columns=REFERENCE_COLUMNS)
    frame["symbol"] = frame["symbol"].astype(str).map(reference.normalize_symbol)
    frame["date"] = frame["date"].astype(str).str[:10]
    check = axis.merge(
        frame[["symbol", "date", "close"]].rename(columns={"close": "source_close"}),
        on=["symbol", "date"],
        how="inner",
        validate="one_to_one",
    )
    mismatch = check[
        ~check.apply(lambda row: _cents_equal(row["close"], row["source_close"]), axis=1)
    ]
    if len(mismatch):
        raise ValueError(
            f"close mismatch for {symbol}: {mismatch.head(20).to_dict('records')}"
        )
    frame = frame.sort_values(["symbol", "date"]).reset_index(drop=True)
    audit = {
        "symbol": symbol,
        "expected_rows": int(len(axis)),
        "reference_rows": int(len(frame)),
        "close_mismatch_n": 0,
        "date_axis": date_audit,
        "status": "PASS_SYMBOL_REFERENCE",
    }
    return frame, audit


def merge_reference_frames(
    expected: pd.DataFrame,
    frames: list[pd.DataFrame],
) -> tuple[pd.DataFrame, dict]:
    axis = expected[["symbol", "date", "close"]].copy()
    axis["symbol"] = axis["symbol"].astype(str).map(reference.normalize_symbol)
    axis["date"] = axis["date"].astype(str).str[:10]
    if axis.duplicated(["symbol", "date"]).any():
        raise ValueError("duplicate expected symbol-date rows")
    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=REFERENCE_COLUMNS)
    if len(merged):
        merged["symbol"] = merged["symbol"].astype(str).map(reference.normalize_symbol)
        merged["date"] = merged["date"].astype(str).str[:10]
    duplicate_n = int(merged.duplicated(["symbol", "date"]).sum()) if len(merged) else 0
    if duplicate_n:
        raise ValueError(f"duplicate reference symbol-date rows: {duplicate_n}")
    actual_keys = merged[["symbol", "date"]] if len(merged) else pd.DataFrame(columns=["symbol", "date"])
    coverage = axis[["symbol", "date"]].merge(
        actual_keys,
        on=["symbol", "date"],
        how="outer",
        indicator=True,
    )
    missing = coverage[coverage["_merge"] == "left_only"]
    extra = coverage[coverage["_merge"] == "right_only"]
    if len(missing):
        raise ValueError(f"missing reference rows: {missing.head(20).to_dict('records')}")
    if len(extra):
        raise ValueError(f"extra reference rows: {extra.head(20).to_dict('records')}")
    check = axis.merge(
        merged[["symbol", "date", "close"]].rename(columns={"close": "source_close"}),
        on=["symbol", "date"],
        how="inner",
        validate="one_to_one",
    )
    close_mismatch = check[
        ~check.apply(lambda row: _cents_equal(row["close"], row["source_close"]), axis=1)
    ]
    if len(close_mismatch):
        raise ValueError(
            f"close mismatch in merged reference panel: {close_mismatch.head(20).to_dict('records')}"
        )
    merged = merged.sort_values(["symbol", "date"]).reset_index(drop=True)
    audit = {
        "expected_rows": int(len(axis)),
        "reference_rows": int(len(merged)),
        "symbol_n": int(merged["symbol"].nunique()) if len(merged) else 0,
        "duplicate_symbol_dates": 0,
        "missing_rows": 0,
        "extra_rows": 0,
        "close_mismatch_n": 0,
        "status": "PASS_EXACT_REFERENCE_PANEL",
    }
    return merged, audit
