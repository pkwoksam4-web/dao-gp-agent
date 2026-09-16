from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

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


def _prepare_special_keys(
    special_keys: set[tuple[str, str]] | list[tuple[str, str]],
    lifecycle_keys: set[tuple[str, str]],
) -> set[tuple[str, str]]:
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


def load_special_no_limit_evidence(doc: dict, *, expected_entry_count: int) -> set[tuple[str, str]]:
    if not isinstance(doc, dict):
        raise ValueError("special evidence must be an object")
    if doc.get("artifact") != "GP12_STATUS_SPECIAL_NO_LIMIT_EVIDENCE_V1":
        raise ValueError("special evidence artifact mismatch")
    entries = doc.get("entries")
    if not isinstance(entries, list):
        raise ValueError("special evidence entries must be a list")
    if doc.get("entry_count") != len(entries) or len(entries) != int(expected_entry_count):
        raise ValueError("special evidence entry count mismatch")
    keys: set[tuple[str, str]] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("invalid special evidence entry")
        key = (_normalize_symbol(entry.get("symbol")), _normalize_date(entry.get("date")))
        if key in keys:
            raise ValueError(f"duplicate special evidence key: {key}")
        if entry.get("no_price_limit") is not True:
            raise ValueError(f"special evidence does not prove no limit: {key}")
        if not str(entry.get("event_type") or "").strip():
            raise ValueError(f"special evidence missing event type: {key}")
        if not str(entry.get("source_url") or "").startswith(("https://", "http://")):
            raise ValueError(f"special evidence missing source URL: {key}")
        keys.add(key)
    return keys


