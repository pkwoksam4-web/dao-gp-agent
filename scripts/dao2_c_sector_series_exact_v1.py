from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import pandas as pd

FORMAL_START="20200601"
FORMAL_END="20260417"
SW2014_LAST="20211210"
SW2021_FIRST="20211213"
SW2014_ONLY={"801020.SI"}
SW2021_NEW={"801950.SI","801960.SI","801970.SI","801980.SI"}

def norm_date(x):
    return pd.to_datetime(str(x),errors="coerce").strftime("%Y%m%d")

def expected_dates(code, dates):
    out=[]
    for d in dates:
        if code in SW2014_ONLY and d>SW2014_LAST: continue
        if code in SW2021_NEW and d<SW2021_FIRST: continue
        out.append(d)
    return out

def read_calendar(path):
    f=pd.read_csv(path)
    if "is_open" in f: f=f[f["is_open"].astype(str).isin(["1","1.0","True","true"])]
    col=next(c for c in ("trade_date","cal_date","date") if c in f)
    dates=sorted(set(pd.to_datetime(f[col].astype(str),errors="coerce").dt.strftime("%Y%m%d").dropna()))
    dates=[d for d in dates if FORMAL_START<=d<=FORMAL_END]
    assert len(dates)==1426,(len(dates),dates[:1],dates[-1:])
    assert dates[0]==FORMAL_START and dates[-1]==FORMAL_END
    return dates

