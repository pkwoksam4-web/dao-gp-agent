from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import pandas as pd
import requests

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

def fetch_sw_analysis_day(trade_date: str) -> pd.DataFrame:
    """Fetch one SW L1 analysis-report date directly from the same official endpoint AKShare wraps."""
    url="https://www.swsresearch.com/institute-sw/api/index_analysis/index_analysis_report/"
    params={
        "page":"1",
        "page_size":"50",
        "index_type":"一级行业",
        "start_date":f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}",
        "end_date":f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}",
        "type":"DAY",
        "swindexcode":"all",
    }
    headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/114.0.0.0 Safari/537.36"}
    first=requests.get(url,params=params,headers=headers,verify=False,timeout=30)
    first.raise_for_status()
    payload=first.json()
    data=payload.get("data") or {}
    count=int(data.get("count") or 0)
    if count == 0:
        return pd.DataFrame(columns=["industry_code","trade_date","close"])
    frames=[]
    pages=max(1,(count+49)//50)
    for page in range(1,pages+1):
        params["page"]=str(page)
        resp=requests.get(url,params=params,headers=headers,verify=False,timeout=30)
        resp.raise_for_status()
        body=resp.json().get("data") or {}
        part=pd.DataFrame(body.get("results") or [])
        if not part.empty:
            frames.append(part)
    if not frames:
        return pd.DataFrame(columns=["industry_code","trade_date","close"])
    g=pd.concat(frames,ignore_index=True)
    required={"swindexcode","bargaindate","closeindex"}
    if not required.issubset(g.columns):
        raise RuntimeError(f"analysis endpoint missing columns: {sorted(required-set(g.columns))}; got={list(g.columns)}")
    g=g.rename(columns={"swindexcode":"industry_code","bargaindate":"trade_date","closeindex":"close"})
    g["industry_code"]=g["industry_code"].astype(str).str.replace(".0","",regex=False).map(lambda x:x if x.endswith(".SI") else x+".SI")
    g["trade_date"]=pd.to_datetime(g["trade_date"],errors="coerce").dt.strftime("%Y%m%d")
    g["close"]=pd.to_numeric(g["close"],errors="coerce")
    g=g.dropna(subset=["industry_code","trade_date","close"]).copy()
    wrong_dates=sorted(set(g["trade_date"])-{trade_date})
    if wrong_dates:
        raise RuntimeError(f"analysis endpoint returned non-request dates for {trade_date}: {wrong_dates[:10]}")
    return g[["industry_code","trade_date","close"]]


def fetch_eastmoney_sw_history(code: str) -> pd.DataFrame:
    """Fetch Eastmoney's mirror of the Shenwan index daily series for one 801xxx code."""
    bare=code.removesuffix(".SI")
    url="https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params={
        "secid":f"90.{bare}",
        "fields1":"f1,f2,f3,f4,f5,f6",
        "fields2":"f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt":"101",
        "fqt":"0",
        "beg":FORMAL_START,
        "end":FORMAL_END,
        "lmt":"5000",
    }
    headers={
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Referer":"https://quote.eastmoney.com/",
    }
    last=None
    for attempt in range(4):
        try:
            resp=requests.get(url,params=params,headers=headers,timeout=30)
            resp.raise_for_status()
            payload=resp.json()
            data=payload.get("data") or {}
            klines=data.get("klines") or []
            rows=[]
            for line in klines:
                parts=str(line).split(",")
                if len(parts)<3:
                    continue
                td=pd.to_datetime(parts[0],errors="coerce")
                close=pd.to_numeric(parts[2],errors="coerce")
                if pd.isna(td) or pd.isna(close):
                    continue
                rows.append({
                    "industry_code":code,
                    "trade_date":td.strftime("%Y%m%d"),
                    "close":float(close),
                })
            out=pd.DataFrame(rows,columns=["industry_code","trade_date","close"])
            if not out.empty:
                out=out.drop_duplicates(["industry_code","trade_date"],keep=False).sort_values("trade_date").reset_index(drop=True)
            return out
        except Exception as exc:
            last=exc
            if attempt==3:
                break
            import time
            time.sleep(2*(attempt+1))
    raise RuntimeError(f"{code}: Eastmoney SW history failed after retries: {last!r}")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--calendar",type=Path,required=True)
    ap.add_argument("--taxonomy",type=Path,required=True)
    ap.add_argument("--required-keys",type=Path,required=True)
    ap.add_argument("--membership-checkpoint",type=Path,required=True)
    ap.add_argument("--price-basis",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    raw_dir=args.out/"raw_index_hist_sw"
    raw_dir.mkdir(exist_ok=True)

    import akshare as ak
    dates=read_calendar(args.calendar)
    date_set=set(dates)
    tax=json.loads(args.taxonomy.read_text(encoding="utf-8"))

    membership_checkpoint=json.loads(args.membership_checkpoint.read_text(encoding="utf-8"))
    if membership_checkpoint.get("status")!="PASS_SUBCOMPONENT" or membership_checkpoint.get("blocker_closed_within_module") is not True:
        raise RuntimeError("Membership checkpoint is not PASS_SUBCOMPONENT")

    price_basis=json.loads(args.price_basis.read_text(encoding="utf-8"))
    if price_basis.get("status")!="PASS_CANDIDATE_PRICE_BASIS_DEFINITION" or not price_basis.get("blocker_effect",{}).get("price_basis_subblocker_closed_for_candidate"):
        raise RuntimeError("Candidate sector price basis is not PASS")

    req_df=pd.read_csv(args.required_keys,dtype=str)
    required_cols={"industry_code","trade_date"}
    if not required_cols.issubset(req_df.columns):
        raise RuntimeError(f"required keys missing columns: {sorted(required_cols-set(req_df.columns))}")
    req_df=req_df[["industry_code","trade_date"]].copy()
    req_df["industry_code"]=req_df["industry_code"].astype(str)
    req_df["trade_date"]=pd.to_datetime(req_df["trade_date"],errors="coerce").dt.strftime("%Y%m%d")
    req_df=req_df.dropna().copy()
    input_required_duplicate_rows=int(req_df.duplicated(["industry_code","trade_date"],keep=False).sum())
    if input_required_duplicate_rows:
        raise RuntimeError(f"membership required keys duplicate rows={input_required_duplicate_rows}")
    required=set(map(tuple,req_df.itertuples(index=False,name=None)))
    if len(required)!=43084:
        raise RuntimeError(f"membership required key count mismatch: {len(required)} != 43084")
    if any(d not in date_set for _,d in required):
        raise RuntimeError("membership required keys contain dates outside frozen Formal calendar")
    codes=sorted(req_df["industry_code"].unique().tolist())
    if len(codes)!=32:
        raise RuntimeError(f"membership required industry code count mismatch: {len(codes)}")
    if set(codes)!=set(tax["required_industry_codes"]):
        raise RuntimeError("membership required industry codes disagree with pinned taxonomy manifest")
    required_by_code={code:{d for c,d in required if c==code} for code in codes}

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
        f=f.dropna(subset=["trade_date","close"]).copy()
        duplicate_rows=int(f.duplicated(["industry_code","trade_date"],keep=False).sum())
        if duplicate_rows:
            raise RuntimeError(f"{code}: duplicate sector-date rows={duplicate_rows}")
        f.to_parquet(raw_dir/f"{code}.parquet",index=False,compression="zstd")
        m={(code,d):float(c) for d,c in f[["trade_date","close"]].itertuples(index=False,name=None)}
        base.update(m)
        exp=required_by_code[code]
        pres=set(f["trade_date"])
        miss=sorted(exp-pres)
        per_code[code]={"base_rows":len(f),"expected_rows":len(exp),"base_missing":len(miss),"base_missing_dates":miss,"duplicate_rows":duplicate_rows}
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
            g=fetch_sw_analysis_day(d)
        except Exception as exc:
            daily_errors.append({"trade_date":d,"error":repr(exc)})
            continue
        if g.empty:
            daily_errors.append({"trade_date":d,"error":"EMPTY"})
            continue
        duplicate_patch_rows=int(g.duplicated(["industry_code","trade_date"],keep=False).sum())
        if duplicate_patch_rows:
            daily_errors.append({"trade_date":d,"error":f"duplicate_endpoint_rows:{duplicate_patch_rows}"})
            continue

        # Cross-check every same-date overlap available between the two official SW endpoints.
        for code,td,close in g[["industry_code","trade_date","close"]].itertuples(index=False,name=None):
            k=(code,td)
            if k in base:
                overlap.append({"industry_code":code,"trade_date":td,"hist_close":base[k],"analysis_close":float(close),"abs_diff":abs(base[k]-float(close))})
            if k in missing:
                patch.append({"industry_code":code,"trade_date":td,"close":float(close),"source_provider":"swsresearch:index_analysis_report","source_trade_date":td,"fill_method":"NONE","price_basis":"SW_INDUSTRY_INDEX_CLOSE_LEVEL"})
        print(f"daily {pos}/{len(gap_dates)} {d} rows={len(g)}",flush=True)

    # Same-index mirror fallback: Eastmoney secid=90.801xxx.
    # A code is eligible for patching only after its close levels match the official SW/AKShare
    # base exactly on a substantial same-date overlap; otherwise it is rejected fail-closed.
    patched_keys={(str(r["industry_code"]),str(r["trade_date"])) for r in patch}
    remaining_for_eastmoney=set(missing)-patched_keys
    eastmoney_patch_rows=0
    eastmoney_errors=[]
    eastmoney_overlap=[]
    eastmoney_code_validation={}
    eastmoney_raw_dir=args.out/"raw_eastmoney_sw_mirror"
    eastmoney_raw_dir.mkdir(exist_ok=True)
    for code in sorted({c for c,_ in remaining_for_eastmoney}):
        try:
            em=fetch_eastmoney_sw_history(code)
        except Exception as exc:
            eastmoney_errors.append({"industry_code":code,"error":repr(exc)})
            eastmoney_code_validation[code]={"eligible":False,"reason":"FETCH_ERROR"}
            continue
        if em.empty:
            eastmoney_errors.append({"industry_code":code,"error":"EMPTY"})
            eastmoney_code_validation[code]={"eligible":False,"reason":"EMPTY"}
            continue
        em.to_parquet(eastmoney_raw_dir/f"{code}.parquet",index=False,compression="zstd")
        dup=int(em.duplicated(["industry_code","trade_date"],keep=False).sum())
        if dup:
            eastmoney_errors.append({"industry_code":code,"error":f"duplicate_rows:{dup}"})
            eastmoney_code_validation[code]={"eligible":False,"reason":"DUPLICATE"}
            continue
        overlaps=[]
        for _,r in em.iterrows():
            k=(code,str(r["trade_date"]))
            if k in base:
                diff=abs(float(base[k])-float(r["close"]))
                overlaps.append(diff)
                eastmoney_overlap.append({
                    "industry_code":code,
                    "trade_date":str(r["trade_date"]),
                    "official_close":float(base[k]),
                    "eastmoney_close":float(r["close"]),
                    "abs_diff":diff,
                })
        overlap_rows=len(overlaps)
        overlap_max=max(overlaps) if overlaps else None
        eligible=bool(overlap_rows>=100 and overlap_max is not None and overlap_max<=1e-8)
        eastmoney_code_validation[code]={
            "eligible":eligible,
            "overlap_rows":overlap_rows,
            "max_abs_close_diff":overlap_max,
            "required_min_overlap_rows":100,
            "required_max_abs_close_diff":1e-8,
            "secid":f"90.{code.removesuffix('.SI')}",
            "fqt":0,
        }
        if not eligible:
            eastmoney_errors.append({
                "industry_code":code,
                "error":"OVERLAP_VALIDATION_FAILED",
                "overlap_rows":overlap_rows,
                "max_abs_close_diff":overlap_max,
            })
            continue
        em_map={(code,str(td)):float(close) for td,close in em[["trade_date","close"]].itertuples(index=False,name=None)}
        for k in sorted(remaining_for_eastmoney):
            if k[0]!=code or k not in em_map:
                continue
            patch.append({
                "industry_code":code,
                "trade_date":k[1],
                "close":em_map[k],
                "source_provider":"eastmoney:push2his:sw_index_mirror",
                "source_trade_date":k[1],
                "fill_method":"NONE",
                "price_basis":"SW_INDUSTRY_INDEX_CLOSE_LEVEL",
            })
            eastmoney_patch_rows+=1

    if eastmoney_overlap:
        pd.DataFrame(eastmoney_overlap).to_csv(args.out/"eastmoney_official_same_day_overlap.csv",index=False)

    # Existing approved fallback: Tushare SW daily, exact same trade date only.
    patched_keys={(str(r["industry_code"]),str(r["trade_date"])) for r in patch}
    remaining_for_tushare=set(missing)-patched_keys
    tushare_patch_rows=0
    tushare_errors=[]
    tushare_overlap=[]
    tushare_token_present=bool(os.environ.get("TUSHARE_TOKEN"))
    if remaining_for_tushare and tushare_token_present:
        import tushare as ts
        pro=ts.pro_api(os.environ["TUSHARE_TOKEN"])
        for d in sorted({td for _,td in remaining_for_tushare}):
            try:
                t=pro.sw_daily(trade_date=d)
            except Exception as exc:
                tushare_errors.append({"trade_date":d,"error":repr(exc)})
                if "token" in str(exc).lower() or "token不对" in str(exc):
                    break
                continue
            if t is None or t.empty:
                tushare_errors.append({"trade_date":d,"error":"EMPTY"})
                continue
            if not {"ts_code","trade_date","close"}.issubset(t.columns):
                tushare_errors.append({"trade_date":d,"error":f"missing_columns:{list(t.columns)}"})
                continue
            t=t.rename(columns={"ts_code":"industry_code"})[["industry_code","trade_date","close"]].copy()
            t["industry_code"]=t["industry_code"].astype(str)
            t["trade_date"]=pd.to_datetime(t["trade_date"],errors="coerce").dt.strftime("%Y%m%d")
            t["close"]=pd.to_numeric(t["close"],errors="coerce")
            t=t.dropna(subset=["industry_code","trade_date","close"]).copy()
            wrong=sorted(set(t["trade_date"])-{d})
            if wrong:
                tushare_errors.append({"trade_date":d,"error":f"non_same_date:{wrong[:5]}"})
                continue
            dup=int(t.duplicated(["industry_code","trade_date"],keep=False).sum())
            if dup:
                tushare_errors.append({"trade_date":d,"error":f"duplicate_rows:{dup}"})
                continue
            for code,td,close in t.itertuples(index=False,name=None):
                k=(str(code),str(td))
                if k in base:
                    tushare_overlap.append({
                        "industry_code":str(code),
                        "trade_date":str(td),
                        "hist_close":float(base[k]),
                        "tushare_close":float(close),
                        "abs_diff":abs(float(base[k])-float(close)),
                    })
                if k in remaining_for_tushare:
                    patch.append({
                        "industry_code":str(code),
                        "trade_date":str(td),
                        "close":float(close),
                        "source_provider":"tushare:sw_daily",
                        "source_trade_date":str(td),
                        "fill_method":"NONE",
                        "price_basis":"SW_INDUSTRY_INDEX_CLOSE_LEVEL",
                    })
                    tushare_patch_rows+=1
            print(f"tushare exact {d} rows={len(t)} patch_total={tushare_patch_rows}",flush=True)
    elif remaining_for_tushare:
        tushare_errors.append({"error":"NO_TUSHARE_TOKEN","remaining_keys":len(remaining_for_tushare)})

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
        patch_duplicate_rows=int(patch_df.duplicated(["industry_code","trade_date"],keep=False).sum())
        if patch_duplicate_rows:
            raise RuntimeError(f"duplicate same-day patch rows={patch_duplicate_rows}")
        patch_df.to_csv(args.out/"same_day_gap_patch.csv",index=False)
        rows.extend(patch_df.to_dict("records"))
    else:
        patch_duplicate_rows=0
    panel=pd.DataFrame(rows)
    duplicate_required_rows=int(panel.duplicated(["industry_code","trade_date"],keep=False).sum())
    if duplicate_required_rows:
        raise RuntimeError(f"duplicate required sector-date rows={duplicate_required_rows}")
    panel=panel.sort_values(["industry_code","trade_date"])
    panel.to_csv(args.out/"sector_close_formal.csv.gz",index=False,compression="gzip")

    observed=set(map(tuple,panel[["industry_code","trade_date"]].astype(str).itertuples(index=False,name=None)))
    final_missing=sorted(required-observed)
    same_date=bool((panel["trade_date"].astype(str)==panel["source_trade_date"].astype(str)).all())
    no_fill=bool(panel["fill_method"].eq("NONE").all())
    finite=bool((pd.to_numeric(panel["close"],errors="coerce").notna() & (pd.to_numeric(panel["close"],errors="coerce")>0)).all())

    audit={
      "artifact":"DAO2_C_SECTOR_SERIES_EXACT_AUDIT_V1",
      "status":"PASS_SUBCOMPONENT" if (
          not final_missing
          and duplicate_required_rows==0
          and same_date
          and no_fill
          and finite
          and (
              eastmoney_patch_rows==0
              or all(
                  eastmoney_code_validation.get(str(r["industry_code"]),{}).get("eligible") is True
                  for r in patch if r.get("source_provider")=="eastmoney:push2his:sw_index_mirror"
              )
          )
      ) else "BLOCKED",
      "formal":{"start":FORMAL_START,"end":FORMAL_END,"trading_days":len(dates)},
      "taxonomy_switch":{"sw2014_last":SW2014_LAST,"sw2021_first":SW2021_FIRST,"sw2014_only":sorted(SW2014_ONLY),"sw2021_new":sorted(SW2021_NEW)},
      "required_key_source":"PASS membership artifact: membership_out/formal_required_sector_keys.csv.gz",
      "membership_checkpoint_status":membership_checkpoint.get("status"),
      "price_basis_binding_status":price_basis.get("status"),
      "required_industry_codes":len(codes),
      "required_sector_date_keys":len(required),
      "input_required_duplicate_rows":input_required_duplicate_rows,
      "observed_required_keys":len(required)-len(final_missing),
      "missing_required_keys":len(final_missing),
      "duplicate_required_keys":duplicate_required_rows,
      "missing_required_key_sample":[{"industry_code":a,"trade_date":b} for a,b in final_missing[:100]],
      "base_missing_keys":sum(x["base_missing"] for x in per_code.values()),
      "gap_dates":gap_dates,
      "same_day_patch_rows":0 if patch_df.empty else int(len(patch_df)),
      "same_day_patch_duplicate_rows":patch_duplicate_rows,
      "eastmoney_patch_rows":eastmoney_patch_rows,
      "eastmoney_errors":eastmoney_errors,
      "eastmoney_code_validation":eastmoney_code_validation,
      "eastmoney_overlap_rows":len(eastmoney_overlap),
      "eastmoney_patch_rows_all_overlap_validated":bool(
          eastmoney_patch_rows==0
          or all(
              eastmoney_code_validation.get(str(r["industry_code"]),{}).get("eligible") is True
              for r in patch if r.get("source_provider")=="eastmoney:push2his:sw_index_mirror"
          )
      ),
      "tushare_token_present":tushare_token_present,
      "tushare_patch_rows":tushare_patch_rows,
      "tushare_errors":tushare_errors,
      "tushare_same_day_overlap_rows":len(tushare_overlap),
      "same_day_endpoint_overlap":{"rows":int(len(overlap_df)),"max_abs_close_diff":overlap_max,"p99_abs_close_diff":overlap_p99,"exact_pass":overlap_pass},
      "same_date_provenance":same_date,
      "same_day_sources_closed_all_required_gaps":len(final_missing)==0,
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
    if audit["status"]!="PASS_SUBCOMPONENT":
        raise SystemExit(2)

if __name__=="__main__":
    main()
