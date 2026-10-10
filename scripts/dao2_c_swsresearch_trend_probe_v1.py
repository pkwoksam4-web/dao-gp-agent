from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
import urllib3

URL = "https://www.swsresearch.com/institute-sw/api/index_publish/trend/"
ANALYSIS_URL = "https://www.swsresearch.com/institute-sw/api/index_analysis/index_analysis_report/"
SYMBOL = "801020"
TARGET_DATES = ["20210806", "20211008", "20211022"]
NEIGHBOR_DATES = ["20210805", "20210809", "20210930", "20211011", "20211021", "20211025"]
ALL_DATES = set(TARGET_DATES + NEIGHBOR_DATES)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm_date(value) -> str | None:
    if value is None:
        return None
    x = pd.to_datetime(str(value), errors="coerce")
    if pd.isna(x):
        return None
    return x.strftime("%Y%m%d")


def finite(value) -> float | None:
    try:
        x = float(str(value).replace(",", "").strip())
    except Exception:
        return None
    return x if math.isfinite(x) else None


def positive(value) -> float | None:
    x = finite(value)
    return x if x is not None and x > 0 else None


def normalize_trend_rows(raw: bytes) -> list[dict]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return []
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for r in data:
        if not isinstance(r, dict):
            continue
        code = str(r.get("swindexcode") or "").strip()
        date = norm_date(r.get("bargaindate"))
        o = positive(r.get("openindex"))
        h = positive(r.get("maxindex"))
        l = positive(r.get("minindex"))
        c = positive(r.get("closeindex"))
        if code != SYMBOL or not date or None in (o, h, l, c):
            continue
        out.append(
            {
                "industry_code": code + ".SI",
                "trade_date": date,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": finite(r.get("bargainamount")),
                "amount": finite(r.get("bargainsum")),
            }
        )
    return out


def normalize_analysis_rows(raw: bytes) -> list[dict]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return []
    data = payload.get("data") if isinstance(payload, dict) else None
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        return []
    out: list[dict] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        code = str(r.get("swindexcode") or "").strip()
        date = norm_date(r.get("bargaindate"))
        close = positive(r.get("closeindex"))
        if code != SYMBOL or not date or close is None:
            continue
        out.append(
            {
                "industry_code": code + ".SI",
                "trade_date": date,
                "close": close,
                "volume": finite(r.get("bargainamount")),
                "markup": finite(r.get("markup")),
            }
        )
    return out


def validate_neighbor_overlap(source_rows: list[dict], base: dict[tuple[str, str], float]) -> dict:
    src = {(r["industry_code"], r["trade_date"]): float(r["close"]) for r in source_rows}
    details = []
    matched = 0
    for d in NEIGHBOR_DATES:
        key = ("801020.SI", d)
        s = src.get(key)
        b = base.get(key)
        ok = s is not None and b is not None and abs(float(s) - float(b)) <= 1e-9
        matched += int(ok)
        details.append({"industry_code": key[0], "trade_date": d, "source_close": s, "base_close": b, "exact": ok})
    return {
        "status": "PASS_EXACT_NEIGHBOR_OVERLAP" if matched == len(NEIGHBOR_DATES) else "FAIL_NEIGHBOR_OVERLAP",
        "matched": matched,
        "required": len(NEIGHBOR_DATES),
        "details": details,
    }