def git_blob_sha(data:bytes):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--calendar",type=Path,required=True)
    ap.add_argument("--taxonomy",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    raw_dir=args.out/"raw_index_hist_sw"
    raw_dir.mkdir(exist_ok=True)

    import akshare as ak
    dates=read_calendar(args.calendar)
    tax=json.loads(args.taxonomy.read_text(encoding="utf-8"))
    codes=tax["required_industry_codes"]
    assert len(codes)==32,len(codes)

    base={}
    rows=[]
    per_code={}
    for pos,code in enumerate(codes,1):
        f=ak.index_hist_sw(symbol=code.removesuffix(".SI"),period="day").copy()
        ren={"日期":"trade_date","收盘":"close","代码":"industry_code"}
        f=f.rename(columns=ren)
        if "trade_date" not in f:
            raise RuntimeError(f"{code}: missing 日期/trade_date")
        if "close" not in f:
            raise RuntimeError(f"{code}: missing 收盘/close")
        f["trade_date"]=pd.to_datetime(f["trade_date"],errors="coerce").dt.strftime("%Y%m%d")
        f=f[f["trade_date"].isin(dates)].copy()
        f["industry_code"]=code
        f["close"]=pd.to_numeric(f["close"],errors="coerce")
        f=f.dropna(subset=["trade_date","close"]).drop_duplicates(["industry_code","trade_date"],keep="last")
        f.to_parquet(raw_dir/f"{code}.parquet",index=False,compression="zstd")
        m={(code,d):float(c) for d,c in f[["trade_date","close"]].itertuples(index=False,name=None)}
        base.update(m)
        exp=set(expected_dates(code,dates))
        pres=set(f["trade_date"])
        miss=sorted(exp-pres)
        per_code[code]={"base_rows":len(f),"expected_rows":len(exp),"base_missing":len(miss),"base_missing_dates":miss}
        for d,c in f[["trade_date","close"]].itertuples(index=False,name=None):
            if d in exp:
                rows.append({"industry_code":code,"trade_date":d,"close":float(c),"source_provider":"akshare:index_hist_sw","source_trade_date":d,"fill_method":"NONE","price_basis":"SW_INDUSTRY_INDEX_CLOSE_LEVEL"})
        print(f"hist {pos}/{len(codes)} {code} rows={len(f)} missing={len(miss)}",flush=True)

    missing=set()
    for code,item in per_code.items():
        for d in item["base_missing_dates"]: missing.add((code,d))
    gap_dates=sorted({d for _,d in missing})
    patch=[]
    overlap=[]
    daily_errors=[]
    for pos,d in enumerate(gap_dates,1):
        try:
            g=ak.index_analysis_daily_sw(symbol="一级行业",start_date=d,end_date=d).copy()
        except Exception as exc:
            daily_errors.append({"trade_date":d,"error":repr(exc)})
            continue
        if g.empty:
            daily_errors.append({"trade_date":d,"error":"EMPTY"})
            continue
        g=g.rename(columns={"指数代码":"industry_code","发布日期":"trade_date","收盘指数":"close"})
        if not {"industry_code","trade_date","close"}.issubset(g.columns):
            daily_errors.append({"trade_date":d,"error":f"missing_columns:{list(g.columns)}"})
            continue
        g["industry_code"]=g["industry_code"].astype(str).str.replace(".0","",regex=False).map(lambda x:x if x.endswith(".SI") else x+".SI")
        g["trade_date"]=pd.to_datetime(g["trade_date"],errors="coerce").dt.strftime("%Y%m%d")
        g["close"]=pd.to_numeric(g["close"],errors="coerce")
        g=g.dropna(subset=["industry_code","trade_date","close"]).drop_duplicates(["industry_code","trade_date"],keep="last")

        # Cross-check every same-date overlap available between the two SW endpoints.
        for code,td,close in g[["industry_code","trade_date","close"]].itertuples(index=False,name=None):
            k=(code,td)
            if k in base:
                overlap.append({"industry_code":code,"trade_date":td,"hist_close":base[k],"analysis_close":float(close),"abs_diff":abs(base[k]-float(close))})
            if k in missing:
                patch.append({"industry_code":code,"trade_date":td,"close":float(close),"source_provider":"akshare:index_analysis_daily_sw","source_trade_date":td,"fill_method":"NONE","price_basis":"SW_INDUSTRY_INDEX_CLOSE_LEVEL"})
        print(f"daily {pos}/{len(gap_dates)} {d} rows={len(g)}",flush=True)

    overlap_df=pd.DataFrame(overlap)
    patch_df=pd.DataFrame(patch)
    if not overlap_df.empty:
        overlap_df.to_csv(args.out/"same_day_endpoint_overlap.csv",index=False)
        overlap_max=float(overlap_df["abs_diff"].max())
        overlap_p99=float(overlap_df["abs_diff"].quantile(.99))
        overlap_pass=overlap_max<=1e-8
    else:
        overlap_max=None; overlap_p99=None; overlap_pass=False

    if not patch_df.empty:
        patch_df=patch_df.drop_duplicates(["industry_code","trade_date"],keep="last")
        patch_df.to_csv(args.out/"same_day_gap_patch.csv",index=False)
        rows.extend(patch_df.to_dict("records"))
    panel=pd.DataFrame(rows).drop_duplicates(["industry_code","trade_date"],keep="last")
    panel=panel.sort_values(["industry_code","trade_date"])
    panel.to_csv(args.out/"sector_close_formal.csv.gz",index=False,compression="gzip")

    observed=set(map(tuple,panel[["industry_code","trade_date"]].astype(str).itertuples(index=False,name=None)))
    required=set()
    for code in codes:
        required.update((code,d) for d in expected_dates(code,dates))
    final_missing=sorted(required-observed)
    same_date=bool((panel["trade_date"].astype(str)==panel["source_trade_date"].astype(str)).all())
    no_fill=bool(panel["fill_method"].eq("NONE").all())
    finite=bool((pd.to_numeric(panel["close"],errors="coerce").notna() & (pd.to_numeric(panel["close"],errors="coerce")>0)).all())

    audit={
      "artifact":"DAO2_C_SECTOR_SERIES_EXACT_AUDIT_V1",
      "status":"PASS_SUBCOMPONENT" if not final_missing and same_date and no_fill and finite and overlap_pass else "BLOCKED",
      "formal":{"start":FORMAL_START,"end":FORMAL_END,"trading_days":len(dates)},
      "taxonomy_switch":{"sw2014_last":SW2014_LAST,"sw2021_first":SW2021_FIRST,"sw2014_only":sorted(SW2014_ONLY),"sw2021_new":sorted(SW2021_NEW)},
      "required_industry_codes":len(codes),
      "required_sector_date_keys":len(required),
      "observed_required_keys":len(required)-len(final_missing),
      "missing_required_keys":len(final_missing),
      "missing_required_key_sample":[{"industry_code":a,"trade_date":b} for a,b in final_missing[:100]],
      "base_missing_keys":sum(x["base_missing"] for x in per_code.values()),
      "gap_dates":gap_dates,
      "same_day_patch_rows":0 if patch_df.empty else int(len(patch_df)),
      "same_day_endpoint_overlap":{"rows":int(len(overlap_df)),"max_abs_close_diff":overlap_max,"p99_abs_close_diff":overlap_p99,"exact_pass":overlap_pass},
      "same_date_provenance":same_date,
      "fill_method_none":no_fill,
      "forward_fill_used":False,
      "finite_positive_close":finite,
      "price_basis_binding":"data/dao2/modules/C_SECTOR_PRICE_BASIS_BINDING_V1.json",
      "price_basis":"SW_INDUSTRY_INDEX_CLOSE_LEVEL",
      "historical_gp_v11_series_identity_claim":False,
      "daily_patch_errors":daily_errors,
      "per_code":per_code,
    }
    (args.out/"series_exact_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(audit,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":
    main()