def crosscheck_upper_limit_truth(
    panel: pd.DataFrame,
    truth: pd.DataFrame,
    special_no_limit_keys: set[tuple[str, str]] | list[tuple[str, str]],
    *,
    require_exact: bool = False,
) -> dict:
    panel_required = {"symbol", "date", "tradable", "limit_pct_percent", "limit_price_cny", "upper_limit"}
    missing = panel_required - set(panel.columns)
    if missing:
        raise ValueError(f"missing panel truth-crosscheck columns: {sorted(missing)}")
    truth_symbol = "symbol" if "symbol" in truth.columns else "code" if "code" in truth.columns else None
    if truth_symbol is None:
        raise ValueError("truth symbol/code column missing")
    truth_required = {truth_symbol, "date", "close", "high_limit"}
    missing_truth = truth_required - set(truth.columns)
    if missing_truth:
        raise ValueError(f"missing truth columns: {sorted(missing_truth)}")

    candidate = panel[["symbol", "date", "tradable", "limit_pct_percent", "limit_price_cny", "upper_limit"]].copy()
    candidate["symbol"] = candidate["symbol"].map(_normalize_symbol)
    candidate["date"] = candidate["date"].map(_normalize_date)
    if candidate.duplicated(["symbol", "date"]).any():
        raise ValueError("duplicate panel key in truth crosscheck")

    observed = truth[[truth_symbol, "date", "close", "high_limit"]].copy().rename(columns={truth_symbol: "symbol"})
    observed["symbol"] = observed["symbol"].map(_normalize_symbol)
    observed["date"] = observed["date"].map(_normalize_date)
    observed["close"] = pd.to_numeric(observed["close"], errors="raise")
    observed["high_limit"] = pd.to_numeric(observed["high_limit"], errors="raise")
    if observed.duplicated(["symbol", "date"]).any():
        raise ValueError("duplicate truth key")

    joined = observed.merge(candidate, on=["symbol", "date"], how="left", validate="one_to_one", indicator=True)
    if not (joined["_merge"] == "both").all():
        missing_keys = joined.loc[joined["_merge"] != "both", ["symbol", "date"]]
        raise ValueError(f"truth key missing from panel: {missing_keys.head(20).to_dict('records')}")
    if not joined["tradable"].astype(bool).all():
        bad = joined.loc[~joined["tradable"].astype(bool), ["symbol", "date"]]
        raise ValueError(f"truth overlap contains nontradable candidate row: {bad.head(20).to_dict('records')}")

    special = {(_normalize_symbol(symbol), _normalize_date(trade_date)) for symbol, trade_date in special_no_limit_keys}
    special_mask = pd.Series(
        [(symbol, trade_date) in special for symbol, trade_date in zip(joined["symbol"], joined["date"])],
        index=joined.index,
        dtype=bool,
    )
    truth_no_limit = (joined["high_limit"] >= 999999.0) | special_mask
    candidate_no_limit = joined["limit_pct_percent"].isna()
    no_limit_mismatch = truth_no_limit != candidate_no_limit

    candidate_limit = pd.to_numeric(joined["limit_price_cny"], errors="coerce")
    price_equal = pd.Series(
        [
            False if pd.isna(left) else _cents_equal(left, right)
            for left, right in zip(candidate_limit, joined["high_limit"])
        ],
        index=joined.index,
        dtype=bool,
    )
    price_match = (truth_no_limit & candidate_no_limit) | ((~truth_no_limit) & (~candidate_no_limit) & price_equal)

    truth_upper = pd.Series(
        [
            (not bool(no_limit)) and _cents_equal(close, high_limit)
            for close, high_limit, no_limit in zip(joined["close"], joined["high_limit"], truth_no_limit)
        ],
        index=joined.index,
        dtype=bool,
    )
    candidate_upper = joined["upper_limit"].astype(bool)
    boolean_match = truth_upper == candidate_upper

    summary = {
        "status": "PASS_EXACT_TRUTH_CROSSCHECK" if (not no_limit_mismatch.any() and price_match.all() and boolean_match.all()) else "REVIEW_TRUTH_CROSSCHECK",
        "overlap_rows": int(len(joined)),
        "overlap_symbols": int(joined["symbol"].nunique()),
        "special_overlap_rows": int(special_mask.sum()),
        "truth_no_limit_n": int(truth_no_limit.sum()),
        "candidate_no_limit_n": int(candidate_no_limit.sum()),
        "no_limit_mismatch_n": int(no_limit_mismatch.sum()),
        "price_mismatch_n": int((~price_match).sum()),
        "boolean_mismatch_n": int((~boolean_match).sum()),
    }
    if require_exact and summary["status"] != "PASS_EXACT_TRUTH_CROSSCHECK":
        raise ValueError(f"truth crosscheck mismatch: {summary}")
    return summary


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def materialize_status_artifact(
    panel: pd.DataFrame,
    audit: dict,
    out_dir: Path | str,
    *,
    metadata: dict | None = None,
) -> dict:
    if audit.get("status") != "PASS_EXACT_STATUS_PANEL":
        raise ValueError("cannot materialize non-passing status panel")
    if panel.duplicated(["symbol", "date"]).any():
        raise ValueError("cannot materialize duplicate status panel")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    panel_path = out / "GP12_STATUS_PANEL_V1.parquet"
    audit_path = out / "GP12_STATUS_PANEL_AUDIT_V1.json"

    serial = panel.copy()
    if "listing_trade_rank" in serial.columns:
        serial["listing_trade_rank"] = pd.to_numeric(serial["listing_trade_rank"], errors="coerce").astype("Int64")
    for column in ["reference_close_cny", "limit_pct_percent", "limit_price_cny"]:
        if column in serial.columns:
            serial[column] = pd.to_numeric(serial[column], errors="coerce").astype("Float64")
    for column in ["is_st", "tradable", "special_no_limit", "upper_limit"]:
        if column in serial.columns:
            serial[column] = serial[column].astype(bool)
    serial.to_parquet(panel_path, index=False)
    panel_sha = _sha256_file(panel_path)

    doc = dict(metadata or {})
    doc.update(audit)
    doc.update(
        {
            "artifact": "GP12_STATUS_PANEL_AUDIT_V1",
            "version": "1.0",
            "panel_file": panel_path.name,
            "panel_sha256": panel_sha,
            "formal_binding_allowed": False,
            "historical_gp_v11_source_recovered": False,
            "model_freeze_allowed": False,
            "oos_metrics_allowed": False,
        }
    )
    audit_payload_sha = _canonical_sha256(doc)
    doc["audit_sha256"] = audit_payload_sha
    audit_path.write_text(
        json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return {
        "panel_path": str(panel_path),
        "audit_path": str(audit_path),
        "panel_sha256": panel_sha,
        "audit_sha256": audit_payload_sha,
        "audit_file_sha256": _sha256_file(audit_path),
    }
