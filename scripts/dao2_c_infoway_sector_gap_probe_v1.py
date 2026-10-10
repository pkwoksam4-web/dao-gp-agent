from __future__ import annotations
import csv, gzip, hashlib, json, os, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, parse, request

BASE_URL="https://data.infoway.io"
SYMBOLS_URL=BASE_URL+"/common/basic/symbols"
KLINE_URL=BASE_URL+"/stock/v2/batch_kline"
TARGET_CODES=["801020.SI","801960.SI","801010.SI","801030.SI","801040.SI"]
PRIORITY_GAP_DATES=["20210806","20220303","20230908","20211022","20220509"]
REQUIRED_KEYS=43084
FROZEN_BASE_KEYS=42783
EXPECTED_GAPS=301
DOCS={
  "symbol_list":"https://docs.infoway.io/en-docs/rest-api/get-basic-info/get-symbol-list",
  "candles":"https://docs.infoway.io/rest-api/http-endpoints/get-candles",
}
# Official docs: type=INDICES is the documented instrument class for indices.
# Candles docs: klineType=8 is daily; timestamp is effective only for minute/hour K.
DAILY_KLINE_TYPE=8
DAILY_MAX_BARS=500

def sha256(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()

def utc_now()->str:
    return datetime.now(timezone.utc).isoformat()

def ymd_from_epoch(x)->str|None:
    try:
        return datetime.fromtimestamp(int(str(x)),tz=timezone.utc).strftime("%Y%m%d")
    except Exception:
        return None

def sanitize_headers(headers):
    keep={}
    for k,v in headers.items():
        lk=k.lower()
        if lk in {"content-type","content-length","date","server","x-request-id","x-trace-id"}:
            keep[k]=v
    return keep

def call_raw(*,method,url,api_key,payload=None):
    body=None if payload is None else json.dumps(payload,separators=(",",":")).encode()
    headers={"Accept":"application/json","User-Agent":"dao2-c-infoway-sector-probe/1.0","apiKey":api_key}
    if body is not None:
        headers["Content-Type"]="application/json"
    req=request.Request(url,data=body,headers=headers,method=method)
    ts=utc_now()
    try:
        with request.urlopen(req,timeout=60) as resp:
            raw=resp.read()
            return {
                "request_timestamp_utc":ts,
                "http_status":int(resp.status),
                "response_headers":sanitize_headers(dict(resp.headers.items())),
                "raw_bytes":raw,
                "raw_sha256":sha256(raw),
                "error":None,
            }
    except error.HTTPError as e:
        raw=e.read()
        return {
            "request_timestamp_utc":ts,
            "http_status":int(e.code),
            "response_headers":sanitize_headers(dict(e.headers.items())) if e.headers else {},
            "raw_bytes":raw,
            "raw_sha256":sha256(raw),
            "error":f"HTTPError:{e.code}",
        }
    except Exception as e:
        raw=repr(e).encode()
        return {
            "request_timestamp_utc":ts,
            "http_status":None,
            "response_headers":{},
            "raw_bytes":raw,
            "raw_sha256":sha256(raw),
            "error":f"{type(e).__name__}:{e}",
        }

def decode_json(call):
    try:
        return json.loads(call["raw_bytes"].decode("utf-8"))
    except Exception:
        return None

def write_raw(out:Path,name:str,call:dict,request_meta:dict):
    out.mkdir(parents=True,exist_ok=True)
    raw_path=out/(name+".response.bin")
    raw_path.write_bytes(call["raw_bytes"])
    meta={
      "request":request_meta,
      "request_timestamp_utc":call["request_timestamp_utc"],
      "http_status":call["http_status"],
      "response_headers":call["response_headers"],
      "raw_response_file":raw_path.name,
      "raw_response_sha256":call["raw_sha256"],
      "error":call["error"],
    }
    (out/(name+".meta.json")).write_text(json.dumps(meta,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return meta

def load_csv_gz(path:Path):
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        return list(csv.DictReader(f))

def norm_date(s):
    return str(s).replace("-","")[:8]

def exact_close_map(rows):
    out={}
    for r in rows:
        c=str(r["industry_code"])
        d=norm_date(r["trade_date"])
        out[(c,d)]=float(r["close"])
    return out

def extract_symbol_rows(body):
    if isinstance(body,dict) and isinstance(body.get("data"),list):
        return [x for x in body["data"] if isinstance(x,dict)]
    return []

def normalize_symbol_core(s):
    return re.sub(r"[^0-9]","",str(s))

def extract_kline(body,symbol):
    if not isinstance(body,dict):
        return []
    data=body.get("data")
    if not isinstance(data,list):
        return []
    rows=[]
    for item in data:
        if not isinstance(item,dict): continue
        if str(item.get("s"))!=symbol: continue
        resp=item.get("respList")
        if not isinstance(resp,list): continue
        for r in resp:
            if not isinstance(r,dict): continue
            td=ymd_from_epoch(r.get("t"))
            try: close=float(r["c"])
            except Exception: close=None
            rows.append({"trade_date":td,"t":r.get("t"),"close":close,"raw":r})
    return rows

def choose_overlap_targets(base_map):
    # Deterministic 12-row audit target. Includes legacy SW2014-only 801020 and
    # SW2021-new 801960, multiple calendar years, and multiple codes.
    desired=[
      ("801020.SI","20210601"),("801020.SI","20211101"),
      ("801010.SI","20200803"),("801030.SI","20210805"),
      ("801960.SI","20211213"),("801960.SI","20220302"),
      ("801960.SI","20230907"),("801010.SI","20240102"),
      ("801030.SI","20250102"),("801040.SI","20251008"),
      ("801960.SI","20260302"),("801010.SI","20260416"),
    ]
    got=[x for x in desired if x in base_map]
    # Fail closed if any deterministic target is absent; do not silently swap dates.
    return desired,got

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--required-keys",type=Path,required=True)
    ap.add_argument("--base-panel",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    raw_dir=args.out/"raw"
    primary=os.environ.get("INFOWAY_API_KEY_PRIMARY","").strip()
    legacy=os.environ.get("INFOWAY_API_KEY_LEGACY","").strip()
    api_key=primary or legacy
    credential_source="INFOWAY_API_KEY" if primary else ("TUSHARE_TOKEN_LEGACY_INFOWAY_FALLBACK" if legacy else None)
    if not api_key:
        raise RuntimeError("No Infoway credential present in INFOWAY_API_KEY or legacy fallback")

    req_rows=load_csv_gz(args.required_keys)
    base_rows=load_csv_gz(args.base_panel)
    required={(str(r["industry_code"]),norm_date(r["trade_date"])) for r in req_rows}
    base_map=exact_close_map(base_rows)
    base=set(base_map)
    assert len(required)==REQUIRED_KEYS,len(required)
    assert len(base)==FROZEN_BASE_KEYS,len(base)
    assert base.issubset(required)
    missing=sorted(required-base)
    assert len(missing)==EXPECTED_GAPS,len(missing)
    missing_codes=sorted({c for c,_ in missing})
    missing_dates=sorted({d for _,d in missing})
    for c in TARGET_CODES:
        if c not in missing_codes:
            raise RuntimeError(f"probe code is not a real missing industry_code: {c}")
    for d in PRIORITY_GAP_DATES:
        if d not in missing_dates:
            raise RuntimeError(f"probe date is not a real gap date: {d}")

    result={
      "artifact":"DAO2_C_INFOWAY_SECTOR_EXACT_GAP_PROBE_V1",
      "version":"1.0",
      "provider":"INFOWAY",
      "credential_source":credential_source,
      "status":"RUNNING",
      "run_timestamp_utc":utc_now(),
      "frozen_input":{
        "required_keys":len(required),
        "frozen_observed_base":len(base),
        "exact_missing":len(missing),
        "gap_dates":missing_dates,
        "frozen_base_rewritten":False,
      },
      "probe_scope":{
        "target_codes":TARGET_CODES,
        "priority_gap_dates":PRIORITY_GAP_DATES,
        "daily_kline_type":DAILY_KLINE_TYPE,
        "daily_max_bars":DAILY_MAX_BARS,
        "daily_timestamp_targeting_documented":False,
        "daily_timestamp_note":"Infoway candles documentation states timestamp only applies to minute/hour K; daily exact-date targeting is not documented.",
      },
      "documentation":DOCS,
      "raw_evidence":[],
      "symbol_capability":{},
      "history_capability":{},
      "overlap_validation":{},
      "recovery_gate":{"allowed":False},
      "decision":{},
    }

    # Phase 1A: documented index-class exact symbol lookup.
    q=parse.urlencode({"type":"INDICES","symbols":",".join(TARGET_CODES)})
    url=SYMBOLS_URL+"?"+q
    call=call_raw(method="GET",url=url,api_key=api_key)
    meta=write_raw(raw_dir,"01_symbols_exact",call,{"method":"GET","endpoint":SYMBOLS_URL,"params":{"type":"INDICES","symbols":TARGET_CODES}})
    result["raw_evidence"].append(meta)
    body=decode_json(call)
    exact_rows=extract_symbol_rows(body)
    exact_found=sorted({str(r.get("symbol")) for r in exact_rows if r.get("symbol")})
    exact_missing=[c for c in TARGET_CODES if c not in exact_found]

    mapping_matches={}
    full_body=None
    if exact_missing:
        time.sleep(1.2)
        q=parse.urlencode({"type":"INDICES"})
        full_url=SYMBOLS_URL+"?"+q
        full_call=call_raw(method="GET",url=full_url,api_key=api_key)
        full_meta=write_raw(raw_dir,"02_symbols_full_indices",full_call,{"method":"GET","endpoint":SYMBOLS_URL,"params":{"type":"INDICES"}})
        result["raw_evidence"].append(full_meta)
        full_body=decode_json(full_call)
        full_rows=extract_symbol_rows(full_body)
        for code in exact_missing:
            core=normalize_symbol_core(code)
            matches=[r for r in full_rows if normalize_symbol_core(r.get("symbol",""))==core]
            mapping_matches[code]=matches[:20]

    mapped={}
    for c in TARGET_CODES:
        if c in exact_found:
            mapped[c]=c
        elif len(mapping_matches.get(c,[]))==1 and mapping_matches[c][0].get("symbol"):
            mapped[c]=str(mapping_matches[c][0]["symbol"])

    result["symbol_capability"]={
      "endpoint":SYMBOLS_URL,
      "documented_type":"INDICES",
      "exact_si_symbols_found":[c for c in TARGET_CODES if c in exact_found],
      "exact_si_symbols_missing":exact_missing,
      "documented_mapping_matches":mapping_matches,
      "admitted_symbol_mapping":mapped,
      "all_probe_codes_mapped":all(c in mapped for c in TARGET_CODES),
    }

    # If no documented mapping for the exact SW codes, close route A immediately.
    if not mapped:
        result["status"]="INFOWAY_SW_INDEX_UNSUPPORTED"
        result["decision"]={"case":"A","code":"INFOWAY_SW_INDEX_UNSUPPORTED","reason":"No targeted SW industry code was returned by the documented INDICES symbol mapping endpoint."}
        (args.out/"probe.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(result["decision"],ensure_ascii=False))
        return

    # Phase 1B: historical daily-bar capability. Daily timestamp targeting is not documented,
    # so request the maximum documented daily history and measure the actual returned window.
    hist={}
    for i,src_code in enumerate(TARGET_CODES,1):
        symbol=mapped.get(src_code)
        if not symbol:
            hist[src_code]={"supported":False,"reason":"NO_DOCUMENTED_SYMBOL_MAPPING"}
            continue
        if i>1: time.sleep(1.2)
        payload={"klineType":DAILY_KLINE_TYPE,"klineNum":DAILY_MAX_BARS,"codes":symbol}
        call=call_raw(method="POST",url=KLINE_URL,api_key=api_key,payload=payload)
        meta=write_raw(raw_dir,f"1{i:02d}_daily_{src_code.replace('.','_')}",call,{"method":"POST","endpoint":KLINE_URL,"json":payload})
        result["raw_evidence"].append(meta)
        body=decode_json(call)
        bars=extract_kline(body,symbol)
        dates=sorted({x["trade_date"] for x in bars if x["trade_date"]})
        gap_hits={}
        for d in PRIORITY_GAP_DATES:
            vals=[x["close"] for x in bars if x["trade_date"]==d and x["close"] is not None]
            gap_hits[d]=vals
        hist[src_code]={
          "mapped_symbol":symbol,
          "http_status":call["http_status"],
          "api_ret":body.get("ret") if isinstance(body,dict) else None,
          "api_msg":body.get("msg") if isinstance(body,dict) else None,
          "returned_bars":len(bars),
          "earliest_returned_date":dates[0] if dates else None,
          "latest_returned_date":dates[-1] if dates else None,
          "target_gap_date_hits":gap_hits,
          "raw_response_sha256":call["raw_sha256"],
          "close_field_observed":any(x["close"] is not None for x in bars),
        }
    result["history_capability"]=hist

    target_exact_hits=[]
    for code,info in hist.items():
        for d,vals in info.get("target_gap_date_hits",{}).items():
            if vals:
                target_exact_hits.append({"industry_code":code,"trade_date":d,"close_values":vals})

    # Phase 2: deterministic overlap audit. It only passes if all targeted rows are actually
    # present in Infoway returned daily bars and exact/tolerance comparison succeeds.
    desired_overlap,existing_overlap=choose_overlap_targets(base_map)
    overlap_rows=[]
    overlap_missing=[]
    by_source={}
    # Reuse already captured bars by decoding raw files to avoid any extra provider requests.
    for src_code in TARGET_CODES:
        info=hist.get(src_code,{})
        symbol=info.get("mapped_symbol")
        if not symbol: continue
        meta_match=[m for m in result["raw_evidence"] if m["request"].get("json",{}).get("codes")==symbol and m["request"].get("json",{}).get("klineType")==DAILY_KLINE_TYPE]
        if not meta_match: continue
        raw=(raw_dir/meta_match[0]["raw_response_file"]).read_bytes()
        try: b=json.loads(raw.decode("utf-8"))
        except Exception: b=None
        by_source[src_code]=extract_kline(b,symbol)

    for code,d in desired_overlap:
        if (code,d) not in base_map:
            overlap_missing.append({"industry_code":code,"trade_date":d,"reason":"NOT_IN_FROZEN_BASE"})
            continue
        candidates=[x for x in by_source.get(code,[]) if x["trade_date"]==d and x["close"] is not None]
        if len(candidates)!=1:
            overlap_missing.append({"industry_code":code,"trade_date":d,"reason":"INFOWAY_EXACT_DATE_NOT_RETURNED","match_count":len(candidates)})
            continue
        inf=float(candidates[0]["close"]); ex=float(base_map[(code,d)])
        ad=abs(inf-ex); rd=(ad/abs(ex) if ex else None); bp=(rd*10000 if rd is not None else None)
        raw_meta=next((m for m in result["raw_evidence"] if m["request"].get("json",{}).get("codes")==hist[code].get("mapped_symbol")),None)
        overlap_rows.append({
          "industry_code":code,"trade_date":d,
          "existing_accepted_close":ex,"infoway_close":inf,
          "absolute_diff":ad,"relative_diff":rd,"bp_diff":bp,
          "endpoint":KLINE_URL,
          "raw_response_sha256":raw_meta["raw_response_sha256"] if raw_meta else None,
        })
    exact_pass=(len(overlap_rows)>=10 and len(overlap_missing)==0 and all(r["absolute_diff"]<=1e-8 for r in overlap_rows))
    tolerance_pass=(len(overlap_rows)>=10 and len(overlap_missing)==0 and all((r["bp_diff"] or 0)<=0.01 for r in overlap_rows))
    result["overlap_validation"]={
      "desired_rows":len(desired_overlap),
      "existing_frozen_targets":len(existing_overlap),
      "compared_rows":len(overlap_rows),
      "rows":overlap_rows,
      "missing":overlap_missing,
      "covers_sw2014_era":any(r["industry_code"]=="801020.SI" for r in overlap_rows),
      "covers_sw2021_era":any(r["industry_code"]=="801960.SI" for r in overlap_rows),
      "exact_pass":exact_pass,
      "tolerance_pass_0_01bp":tolerance_pass,
      "pass":exact_pass,
    }

    earliest=[x.get("earliest_returned_date") for x in hist.values() if x.get("earliest_returned_date")]
    earliest_available=min(earliest) if earliest else None
    all_gap_dates_accessible=all(
        any(info.get("target_gap_date_hits",{}).get(d) for info in hist.values())
        for d in PRIORITY_GAP_DATES
    )

    if not all(c in mapped for c in TARGET_CODES):
        result["status"]="INFOWAY_SW_INDEX_PARTIAL_UNSUPPORTED"
        result["decision"]={"case":"A","code":"INFOWAY_SW_INDEX_UNSUPPORTED","reason":"At least one required probe SW industry code lacks a documented INDICES symbol mapping.","mapped":mapped}
    elif not target_exact_hits:
        result["status"]="INFOWAY_HISTORY_WINDOW_DOES_NOT_REACH_GAPS"
        result["decision"]={
          "case":"B","code":"INFOWAY_SW_INDEX_HISTORY_WINDOW_INSUFFICIENT",
          "earliest_returned_daily_date":earliest_available,
          "exact_gap_hits":0,
          "reason":"Mapped SW indices are queryable, but the documented daily endpoint did not return any targeted 2021-2023 gap date under the current plan; daily timestamp targeting is not documented.",
          "next_action":"Evaluate Custom Plan only; do not retry public-plan exact-gap recovery."
        }
    elif not exact_pass:
        result["status"]="INFOWAY_OVERLAP_NOT_VALIDATED"
        result["decision"]={
          "case":"D","code":"INFOWAY_SECTOR_CLOSE_SEMANTIC_MISMATCH" if overlap_rows else "INFOWAY_OVERLAP_HISTORY_NOT_EXECUTABLE",
          "reason":"Target gap access exists but the required 10+ row cross-era overlap validation did not PASS.",
        }
    else:
        result["status"]="PASS_CAPABILITY_AND_OVERLAP"
        result["recovery_gate"]={"allowed":True,"reason":"Mapped SW index daily data reached target gaps and 10+ deterministic cross-era overlap rows exact-matched."}
        result["decision"]={"case":"C","code":"INFOWAY_TARGETED_RECOVERY_ALLOWED","reason":"Proceed to query only the 301 missing keys; frozen 42,783 rows remain immutable."}

    canonical=json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    result["artifact_sha256_without_hash_field"]=sha256(canonical.encode())
    (args.out/"probe.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
      "status":result["status"],
      "decision":result["decision"],
      "symbol_capability":result["symbol_capability"],
      "earliest_returned_daily_date":earliest_available,
      "target_exact_hits":target_exact_hits,
      "overlap_compared":len(overlap_rows),
      "overlap_pass":result["overlap_validation"].get("pass"),
      "recovery_allowed":result["recovery_gate"].get("allowed"),
    },ensure_ascii=False))

if __name__=="__main__":
    main()
