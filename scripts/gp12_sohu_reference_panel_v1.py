from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path
from typing import Callable

import pandas as pd

import gp12_sohu_reference_v1 as reference

FORMAL_SYMBOL_N = 844
FORMAL_ROW_N = 1_011_607
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


def _read_raw_axis(
    raw_path: Path | str,
    *,
    expected_symbol_n: int,
    expected_row_n: int,
) -> pd.DataFrame:
    raw = pd.read_parquet(raw_path, columns=["symbol", "date", "close"])
    return validate_expected_axis(
        raw,
        expected_symbol_n=expected_symbol_n,
        expected_row_n=expected_row_n,
    )


def materialize_shard(
    raw_path: Path | str,
    *,
    shard_index: int,
    shard_count: int,
    out_dir: Path | str,
    workers: int = 2,
    timeout: int = 20,
    retries: int = 3,
    delay: float = 0.05,
    fetcher: Callable[..., list[dict]] = reference.fetch_symbol_reference,
    expected_symbol_n: int = FORMAL_SYMBOL_N,
    expected_row_n: int = FORMAL_ROW_N,
) -> dict:
    axis = _read_raw_axis(
        raw_path,
        expected_symbol_n=expected_symbol_n,
        expected_row_n=expected_row_n,
    )
    symbols = sorted(axis["symbol"].drop_duplicates().tolist())
    selected = reference.select_shard(symbols, shard_index, shard_count)
    expected_selected = axis[axis["symbol"].isin(selected)].copy()
    frames: list[pd.DataFrame] = []
    audits: list[dict] = []

    def one(symbol: str) -> tuple[pd.DataFrame, dict]:
        expected = expected_selected[expected_selected["symbol"] == symbol].copy()
        return collect_symbol(
            expected,
            fetcher=fetcher,
            timeout=timeout,
            retries=retries,
            delay=delay,
        )

    if workers <= 1:
        for position, symbol in enumerate(selected, 1):
            frame, audit = one(symbol)
            frames.append(frame)
            audits.append(audit)
            print(json.dumps({"progress": position, "total": len(selected), "symbol": symbol, "status": audit["status"]}, ensure_ascii=False), flush=True)
    else:
        with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
            futures = {pool.submit(one, symbol): symbol for symbol in selected}
            for position, future in enumerate(as_completed(futures), 1):
                symbol = futures[future]
                frame, audit = future.result()
                frames.append(frame)
                audits.append(audit)
                print(json.dumps({"progress": position, "total": len(selected), "symbol": symbol, "status": audit["status"]}, ensure_ascii=False), flush=True)

    merged, merge_audit = merge_reference_frames(expected_selected, frames)
    if merge_audit["symbol_n"] != len(selected):
        raise ValueError(f"shard symbol count {merge_audit['symbol_n']} != {len(selected)}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    parquet = out / f"SOHU_REFERENCE_SHARD_{shard_index:02d}_V1.parquet"
    audit_path = out / f"SOHU_REFERENCE_SHARD_{shard_index:02d}_AUDIT_V1.json"
    merged.to_parquet(parquet, index=False, compression="zstd")
    audits.sort(key=lambda row: row["symbol"])
    report = {
        "artifact": "SOHU_REFERENCE_SHARD_V1",
        "version": "1.0",
        "status": "PASS_SHARD_REFERENCE",
        "shard_index": int(shard_index),
        "shard_count": int(shard_count),
        "symbols_selected": len(selected),
        "symbol_list": selected,
        "expected_rows": int(len(expected_selected)),
        "reference_rows": int(len(merged)),
        "close_mismatch_n": 0,
        "merge_audit": merge_audit,
        "symbol_audits": audits,
        "formal_binding_allowed": False,
        "historical_gp_v11_source_recovered": False,
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
    }
    audit_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report


def merge_shard_artifacts(
    raw_path: Path | str,
    *,
    shards_root: Path | str,
    out_dir: Path | str,
    expected_symbol_n: int = FORMAL_SYMBOL_N,
    expected_row_n: int = FORMAL_ROW_N,
    expected_shard_count: int = 8,
) -> dict:
    axis = _read_raw_axis(
        raw_path,
        expected_symbol_n=expected_symbol_n,
        expected_row_n=expected_row_n,
    )
    root = Path(shards_root)
    audit_files = sorted(root.rglob("SOHU_REFERENCE_SHARD_*_AUDIT_V1.json"))
    parquet_files = sorted(root.rglob("SOHU_REFERENCE_SHARD_*_V1.parquet"))
    if len(audit_files) != int(expected_shard_count):
        raise ValueError(f"expected {expected_shard_count} shard audits; got {len(audit_files)}")
    if len(parquet_files) != int(expected_shard_count):
        raise ValueError(f"expected {expected_shard_count} shard parquets; got {len(parquet_files)}")

    reports = [json.loads(path.read_text(encoding="utf-8")) for path in audit_files]
    for report in reports:
        if report.get("status") != "PASS_SHARD_REFERENCE":
            raise ValueError(f"non-PASS shard report: {report.get('shard_index')}")
        if int(report.get("shard_count", -1)) != int(expected_shard_count):
            raise ValueError("shard count contract mismatch")
    shard_ids = sorted(int(report["shard_index"]) for report in reports)
    if shard_ids != list(range(int(expected_shard_count))):
        raise ValueError(f"incomplete shard partition: {shard_ids}")
    symbol_lists = [symbol for report in reports for symbol in report.get("symbol_list", [])]
    if len(symbol_lists) != len(set(symbol_lists)):
        raise ValueError("duplicate symbols across shard reports")
    if sorted(symbol_lists) != sorted(axis["symbol"].drop_duplicates().tolist()):
        raise ValueError("shard symbol partition does not cover expected axis")

    frames = [pd.read_parquet(path) for path in parquet_files]
    merged, merge_audit = merge_reference_frames(axis, frames)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    parquet = out / "SOHU_REFERENCE_FULL_V1.parquet"
    audit_path = out / "SOHU_REFERENCE_FULL_AUDIT_V1.json"
    merged.to_parquet(parquet, index=False, compression="zstd")
    report = {
        "artifact": "SOHU_REFERENCE_FULL_V1",
        "version": "1.0",
        "status": "PASS_FULL_REFERENCE_PANEL",
        "shard_count": int(expected_shard_count),
        "symbol_n": int(merge_audit["symbol_n"]),
        "expected_rows": int(expected_row_n),
        "reference_rows": int(len(merged)),
        "duplicate_symbol_dates": 0,
        "missing_rows": 0,
        "extra_rows": 0,
        "close_mismatch_n": 0,
        "merge_audit": merge_audit,
        "formal_binding_allowed": False,
        "historical_gp_v11_source_recovered": False,
        "model_freeze_allowed": False,
        "oos_metrics_allowed": False,
    }
    audit_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    shard = sub.add_parser("shard")
    shard.add_argument("--raw", required=True)
    shard.add_argument("--shard-index", type=int, required=True)
    shard.add_argument("--shard-count", type=int, required=True)
    shard.add_argument("--out-dir", required=True)
    shard.add_argument("--workers", type=int, default=2)
    shard.add_argument("--timeout", type=int, default=20)
    shard.add_argument("--retries", type=int, default=3)
    shard.add_argument("--delay", type=float, default=0.05)

    merge = sub.add_parser("merge")
    merge.add_argument("--raw", required=True)
    merge.add_argument("--shards-root", required=True)
    merge.add_argument("--out-dir", required=True)
    merge.add_argument("--expected-shard-count", type=int, default=8)

    args = parser.parse_args()
    if args.command == "shard":
        report = materialize_shard(
            args.raw,
            shard_index=args.shard_index,
            shard_count=args.shard_count,
            out_dir=args.out_dir,
            workers=args.workers,
            timeout=args.timeout,
            retries=args.retries,
            delay=args.delay,
        )
    else:
        report = merge_shard_artifacts(
            args.raw,
            shards_root=args.shards_root,
            out_dir=args.out_dir,
            expected_shard_count=args.expected_shard_count,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
