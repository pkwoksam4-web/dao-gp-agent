from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

FORMAL_START = "20200601"
FORMAL_END = "20260417"
SW2014_LAST = "20211210"
SW2021_FIRST = "20211213"
NEW_SW2021_L1 = {"801950.SI","801960.SI","801970.SI","801980.SI"}
SW2014_ONLY_L1 = {"801020.SI"}


def read_calendar(path: Path) -> list[str]:
    frame = pd.read_csv(path)
    raw = None
    for col in ("trade_date","cal_date","date"):
        if col in frame.columns:
            raw = frame[col]
            break
    if raw is None:
        raise ValueError("calendar missing trade_date/cal_date/date")
    if "is_open" in frame.columns:
        frame = frame.loc[frame["is_open"].astype(str).isin(["1","1.0","True","true"])].copy()
        for col in ("trade_date","cal_date","date"):
            if col in frame.columns:
                raw = frame[col]
                break
    dates = (
        pd.to_datetime(raw.astype(str), errors="coerce")
        .dt.strftime("%Y%m%d")
        .dropna()
        .tolist()
    )
    dates = sorted(set(d for d in dates if FORMAL_START <= d <= FORMAL_END))
    if len(dates) != 1426:
        raise ValueError(f"formal calendar expected 1426 dates, got {len(dates)}")
    if dates[0] != FORMAL_START or dates[-1] != FORMAL_END:
        raise ValueError((dates[0], dates[-1]))
    return dates


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def prepare_root(taxonomy: Path, formal_calendar: Path, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    payload = json.loads(taxonomy.read_text(encoding="utf-8"))
    codes = payload["required_industry_codes"]
    pd.DataFrame(
        {"index_code": codes, "classification_source": ["SW2021"] * len(codes)}
    ).to_csv(root / "industry_classify.csv", index=False)
    dates = read_calendar(formal_calendar)
    pd.DataFrame({"cal_date": dates, "is_open": [1] * len(dates)}).to_csv(
        root / "trade_cal.csv", index=False
    )
    (root / "dao2_prepared.json").write_text(
        json.dumps(
            {
                "required_industry_codes": codes,
                "required_industry_code_count": len(codes),
                "formal_start": dates[0],
                "formal_end": dates[-1],
                "formal_days": len(dates),
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


def export_membership(root: Path, out: Path, formal_calendar: Path) -> dict[str, Any]:
    membership_path = root / "industry_membership.parquet"
    raw_path = root / "industry_membership_sw2021.parquet"
    unresolved_path = root / "industry_membership_unresolved.parquet"
    if not membership_path.exists() or not raw_path.exists() or not unresolved_path.exists():
        return {
            "status": "BLOCKED_MEMBERSHIP_BYTES_ABSENT",
            "membership_bytes_present": False,
        }

    m = pd.read_parquet(membership_path).copy()
    r = pd.read_parquet(raw_path).copy()
    u = pd.read_parquet(unresolved_path).copy()
    for frame in (m, r, u):
        for col in ("in_date","out_date"):
            if col in frame.columns:
                frame[col] = frame[col].astype("string").str.replace(".0","",regex=False)

    errors: list[str] = []
    if not m.empty:
        p = m[m["taxonomy_version"].eq("SW2014_projected")]
        n = m[m["taxonomy_version"].eq("SW2021")]
        if not p.empty:
            if p["out_date"].fillna("").gt(SW2014_LAST).any():
                errors.append("projected_SW2014_extends_after_20211210")
            if p["in_date"].gt(SW2014_LAST).any():
                errors.append("projected_SW2014_starts_after_20211210")
        if not n.empty and n["in_date"].lt(SW2021_FIRST).any():
            errors.append("native_SW2021_starts_before_20211213")

    # Exact symbol-date overlaps are forbidden within a taxonomy segment.
    for ts_code, g in m.groupby("ts_code"):
        rows = g.sort_values(["in_date","out_date"]).to_dict("records")
        for i, a in enumerate(rows):
            a0 = str(a["in_date"])
            a1 = str(a.get("out_date") or "99991231")
            for b in rows[i+1:]:
                b0 = str(b["in_date"])
                b1 = str(b.get("out_date") or "99991231")
                if max(a0,b0) <= min(a1,b1) and str(a["industry_code"]) != str(b["industry_code"]):
                    # Taxonomy boundary itself is allowed only across the 20211210/20211213 gap.
                    ta, tb = str(a.get("taxonomy_version")), str(b.get("taxonomy_version"))
                    if {ta,tb} != {"SW2014_projected","SW2021"}:
                        errors.append(f"overlap:{ts_code}:{a0}:{a1}:{b0}:{b1}")

    out.mkdir(parents=True, exist_ok=True)
    m.to_csv(out / "industry_membership.csv.gz", index=False, compression="gzip")
    r.to_csv(out / "industry_membership_sw2021.csv.gz", index=False, compression="gzip")
    u.to_csv(out / "industry_membership_unresolved.csv", index=False)
    u.to_json(out / "industry_membership_unresolved.json", orient="records", force_ascii=False, indent=2)

    dates = read_calendar(formal_calendar)
    required_rows: list[dict[str,str]] = []
    for d in dates:
        active = m.loc[
            (m["in_date"].astype(str) <= d)
            & (
                m["out_date"].isna()
                | m["out_date"].astype(str).isin(["","<NA>","nan","None"])
                | (m["out_date"].astype(str) >= d)
            )
        ]
        for code in sorted(active["industry_code"].dropna().astype(str).unique()):
            required_rows.append({"industry_code": code, "trade_date": d})
    req = pd.DataFrame(required_rows).drop_duplicates()
    req.to_csv(out / "formal_required_sector_keys.csv.gz", index=False, compression="gzip")

    unresolved_records = u.to_dict("records")
    return {
        "status": "PASS_MEMBERSHIP_BYTES_MATERIALIZED" if not errors and u.empty else "BLOCKED_UNRESOLVED_OR_SWITCH",
        "membership_bytes_present": True,
        "raw_rows": int(len(r)),
        "effective_rows": int(len(m)),
        "unresolved_rows": int(len(u)),
        "unresolved_records": unresolved_records,
        "switch_exact": {
            "sw2014_last": SW2014_LAST,
            "sw2021_first": SW2021_FIRST,
            "errors": errors,
            "pass": not errors,
        },
        "formal_required_sector_keys": int(len(req)),
        "sha256": {
            "industry_membership.parquet": sha256(membership_path),
            "industry_membership_sw2021.parquet": sha256(raw_path),
            "industry_membership_unresolved.parquet": sha256(unresolved_path),
        },
    }


def patch_series_with_tushare(root: Path, formal_calendar: Path) -> dict[str, Any]:
    token = os.environ.get("TUSHARE_TOKEN","").strip()
    if not token:
        return {"status":"SKIPPED_NO_TUSHARE_TOKEN","patched_rows":0,"attempts":0,"errors":[]}
    try:
        import tushare as ts
    except Exception as exc:
        return {"status":"BLOCKED_TUSHARE_IMPORT","patched_rows":0,"attempts":0,"errors":[repr(exc)]}

    dates = set(read_calendar(formal_calendar))
    cache = root / "industry_by_code"
    manifest_path = root / "industry_source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"series":{}}
    codes = json.loads((root / "dao2_prepared.json").read_text(encoding="utf-8"))["required_industry_codes"]
    missing_by_date: dict[str,set[str]] = {}
    for code in codes:
        p = cache / f"{code}.parquet"
        present: set[str] = set()
        if p.exists():
            f = pd.read_parquet(p)
            present = set(f["trade_date"].astype(str))
        for d in dates - present:
            # Do not request impossible taxonomy-era dates.
            if code in NEW_SW2021_L1 and d < SW2021_FIRST:
                continue
            if code in SW2014_ONLY_L1 and d > SW2014_LAST:
                continue
            missing_by_date.setdefault(d,set()).add(code)

    pro = ts.pro_api(token)
    errors: list[str] = []
    patched = 0
    attempts = 0
    for d in sorted(missing_by_date):
        need = missing_by_date[d]
        attempts += 1
        try:
            day = pro.sw_daily(trade_date=d)
        except Exception as exc:
            errors.append(f"{d}:all:{exc}")
            day = pd.DataFrame()
        if not day.empty and "ts_code" in day.columns:
            day = day.rename(columns={"ts_code":"industry_code"})
        # One Tushare request per missing trade date only. Never fall back to one
        # request per code: that creates rate-limit pressure without improving
        # provenance. Any code absent from the same-day payload remains a gap.
        for code in sorted(need):
            row = day.loc[day.get("industry_code", pd.Series(dtype=str)).astype(str).eq(code)] if not day.empty else pd.DataFrame()
            if row.empty:
                continue
            keep = ["industry_code","trade_date","open","high","low","close","vol","amount"]
            row = row[keep].copy()
            p = cache / f"{code}.parquet"
            old = pd.read_parquet(p) if p.exists() else pd.DataFrame(columns=keep)
            merged = pd.concat([old,row],ignore_index=True).drop_duplicates(["industry_code","trade_date"],keep="last")
            merged = merged.sort_values("trade_date")
            merged.to_parquet(p,index=False,compression="zstd")
            patched += len(row)
            item = manifest.setdefault("series",{}).setdefault(code,{})
            item["same_date_tushare_gap_patch"] = True

    manifest.setdefault("providers",[])
    if patched and "tushare" not in manifest["providers"]:
        manifest["providers"].append("tushare")
    manifest["providers"] = sorted(set(manifest["providers"]))
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {
        "status":"PATCH_ATTEMPTED",
        "patched_rows":int(patched),
        "attempts":int(attempts),
        "errors":errors[:100],
        "error_count":len(errors),
    }


def audit_series(root: Path, formal_calendar: Path, membership_out: Path, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    dates = set(read_calendar(formal_calendar))
    cache = root / "industry_by_code"
    manifest_path = root / "industry_source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"series":{}}
    codes = json.loads((root / "dao2_prepared.json").read_text(encoding="utf-8"))["required_industry_codes"]

    frames: list[pd.DataFrame] = []
    code_report: dict[str,Any] = {}
    for code in codes:
        p = cache / f"{code}.parquet"
        if not p.exists():
            code_report[code] = {"present":False,"rows":0}
            continue
        f = pd.read_parquet(p).copy()
        f["trade_date"] = f["trade_date"].astype(str)
        f = f.loc[f["trade_date"].isin(dates)].copy()
        if f.empty:
            code_report[code] = {"present":True,"rows":0}
            continue
        provider = manifest.get("series",{}).get(code,{}).get("provider","unknown")
        # If a code was patched, row-level exact provider is reconstructed conservatively:
        # original AKShare dates remain akshare, dates absent from original manifest gap list and now present may be tushare.
        original_missing = set(manifest.get("series",{}).get(code,{}).get("missing_expected_dates",[]) or [])
        f["source_provider"] = [
            "tushare" if d in original_missing and manifest.get("series",{}).get(code,{}).get("same_date_tushare_gap_patch") else provider
            for d in f["trade_date"]
        ]
        f["source_trade_date"] = f["trade_date"]
        f["fill_method"] = "NONE"
        f["price_basis"] = "SW_INDUSTRY_INDEX_CLOSE_LEVEL"
        frames.append(f[["industry_code","trade_date","close","source_provider","source_trade_date","fill_method","price_basis"]])
        code_report[code] = {
            "present":True,
            "rows":int(len(f)),
            "first":str(f["trade_date"].min()),
            "last":str(f["trade_date"].max()),
        }

    panel = pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    panel = panel.drop_duplicates(["industry_code","trade_date"],keep="last")
    panel.to_csv(out / "sector_series_formal.csv.gz",index=False,compression="gzip")

    req_path = membership_out / "formal_required_sector_keys.csv.gz"
    if req_path.exists():
        req = pd.read_csv(req_path,dtype=str)
        required = set(map(tuple,req[["industry_code","trade_date"]].itertuples(index=False,name=None)))
        observed = set(map(tuple,panel[["industry_code","trade_date"]].astype(str).itertuples(index=False,name=None)))
        missing = sorted(required-observed)
        extra = sorted(observed-required)
        exact_mode = True
    else:
        required = set()
        observed = set(map(tuple,panel[["industry_code","trade_date"]].astype(str).itertuples(index=False,name=None))) if not panel.empty else set()
        missing = []
        extra = []
        exact_mode = False

    same_date_ok = bool(panel.empty or (panel["trade_date"].astype(str) == panel["source_trade_date"].astype(str)).all())
    no_fill_ok = bool(panel.empty or panel["fill_method"].eq("NONE").all())
    finite_close_ok = bool(panel.empty or (pd.to_numeric(panel["close"],errors="coerce").notna() & (pd.to_numeric(panel["close"],errors="coerce")>0)).all())
    exact_ok = exact_mode and not missing and same_date_ok and no_fill_ok and finite_close_ok

    pd.DataFrame(missing,columns=["industry_code","trade_date"]).to_csv(out / "missing_required_sector_keys.csv",index=False)
    return {
        "status":"PASS_SERIES_EXACT" if exact_ok else ("BLOCKED_NO_MEMBERSHIP_REQUIRED_KEYS" if not exact_mode else "BLOCKED_SERIES_GAPS"),
        "materialized_code_count":sum(1 for x in code_report.values() if x.get("present")),
        "required_code_count":len(codes),
        "panel_rows":int(len(panel)),
        "exact_membership_key_mode":exact_mode,
        "required_keys":len(required),
        "observed_keys":len(observed),
        "missing_required_keys":len(missing),
        "missing_required_key_sample":[{"industry_code":a,"trade_date":b} for a,b in missing[:50]],
        "same_date_provenance":same_date_ok,
        "fill_method_none":no_fill_ok,
        "finite_positive_close":finite_close_ok,
        "price_basis":"SW_INDUSTRY_INDEX_CLOSE_LEVEL",
        "price_basis_binding":"CANDIDATE_EXPLICIT_ALIAS_NOT_HISTORICAL_GP_IDENTITY",
        "code_report":code_report,
    }



SEVEN_859622_SYMBOLS = ["002554","300157","300164","300191","600339","600583","603727"]
CANONICAL_SW_XLS_URL = "https://www.swsresearch.com/swindex/pdf/SwClass2021/StockClassifyUse_stock.xls"
CANONICAL_SW_XLS_SHA256 = "1a181c4a7aa1db22ea3c52233221d9d70b731ed6cb0fd7c9bbc80f6b0c066742"
FORMAL_RAW_EXPECTED_ROWS = 1_011_607
FORMAL_RAW_ARTIFACT = {
    "run_id": 34192233633,
    "artifact_id": 10042614517,
    "artifact_name": "gp-sohu-full-raw-v482-reaudit",
    "artifact_digest_sha256": "cee7e91f1fda605f7c3bdf41c3f4a7796feeae83f8c3702e50900e6af3fa9550",
}


def _six(value: object) -> str:
    text = str(value).strip().replace(".0", "")
    return text[:6].zfill(6)


def _yyyymmdd(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.strftime("%Y%m%d")


def _read_old_index_map(path: Path) -> dict[str, str]:
    frame = pd.read_csv(path, sep=r"\s+", dtype=str, encoding="utf-8-sig")
    frame["code"] = frame["code"].astype(str).str.zfill(6)
    frame["index_code"] = frame["index_code"].astype(str)
    return dict(zip(frame["code"], frame["index_code"].map(lambda x: x if x.endswith(".SI") else x + ".SI")))


def _read_hierarchy(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    for col in ("l3_code", "l2_code", "l1_code"):
        frame[col] = frame[col].astype(str).str.replace(".0", "", regex=False).str.zfill(6)
    return frame


def official_membership(
    *,
    sw_xls: Path,
    formal_raw: Path,
    taxonomy: Path,
    sw2014_hierarchy: Path,
    sw2014_index_map: Path,
    sw2021_hierarchy: Path,
    sw2021_l1: Path,
    sw2021_l3: Path,
    out: Path,
) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)

    raw_xls_sha = sha256(sw_xls)
    raw_xls_bytes = sw_xls.stat().st_size
    if raw_xls_sha != CANONICAL_SW_XLS_SHA256:
        raise ValueError(f"canonical SW XLS sha mismatch: {raw_xls_sha}")
    if raw_xls_bytes != 1_165_824:
        raise ValueError(f"canonical SW XLS byte count mismatch: {raw_xls_bytes}")

    hist = pd.read_excel(sw_xls, dtype={"股票代码": "str", "行业代码": "str"})
    hist = hist.rename(
        columns={
            "股票代码": "symbol",
            "计入日期": "start_date",
            "行业代码": "classification_code",
            "更新日期": "update_time",
        }
    )
    required_hist = {"symbol", "start_date", "classification_code"}
    if not required_hist.issubset(hist.columns):
        raise ValueError(f"SW XLS missing columns: {sorted(required_hist - set(hist.columns))}")
    hist["symbol"] = hist["symbol"].map(_six)
    hist["start_date"] = _yyyymmdd(hist["start_date"])
    hist["classification_code"] = hist["classification_code"].astype(str).str.replace(".0", "", regex=False).str.zfill(6)
    if "update_time" in hist.columns:
        hist["update_time"] = _yyyymmdd(hist["update_time"])
    else:
        hist["update_time"] = pd.NA
    hist = hist.dropna(subset=["symbol", "start_date", "classification_code"]).copy()
    hist = hist.sort_values(["symbol", "start_date"]).reset_index(drop=True)
    hist_dup = int(hist.duplicated(["symbol", "start_date"], keep=False).sum())
    first_official_start = hist.groupby("symbol")["start_date"].min().to_dict()

    taxonomy_payload = json.loads(taxonomy.read_text(encoding="utf-8"))
    required_codes = set(map(str, taxonomy_payload["required_industry_codes"]))
    bridge = {str(k): str(v) for k, v in taxonomy_payload.get("explicit_l3_bridge", {}).items()}

    old_h = _read_hierarchy(sw2014_hierarchy)
    old_l3_to_l1 = dict(zip(old_h["l3_code"], old_h["l1_code"]))
    old_index = _read_old_index_map(sw2014_index_map)

    new_h = _read_hierarchy(sw2021_hierarchy)
    new_l3_to_l1 = dict(zip(new_h["l3_code"], new_h["l1_code"]))

    new_l1 = pd.read_csv(sw2021_l1, dtype=str, encoding="utf-8-sig")
    new_l1["industry_code"] = new_l1["industry_code"].astype(str).str.replace(".0", "", regex=False).str.zfill(6)
    new_l1_index = dict(zip(new_l1["industry_code"], new_l1["index_code"].astype(str)))

    new_l3 = pd.read_csv(sw2021_l3, dtype=str, encoding="utf-8-sig")
    new_l3["industry_code"] = new_l3["industry_code"].astype(str).str.replace(".0", "", regex=False).str.zfill(6)
    new_l3_idx = dict(zip(new_l3["industry_code"], new_l3["index_code"].astype(str)))

    # Resolve the exact seven 859622 rows from official history plus fixed taxonomy tables.
    seven_evidence: list[dict[str, Any]] = []
    special_bridge: dict[tuple[str, str], str] = {}
    for sym in SEVEN_859622_SYMBOLS:
        g = hist.loc[hist["symbol"].eq(sym)].sort_values("start_date").reset_index(drop=True)
        new_rows = g.loc[g["classification_code"].eq("750202") & g["start_date"].le(SW2014_LAST)]
        if len(new_rows) != 1:
            raise ValueError(f"{sym}: expected exactly one pre-switch 750202 row, got {len(new_rows)}")
        row = new_rows.iloc[0]
        pos = int(g.index[g["start_date"].eq(row["start_date"]) & g["classification_code"].eq("750202")][0])
        prev = g.iloc[pos - 1] if pos > 0 else None
        if prev is None or str(prev["classification_code"]) != "210401":
            raise ValueError(f"{sym}: previous official classification is not 210401")
        if old_l3_to_l1.get("210401") != "210000":
            raise ValueError("SW2014 hierarchy does not map 210401 -> 210000")
        if old_index.get("210000") != "801020.SI":
            raise ValueError("SW2014 index map does not map 210000 -> 801020.SI")
        if new_l3_idx.get("750202") != "859622.SI":
            raise ValueError("SW2021 L3 table does not map 750202 -> 859622.SI")
        if new_l3_to_l1.get("750202") != "750000":
            raise ValueError("SW2021 hierarchy does not map 750202 -> 750000")
        if new_l1_index.get("750000") != "801960.SI":
            raise ValueError("SW2021 L1 table does not map 750000 -> 801960.SI")
        special_bridge[(sym, "750202")] = "801020.SI"
        next_start = None
        later = g.loc[g["start_date"].gt(str(row["start_date"]))]
        if not later.empty:
            next_start = str(later.iloc[0]["start_date"])
        seven_evidence.append(
            {
                "symbol": sym,
                "effective_date_interval": ["20210730", SW2014_LAST],
                "official_previous_classification": {
                    "start_date": str(prev["start_date"]),
                    "classification_code": "210401",
                    "update_time": None if pd.isna(prev["update_time"]) else str(prev["update_time"]),
                },
                "official_migration_classification": {
                    "start_date": str(row["start_date"]),
                    "classification_code": "750202",
                    "update_time": None if pd.isna(row["update_time"]) else str(row["update_time"]),
                    "next_start_date": next_start,
                },
                "sw2014": {
                    "l3_classification_code": "210401",
                    "l3_name": "油气钻采服务",
                    "l1_classification_code": "210000",
                    "l1_name": "采掘",
                    "l1_index_code": "801020.SI",
                },
                "sw2021_migration": {
                    "classification_code": "750202",
                    "l3_index_code": "859622.SI",
                    "l3_name": "油气及炼化工程",
                    "l1_classification_code": "750000",
                    "l1_name": "石油石化",
                    "l1_index_code": "801960.SI",
                },
                "pre_switch_resolution": "801020.SI",
                "post_switch_native_l1": "801960.SI",
                "raw_xls_sha256": raw_xls_sha,
                "raw_xls_source_url": CANONICAL_SW_XLS_URL,
            }
        )

    formal = pd.read_parquet(formal_raw).copy()
    required_raw = {"symbol", "date"}
    if not required_raw.issubset(formal.columns):
        raise ValueError(f"Formal RAW missing columns: {sorted(required_raw - set(formal.columns))}")
    formal["symbol_full"] = formal["symbol"].astype(str).str.upper()
    formal["symbol"] = formal["symbol_full"].str[:6]
    formal["trade_date"] = _yyyymmdd(formal["date"])
    formal = formal.dropna(subset=["symbol", "trade_date"]).copy()
    formal = formal[["symbol_full", "symbol", "trade_date"]].sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    duplicate_formal = int(formal.duplicated(["symbol_full", "trade_date"], keep=False).sum())
    if len(formal) != FORMAL_RAW_EXPECTED_ROWS:
        raise ValueError(f"Formal RAW row mismatch: {len(formal)} != {FORMAL_RAW_EXPECTED_ROWS}")
    if duplicate_formal:
        raise ValueError(f"Formal RAW duplicate symbol-date rows: {duplicate_formal}")

    mapped_parts: list[pd.DataFrame] = []
    no_history_symbols: list[str] = []
    for sym, trades in formal.groupby("symbol", sort=True):
        events = hist.loc[hist["symbol"].eq(sym), ["start_date", "classification_code", "update_time"]].copy()
        if events.empty:
            z = trades.copy()
            z["classification_start_date"] = pd.NA
            z["classification_code"] = pd.NA
            z["classification_update_time"] = pd.NA
            mapped_parts.append(z)
            no_history_symbols.append(sym)
            continue
        left = trades.sort_values("trade_date").copy()
        right = events.rename(
            columns={"start_date": "classification_start_date", "update_time": "classification_update_time"}
        ).sort_values("classification_start_date")
        left["_trade_key"] = left["trade_date"].astype(int)
        right["_event_key"] = right["classification_start_date"].astype(int)
        z = pd.merge_asof(
            left,
            right,
            left_on="_trade_key",
            right_on="_event_key",
            direction="backward",
            allow_exact_matches=True,
        )
        z = z.drop(columns=["_trade_key", "_event_key"])
        mapped_parts.append(z)

    panel = pd.concat(mapped_parts, ignore_index=True)
    if len(panel) != len(formal):
        raise ValueError("merge_asof changed Formal row count")

    l1_codes: list[str | None] = []
    methods: list[str] = []
    migration_l3: list[str | None] = []
    for rec in panel[["symbol", "trade_date", "classification_code"]].to_dict("records"):
        sym = str(rec["symbol"])
        d = str(rec["trade_date"])
        code = None if pd.isna(rec["classification_code"]) else str(rec["classification_code"]).zfill(6)
        out_code: str | None = None
        method = "UNRESOLVED"
        l3_idx: str | None = None
        if code is None:
            first_start = first_official_start.get(sym)
            if first_start is not None and d < first_start:
                method = "OFFICIAL_NOT_YET_CLASSIFIED"
        elif d <= SW2014_LAST:
            if code in old_l3_to_l1:
                out_code = old_index.get(old_l3_to_l1[code])
                method = "SW2014_DIRECT_OFFICIAL_HISTORY"
            else:
                l3_idx = new_l3_idx.get(code)
                source_l1_class = new_l3_to_l1.get(code)
                source_l1_index = new_l1_index.get(source_l1_class) if source_l1_class else None
                if (sym, code) in special_bridge:
                    out_code = special_bridge[(sym, code)]
                    method = "SW2021_859622_TO_SW2014_EXACT_HISTORY_BRIDGE"
                elif l3_idx in bridge:
                    out_code = bridge[l3_idx]
                    method = "SW2021_L3_TO_SW2014_PINNED_BRIDGE"
                elif source_l1_index is not None and source_l1_index not in NEW_SW2021_L1:
                    out_code = source_l1_index
                    method = "SW2021_UNCHANGED_L1_IDENTITY"
        elif d >= SW2021_FIRST:
            if code in new_l3_to_l1:
                out_code = new_l1_index.get(new_l3_to_l1[code])
                method = "SW2021_NATIVE_OFFICIAL_HISTORY"
            elif code in new_l1_index:
                out_code = new_l1_index.get(code)
                method = "SW2021_NATIVE_L1_OFFICIAL_HISTORY"
        l1_codes.append(out_code)
        methods.append(method)
        migration_l3.append(l3_idx)

    panel["industry_code"] = l1_codes
    panel["mapping_method"] = methods
    panel["migration_l3_index_code"] = migration_l3
    panel["raw_xls_sha256"] = raw_xls_sha

    explicit_no_membership = panel.loc[panel["mapping_method"].eq("OFFICIAL_NOT_YET_CLASSIFIED")].copy()
    unresolved = panel.loc[panel["mapping_method"].eq("UNRESOLVED")].copy()
    coverage_resolved = panel["industry_code"].notna() | panel["mapping_method"].eq("OFFICIAL_NOT_YET_CLASSIFIED")
    invalid_required = panel.loc[panel["industry_code"].notna() & ~panel["industry_code"].isin(required_codes)].copy()
    duplicate_mapped = int(panel.duplicated(["symbol_full", "trade_date"], keep=False).sum())

    pre = panel.loc[panel["trade_date"].le(SW2014_LAST)]
    post = panel.loc[panel["trade_date"].ge(SW2021_FIRST)]
    pre_new_l1 = int(pre["industry_code"].isin(NEW_SW2021_L1).sum())
    post_old_l1 = int(post["industry_code"].isin(SW2014_ONLY_L1).sum())
    bridge_after_switch = int(post["mapping_method"].str.contains("BRIDGE", na=False).sum())
    native_before_switch = int(pre["mapping_method"].str.contains("SW2021_NATIVE", na=False).sum())
    forbidden_gap_rows = int(panel["trade_date"].isin(["20211211", "20211212"]).sum())

    exact_special_rows = panel.loc[
        panel["symbol"].isin(SEVEN_859622_SYMBOLS)
        & panel["trade_date"].between("20210730", SW2014_LAST)
        & panel["classification_code"].astype(str).eq("750202")
    ].copy()
    special_bad = exact_special_rows.loc[
        ~exact_special_rows["industry_code"].eq("801020.SI")
        | ~exact_special_rows["mapping_method"].eq("SW2021_859622_TO_SW2014_EXACT_HISTORY_BRIDGE")
    ]

    req = (
        panel.loc[panel["industry_code"].notna(), ["industry_code", "trade_date"]]
        .drop_duplicates()
        .sort_values(["trade_date", "industry_code"])
        .reset_index(drop=True)
    )
    req_dup = int(req.duplicated(["industry_code", "trade_date"], keep=False).sum())

    panel_out = panel[
        [
            "symbol_full",
            "trade_date",
            "industry_code",
            "classification_code",
            "classification_start_date",
            "classification_update_time",
            "mapping_method",
            "migration_l3_index_code",
            "raw_xls_sha256",
        ]
    ].sort_values(["symbol_full", "trade_date"])
    panel_out.to_csv(out / "industry_membership_formal.csv.gz", index=False, compression="gzip")
    req.to_csv(out / "formal_required_sector_keys.csv.gz", index=False, compression="gzip")
    unresolved.to_csv(out / "formal_membership_unresolved.csv", index=False)
    explicit_no_membership.to_csv(out / "formal_membership_explicit_no_membership.csv", index=False)
    pd.DataFrame(seven_evidence).to_json(
        out / "seven_859622_resolution.json", orient="records", force_ascii=False, indent=2
    )
    pd.DataFrame(seven_evidence).to_csv(out / "seven_859622_resolution.csv", index=False)

    expected_preclassification_gaps = {
        "001211.SZ": {"count": 1, "min_date": "20210805", "max_date": "20210805", "first_official_start": "20210806"},
        "001289.SZ": {"count": 14, "min_date": "20220124", "max_date": "20220217", "first_official_start": "20220218"},
    }
    observed_preclassification_gaps: dict[str, dict[str, Any]] = {}
    for symbol_full, gap_rows in explicit_no_membership.groupby("symbol_full", sort=True):
        short = str(symbol_full)[:6]
        observed_preclassification_gaps[str(symbol_full)] = {
            "count": int(len(gap_rows)),
            "min_date": str(gap_rows["trade_date"].min()),
            "max_date": str(gap_rows["trade_date"].max()),
            "first_official_start": first_official_start.get(short),
            "all_before_first_official_start": bool(
                first_official_start.get(short)
                and gap_rows["trade_date"].astype(str).lt(str(first_official_start.get(short))).all()
            ),
        }
    exact_preclassification_gap_inventory = observed_preclassification_gaps == expected_preclassification_gaps

    standards = {
        "sw2014_hierarchy": {"path": str(sw2014_hierarchy), "sha256": sha256(sw2014_hierarchy)},
        "sw2014_index_map": {"path": str(sw2014_index_map), "sha256": sha256(sw2014_index_map)},
        "sw2021_hierarchy": {"path": str(sw2021_hierarchy), "sha256": sha256(sw2021_hierarchy)},
        "sw2021_l1": {"path": str(sw2021_l1), "sha256": sha256(sw2021_l1)},
        "sw2021_l3": {"path": str(sw2021_l3), "sha256": sha256(sw2021_l3)},
        "taxonomy_manifest": {"path": str(taxonomy), "sha256": sha256(taxonomy)},
    }
    checks = {
        "canonical_sw_xls_exact": raw_xls_sha == CANONICAL_SW_XLS_SHA256 and raw_xls_bytes == 1_165_824,
        "sw_xls_duplicate_symbol_date_rows_zero": hist_dup == 0,
        "seven_unresolved_resolved": len(seven_evidence) == 7,
        "unresolved_rows_zero": len(unresolved) == 0,
        "formal_stock_date_rows_exact": len(panel) == FORMAL_RAW_EXPECTED_ROWS,
        "formal_coverage_resolved": int(coverage_resolved.sum()) == FORMAL_RAW_EXPECTED_ROWS,
        "formal_duplicate_symbol_date_zero": duplicate_mapped == 0,
        "mapped_industry_codes_within_required_32": len(invalid_required) == 0,
        "pre_switch_has_no_sw2021_new_l1": pre_new_l1 == 0,
        "post_switch_has_no_sw2014_only_l1": post_old_l1 == 0,
        "bridge_rows_after_switch_zero": bridge_after_switch == 0,
        "native_rows_before_switch_zero": native_before_switch == 0,
        "weekend_switch_gap_rows_zero": forbidden_gap_rows == 0,
        "seven_bridge_rows_exact": len(special_bad) == 0,
        "required_sector_key_duplicates_zero": req_dup == 0,
        "explicit_no_membership_is_officially_bounded": exact_preclassification_gap_inventory,
    }
    passed = all(checks.values())
    audit = {
        "artifact": "DAO2_C_SECTOR_MEMBERSHIP_PIT_AUDIT_V1",
        "version": "1.0",
        "status": "PASS_SUBCOMPONENT" if passed else "BLOCKED",
        "blocker": "SECTOR_MEMBERSHIP_PIT_UNBOUND",
        "blocker_closed_within_module": passed,
        "historical_gp_v11_membership_recovered": False,
        "candidate_membership_definition": "Official SW classification-history effective dates with explicit SW2014/SW2021 taxonomy switch",
        "canonical_sw_xls": {
            "source_url": CANONICAL_SW_XLS_URL,
            "sha256": raw_xls_sha,
            "size_bytes": raw_xls_bytes,
            "rows": int(len(hist)),
            "duplicate_symbol_date_rows": hist_dup,
            "source_probe_run_id": 35558312420,
            "source_artifact_id": 10620749755,
        },
        "formal_raw": {
            **FORMAL_RAW_ARTIFACT,
            "parquet_sha256": sha256(formal_raw),
            "stock_date_keys": int(len(formal)),
            "symbols_with_trade_rows": int(formal["symbol_full"].nunique()),
        },
        "formal_membership": {
            "mapped_stock_date_keys": int(panel["industry_code"].notna().sum()),
            "explicit_no_membership_stock_date_keys": int(len(explicit_no_membership)),
            "coverage_resolved_stock_date_keys": int(coverage_resolved.sum()),
            "unresolved_stock_date_keys": int(len(unresolved)),
            "duplicate_stock_date_keys": duplicate_mapped,
            "required_sector_date_keys": int(len(req)),
            "required_sector_date_key_duplicates": req_dup,
            "no_history_symbols": sorted(no_history_symbols),
            "invalid_required_code_rows": int(len(invalid_required)),
            "explicit_no_membership_symbols": sorted(explicit_no_membership["symbol_full"].dropna().unique().tolist()),
            "explicit_no_membership_min_date": None if explicit_no_membership.empty else str(explicit_no_membership["trade_date"].min()),
            "explicit_no_membership_max_date": None if explicit_no_membership.empty else str(explicit_no_membership["trade_date"].max()),
            "explicit_no_membership_next_official_start": {
                sym + (".SZ" if sym.startswith(("0","3")) else ".SH"): first_official_start.get(sym)
                for sym in sorted(explicit_no_membership["symbol"].dropna().unique().tolist())
            },
            "expected_preclassification_gaps": expected_preclassification_gaps,
            "observed_preclassification_gaps": observed_preclassification_gaps,
        },
        "taxonomy_switch": {
            "sw2014_last_trade_date": SW2014_LAST,
            "sw2021_first_trade_date": SW2021_FIRST,
            "pre_switch_sw2021_new_l1_rows": pre_new_l1,
            "post_switch_sw2014_only_l1_rows": post_old_l1,
            "bridge_rows_after_switch": bridge_after_switch,
            "native_rows_before_switch": native_before_switch,
            "weekend_gap_rows": forbidden_gap_rows,
            "pass": pre_new_l1 == 0 and post_old_l1 == 0 and bridge_after_switch == 0 and native_before_switch == 0 and forbidden_gap_rows == 0,
        },
        "seven_859622_resolution": seven_evidence,
        "unresolved_rows": int(len(unresolved)),
        "checks": checks,
        "standards": standards,
        "required_industry_codes": sorted(required_codes),
        "safety": {
            "forward_fill": False,
            "synthetic_membership_rows": False,
            "uses_effective_date_only": True,
            "future_classification_backfill": False,
            "official_pre_classification_gap_is_explicit_no_membership": True,
            "historical_gp_v11_identity_claim": False,
        },
    }
    (out / "membership_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return audit


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd",required=True)

    p = sub.add_parser("prepare")
    p.add_argument("--taxonomy",type=Path,required=True)
    p.add_argument("--formal-calendar",type=Path,required=True)
    p.add_argument("--root",type=Path,required=True)

    p = sub.add_parser("membership")
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--formal-calendar",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)

    p = sub.add_parser("patch-series")
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--formal-calendar",type=Path,required=True)
    p.add_argument("--out-json",type=Path,required=True)

    p = sub.add_parser("series")
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--formal-calendar",type=Path,required=True)
    p.add_argument("--membership-out",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)

    p = sub.add_parser("official-membership")
    p.add_argument("--sw-xls",type=Path,required=True)
    p.add_argument("--formal-raw",type=Path,required=True)
    p.add_argument("--taxonomy",type=Path,required=True)
    p.add_argument("--sw2014-hierarchy",type=Path,required=True)
    p.add_argument("--sw2014-index-map",type=Path,required=True)
    p.add_argument("--sw2021-hierarchy",type=Path,required=True)
    p.add_argument("--sw2021-l1",type=Path,required=True)
    p.add_argument("--sw2021-l3",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)

    args = ap.parse_args()
    if args.cmd == "prepare":
        prepare_root(args.taxonomy,args.formal_calendar,args.root)
    elif args.cmd == "membership":
        result = export_membership(args.root,args.out,args.formal_calendar)
        args.out.mkdir(parents=True,exist_ok=True)
        (args.out/"membership_audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
        print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    elif args.cmd == "patch-series":
        result = patch_series_with_tushare(args.root,args.formal_calendar)
        args.out_json.parent.mkdir(parents=True,exist_ok=True)
        args.out_json.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(result,ensure_ascii=False,indent=2))
    elif args.cmd == "series":
        result = audit_series(args.root,args.formal_calendar,args.membership_out,args.out)
        (args.out/"series_audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(result,ensure_ascii=False,indent=2))
    elif args.cmd == "official-membership":
        result = official_membership(
            sw_xls=args.sw_xls,
            formal_raw=args.formal_raw,
            taxonomy=args.taxonomy,
            sw2014_hierarchy=args.sw2014_hierarchy,
            sw2014_index_map=args.sw2014_index_map,
            sw2021_hierarchy=args.sw2021_hierarchy,
            sw2021_l1=args.sw2021_l1,
            sw2021_l3=args.sw2021_l3,
            out=args.out,
        )
        print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
        if result.get("status") != "PASS_SUBCOMPONENT":
            raise SystemExit(2)


if __name__ == "__main__":
    main()