def load_base(path: Path) -> dict[tuple[str, str], float]:
    df = pd.read_csv(path, compression="infer")
    required = {"industry_code", "trade_date", "close"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"base panel missing columns: {missing}")
    df = df.copy()
    df["industry_code"] = df["industry_code"].astype(str).str.strip().str.upper()
    df["trade_date"] = df["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True).str.replace("-", "", regex=False)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df[df["industry_code"].eq("801020.SI") & df["trade_date"].isin(NEIGHBOR_DATES)]
    return {(r.industry_code, r.trade_date): float(r.close) for r in df.itertuples() if pd.notna(r.close)}


def official_http_meta(r: requests.Response, raw: bytes) -> dict:
    host = (urlparse(r.url).hostname or "").lower()
    official = host == "swsresearch.com" or host.endswith(".swsresearch.com")
    return {
        "status": int(r.status_code),
        "final_url": r.url,
        "final_host": host,
        "official_host": official,
        "content_type": r.headers.get("Content-Type"),
        "raw_bytes": len(raw),
        "raw_sha256": sha256(raw),
    }


def analysis_params(date: str) -> dict:
    d = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    return {
        "page": "1",
        "page_size": "100",
        "index_type": "一级行业",
        "start_date": d,
        "end_date": d,
        "type": "DAY",
        "swindexcode": "all",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-panel", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    raw_dir = out / "raw"
    raw_dir.mkdir(exist_ok=True)
    started = now_utc()

    meta = {
        "artifact": "DAO2_C_SWSRESEARCH_TREND_EXACT_GAP_PROBE_V1",
        "version": "1.1",
        "module_id": "C",
        "component": "sector_series",
        "started_at_utc": started,
        "source_class": "OFFICIAL_SWSRESEARCH_PUBLIC_API",
        "target_dates": TARGET_DATES,
        "neighbor_dates": NEIGHBOR_DATES,
        "admitted_rows": 0,
        "series_checkpoint_changed_to_pass": False,
        "breadth_gate_open": False,
    }

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json,text/plain,*/*"}
    try:
        r = requests.get(
            URL,
            params={"swindexcode": SYMBOL, "period": "DAY"},
            headers=headers,
            timeout=(10, 30),
            verify=False,
        )
        raw = r.content
        (raw_dir / "801020_DAY.response.bin").write_bytes(raw)
        meta["trend_http"] = official_http_meta(r, raw)
    except Exception as exc:
        meta["status"] = "FAIL_TREND_TRANSPORT"
        meta["error"] = f"{type(exc).__name__}:{exc}"
        (out / "probe_result.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 2

    rows = normalize_trend_rows(raw)
    selected = [r for r in rows if r["trade_date"] in ALL_DATES]
    selected.sort(key=lambda x: x["trade_date"])
    pd.DataFrame(selected).to_csv(out / "801020_target_neighbor_ohlc.csv", index=False)
    (out / "801020_target_neighbor_ohlc.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    base = load_base(Path(args.base_panel))
    trend_overlap = validate_neighbor_overlap(selected, base)
    trend_present = {r["trade_date"] for r in selected}
    trend_targets = [d for d in TARGET_DATES if d in trend_present]
    trend_neighbors = [d for d in NEIGHBOR_DATES if d in trend_present]
    trend_unique = len({(r["industry_code"], r["trade_date"]) for r in selected}) == len(selected)
    trend_candidate = (
        meta["trend_http"]["status"] == 200
        and meta["trend_http"]["official_host"]
        and trend_unique
        and len(trend_targets) == 3
        and len(trend_neighbors) == 6
        and trend_overlap["status"] == "PASS_EXACT_NEIGHBOR_OVERLAP"
    )
    meta["trend"] = {
        "endpoint": URL,
        "params": {"swindexcode": SYMBOL, "period": "DAY"},
        "normalized_source_rows": len(rows),
        "selected_rows": len(selected),
        "selected_unique_keys": trend_unique,
        "target_presence": {"present": trend_targets, "required": TARGET_DATES, "complete": len(trend_targets) == 3},
        "neighbor_presence": {"present": trend_neighbors, "required": NEIGHBOR_DATES, "complete": len(trend_neighbors) == 6},
        "neighbor_overlap": trend_overlap,
        "candidate_ready": trend_candidate,
    }

    analysis_rows: list[dict] = []
    analysis_calls: list[dict] = []
    for d in TARGET_DATES + NEIGHBOR_DATES:
        params = analysis_params(d)
        try:
            ar = requests.get(ANALYSIS_URL, params=params, headers=headers, timeout=(10, 30), verify=False)
            araw = ar.content
            (raw_dir / f"analysis_{d}.response.bin").write_bytes(araw)
            hmeta = official_http_meta(ar, araw)
            parsed = normalize_analysis_rows(araw)
            analysis_rows.extend([x for x in parsed if x["trade_date"] == d])
            analysis_calls.append({"trade_date": d, "params": params, "http": hmeta, "parsed_801020_rows": len([x for x in parsed if x["trade_date"] == d])})
        except Exception as exc:
            analysis_calls.append({"trade_date": d, "params": params, "error": f"{type(exc).__name__}:{exc}", "parsed_801020_rows": 0})

    analysis_rows.sort(key=lambda x: x["trade_date"])
    pd.DataFrame(analysis_rows).to_csv(out / "801020_analysis_target_neighbor_close.csv", index=False)
    (out / "801020_analysis_target_neighbor_close.json").write_text(json.dumps(analysis_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    analysis_overlap = validate_neighbor_overlap(analysis_rows, base)
    analysis_present = {r["trade_date"] for r in analysis_rows}
    analysis_targets = [d for d in TARGET_DATES if d in analysis_present]
    analysis_neighbors = [d for d in NEIGHBOR_DATES if d in analysis_present]
    analysis_unique = len({(r["industry_code"], r["trade_date"]) for r in analysis_rows}) == len(analysis_rows)
    analysis_http_ok = all(c.get("http", {}).get("status") == 200 and c.get("http", {}).get("official_host") for c in analysis_calls)
    analysis_candidate = (
        analysis_http_ok
        and analysis_unique
        and len(analysis_targets) == 3
        and len(analysis_neighbors) == 6
        and analysis_overlap["status"] == "PASS_EXACT_NEIGHBOR_OVERLAP"
    )
    meta["analysis"] = {
        "endpoint": ANALYSIS_URL,
        "index_type": "一级行业",
        "calls": analysis_calls,
        "selected_rows": len(analysis_rows),
        "selected_unique_keys": analysis_unique,
        "target_presence": {"present": analysis_targets, "required": TARGET_DATES, "complete": len(analysis_targets) == 3},
        "neighbor_presence": {"present": analysis_neighbors, "required": NEIGHBOR_DATES, "complete": len(analysis_neighbors) == 6},
        "neighbor_overlap": analysis_overlap,
        "candidate_ready": analysis_candidate,
        "provenance_note": "Official same-day closeindex carrier; not admitted by this probe and current provider contract must be reviewed separately before any Series change.",
    }

    if trend_candidate:
        status = "PASS_TREND_RAW_DIRECT_CANDIDATE_NOT_ADMITTED"
        decision = "TREND_AUTHORITATIVE_DIRECT_RAW_CANDIDATE_READY_FOR_SEPARATE_ADMISSION"
        rc = 0
    elif analysis_candidate:
        status = "PASS_ANALYSIS_DIRECT_CLOSE_CANDIDATE_NOT_ADMITTED"
        decision = "SECONDARY_OFFICIAL_DIRECT_CLOSE_CARRIER_READY_FOR_GOVERNANCE_REVIEW"
        rc = 0
    else:
        status = "FAIL_NO_DIRECT_TARGET_CARRIER"
        decision = "DO_NOT_ADMIT"
        rc = 3

    meta.update(
        {
            "status": status,
            "decision": decision,
            "admitted_rows": 0,
            "series_checkpoint_changed_to_pass": False,
            "breadth_gate_open": False,
            "completed_at_utc": now_utc(),
        }
    )
    (out / "probe_result.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
