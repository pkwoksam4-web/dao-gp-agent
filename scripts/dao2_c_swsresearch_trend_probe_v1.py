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
        "version": "1.0",
        "module_id": "C",
        "component": "sector_series",
        "started_at_utc": started,
        "endpoint": URL,
        "params": {"swindexcode": SYMBOL, "period": "DAY"},
        "source_class": "OFFICIAL_SWSRESEARCH_PUBLIC_API",
        "target_dates": TARGET_DATES,
        "neighbor_dates": NEIGHBOR_DATES,
        "admitted_rows": 0,
        "series_checkpoint_changed_to_pass": False,
        "breadth_gate_open": False,
    }

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        r = requests.get(
            URL,
            params={"swindexcode": SYMBOL, "period": "DAY"},
            headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/plain,*/*"},
            timeout=(10, 30),
            verify=False,
        )
        raw = r.content
        (raw_dir / "801020_DAY.response.bin").write_bytes(raw)
        host = (urlparse(r.url).hostname or "").lower()
        official = host == "swsresearch.com" or host.endswith(".swsresearch.com")
        meta["http"] = {
            "status": int(r.status_code),
            "final_url": r.url,
            "final_host": host,
            "official_host": official,
            "content_type": r.headers.get("Content-Type"),
            "raw_bytes": len(raw),
            "raw_sha256": sha256(raw),
        }
    except Exception as exc:
        meta["status"] = "FAIL_TRANSPORT"
        meta["error"] = f"{type(exc).__name__}:{exc}"
        (out / "probe_result.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 2

    rows = normalize_trend_rows(raw)
    selected = [r for r in rows if r["trade_date"] in ALL_DATES]
    selected.sort(key=lambda x: x["trade_date"])
    pd.DataFrame(selected).to_csv(out / "801020_target_neighbor_ohlc.csv", index=False)
    (out / "801020_target_neighbor_ohlc.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    base = load_base(Path(args.base_panel))
    overlap = validate_neighbor_overlap(selected, base)
    present = {r["trade_date"] for r in selected}
    target_present = [d for d in TARGET_DATES if d in present]
    neighbor_present = [d for d in NEIGHBOR_DATES if d in present]
    unique_keys = len({(r["industry_code"], r["trade_date"]) for r in selected}) == len(selected)
    targets_complete = len(target_present) == 3
    neighbors_complete = len(neighbor_present) == 6

    pass_candidate = (
        meta["http"]["status"] == 200
        and meta["http"]["official_host"]
        and unique_keys
        and targets_complete
        and neighbors_complete
        and overlap["status"] == "PASS_EXACT_NEIGHBOR_OVERLAP"
    )
    meta.update(
        {
            "normalized_source_rows": len(rows),
            "selected_rows": len(selected),
            "selected_unique_keys": unique_keys,
            "target_presence": {"present": target_present, "required": TARGET_DATES, "complete": targets_complete},
            "neighbor_presence": {"present": neighbor_present, "required": NEIGHBOR_DATES, "complete": neighbors_complete},
            "neighbor_overlap": overlap,
            "status": "PASS_RAW_DIRECT_CANDIDATE_NOT_ADMITTED" if pass_candidate else "FAIL_NOT_ADMISSIBLE",
            "decision": "AUTHORITATIVE_DIRECT_RAW_CANDIDATE_READY_FOR_SEPARATE_ADMISSION" if pass_candidate else "DO_NOT_ADMIT",
            "admitted_rows": 0,
            "completed_at_utc": now_utc(),
        }
    )
    (out / "probe_result.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if pass_candidate else 3


if __name__ == "__main__":
    raise SystemExit(main())
