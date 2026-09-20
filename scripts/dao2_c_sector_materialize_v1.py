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
            # Do not request impossible taxonomy-era dates for the four new L1s.
            if code in NEW_SW2021_L1 and d < SW2021_FIRST:
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


if __name__ == "__main__":
    main()
