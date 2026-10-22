from __future__ import annotations

import argparse
import ast
import csv
import gzip
import hashlib
import io
import json
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse

import pandas as pd
import requests

REQUIRED_COUNT = 43084
FROZEN_COUNT = 42783
MISSING_COUNT = 301
ALLOWED_OFFICIAL_SUFFIXES = ("swsindex.com", "swsresearch.com")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
REFERER = "http://www.swsindex.com/idx0560.aspx?columnid=8905"

TARGETS = [
    ("801020.SI", "20210806"),
    ("801960.SI", "20220303"),
    ("801010.SI", "20230908"),
    ("801030.SI", "20220303"),
    ("801040.SI", "20211022"),
]

HISTORICAL_IMPLEMENTATIONS = [
    {
        "repo": "PKUJohnson/OpenData",
        "commit": "e9488201d0d14741cc247f780dcfa6141018a0d8",
        "path": "opendatatools/swindex/swindex_agent.py",
        "evidence": "excel2.aspx ctable=swindexhistory; excel.aspx ctable=V_Report type=Day",
    },
    {
        "repo": "DTShare/dtshare",
        "commit": "6274c0bf14a4eaa3da33c56b4d4d293261025686",
        "path": "dtshare/index/index_sw.py",
        "evidence": "excel2.aspx ctable=swindexhistory; V_Report daily indicator",
    },
    {
        "repo": "kingofhawks/stocktrace",
        "commit": "963fb79651d698ed65d0330e206dc3c0535b9259",
        "path": "market/sw.py",
        "evidence": "POST handler.aspx tablename=swindexhistory and V_Report",
    },
    {
        "repo": "venyowong/V.ClassLibrary",
        "commit": "6d39cb584393018d491ff96ebdee6df448442184",
        "path": "V.Finance/Services/IndexService.cs",
        "evidence": "GET handler.aspx swindexhistory fieldlist with CloseIndex/OpenIndex/MaxIndex/MinIndex",
    },
    {
        "repo": "epsimatic88/myData",
        "commit": "ef07e833d4200da6f47d08c133c4fc7f773f0399",
        "path": "R/MarketIndex/fromSW_industry_index.R",
        "evidence": "browser headers + excel2.aspx swindexhistory",
    },
]

FAMILIES = ["A_HANDLER_SWINDEXHISTORY", "B_EXCEL2_SWINDEXHISTORY", "C_HANDLER_V_REPORT_DAY"]
SCHEMES = ["https", "http"]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def official_host(host: str | None) -> bool:
    h = (host or "").lower().split(":")[0]
    return any(h == s or h.endswith("." + s) for s in ALLOWED_OFFICIAL_SUFFIXES)


def norm_date(value) -> str | None:
    if value is None:
        return None
    x = pd.to_datetime(str(value), errors="coerce")
    if pd.isna(x):
        return None
    return x.strftime("%Y%m%d")


def norm_code(value) -> str:
    return str(value or "").strip().upper().replace(".SI", "")[:6]


def finite_positive(value) -> float | None:
    try:
        x = float(str(value).replace(",", "").strip())
    except Exception:
        return None
    return x if math.isfinite(x) and x > 0 else None


def read_gz(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def where_exact(code: str, date: str, *, v_report: bool = False) -> str:
    c = norm_code(code)
    d = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    q = f"swindexcode in ('{c}') and BargainDate >= '{d}' and BargainDate <= '{d}'"
    if v_report:
        q += " and type='Day'"
    return q


def where_many(codes: list[str], date: str, *, v_report: bool = False) -> str:
    cs = "','".join(norm_code(c) for c in codes)
    d = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    q = f"swindexcode in ('{cs}') and BargainDate >= '{d}' and BargainDate <= '{d}'"
    if v_report:
        q += " and type='Day'"
    return q


@dataclass
class RawCall:
    request_id: str
    family: str
    scheme: str
    method: str
    initial_url: str
    params: dict | None
    form: dict | None
    timestamp_utc: str
    hops: list[dict]
    final_status: int | None
    final_url: str | None
    final_content_type: str | None
    final_raw: bytes
    final_sha256: str
    error: str | None
    redirect_rejected: bool = False


class OfficialSession:
    def __init__(self, raw_dir: Path):
        self.raw_dir = raw_dir
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Referer": REFERER,
            "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        })

    def call(self, *, request_id: str, family: str, scheme: str, method: str,
             url: str, params: dict | None = None, form: dict | None = None) -> RawCall:
        timestamp = now_utc()
        current_url = url
        current_method = method
        current_params = params
        current_form = form
        hops = []
        final_raw = b""
        final_status = None
        final_url = None
        final_ct = None
        err = None
        rejected = False

        for hop_no in range(6):
            try:
                resp = self.session.request(
                    current_method,
                    current_url,
                    params=current_params,
                    data=current_form,
                    timeout=(6, 12),
                    allow_redirects=False,
                )
                raw = resp.content
                hop = {
                    "hop": hop_no,
                    "method": current_method,
                    "requested_url": resp.request.url,
                    "status": int(resp.status_code),
                    "location": resp.headers.get("Location"),
                    "content_type": resp.headers.get("Content-Type"),
                    "raw_sha256": sha256(raw),
                    "raw_bytes": len(raw),
                }
                hops.append(hop)
                (self.raw_dir / f"{request_id}.hop{hop_no}.bin").write_bytes(raw)
                final_raw = raw
                final_status = int(resp.status_code)
                final_url = resp.request.url
                final_ct = resp.headers.get("Content-Type")
                if resp.is_redirect or resp.is_permanent_redirect:
                    location = resp.headers.get("Location")
                    if not location:
                        err = "REDIRECT_WITHOUT_LOCATION"
                        break
                    nxt = urljoin(resp.request.url, location)
                    if not official_host(urlparse(nxt).hostname):
                        err = f"NON_OFFICIAL_REDIRECT_REJECTED:{nxt}"
                        rejected = True
                        break
                    # Browser-compatible redirect semantics.
                    if resp.status_code in (301, 302, 303) and current_method.upper() == "POST":
                        current_method = "GET"
                        current_form = None
                        current_params = None
                    else:
                        current_params = None
                    current_url = nxt
                    continue
                break
            except Exception as exc:
                err = f"{type(exc).__name__}:{exc}"
                final_raw = repr(exc).encode("utf-8")
                final_url = current_url
                break

        call = RawCall(
            request_id=request_id,
            family=family,
            scheme=scheme,
            method=method,
            initial_url=url,
            params=params,
            form=form,
            timestamp_utc=timestamp,
            hops=hops,
            final_status=final_status,
            final_url=final_url,
            final_content_type=final_ct,
            final_raw=final_raw,
            final_sha256=sha256(final_raw),
            error=err,
            redirect_rejected=rejected,
        )
        meta = {
            "request_id": request_id,
            "family": family,
            "scheme": scheme,
            "method": method,
            "initial_url": url,
            "params": params,
            "form": form,
            "request_timestamp_utc": timestamp,
            "redirect_chain": hops,
            "final_status": final_status,
            "final_url": final_url,
            "final_content_type": final_ct,
            "final_raw_sha256": call.final_sha256,
            "final_raw_bytes": len(final_raw),
            "error": err,
            "redirect_rejected": rejected,
        }
        (self.raw_dir / f"{request_id}.meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return call


def parse_handler(raw: bytes) -> list[dict]:
    if not raw:
        return []
    text = raw.decode("utf-8", errors="replace").strip()
    candidates = [text, text.replace("'", '"')]
    obj = None
    for c in candidates:
        try:
            obj = json.loads(c)
            break
        except Exception:
            pass
    if obj is None:
        try:
            obj = ast.literal_eval(text)
        except Exception:
            return []
    if isinstance(obj, dict):
        root = obj.get("root")
        if isinstance(root, list):
            return [x for x in root if isinstance(x, dict)]
    return []


def parse_excel_html(raw: bytes) -> list[dict]:
    if not raw:
        return []
    for enc in ("utf-8", "gb18030", "latin1"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            text = None
    if not text:
        return []
    try:
        tables = pd.read_html(io.StringIO(text))
    except Exception:
        return []
    out = []
    for t in tables:
        if t.shape[1] < 7:
            continue
        # Historical implementations establish column order:
        # code,name,date,open,high,low,close,vol,amount,change
        for _, r in t.iterrows():
            vals = [r.iloc[i] if i < len(r) else None for i in range(min(len(r), 10))]
            code = norm_code(vals[0])
            date = norm_date(vals[2])
            close = finite_positive(vals[6])
            if len(code) == 6 and date and close is not None:
                out.append({
                    "SwIndexCode": code,
                    "SwIndexName": str(vals[1]),
                    "BargainDate": date,
                    "OpenIndex": vals[3],
                    "MaxIndex": vals[4],
                    "MinIndex": vals[5],
                    "CloseIndex": close,
                })
    return out


def normalize_rows(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        # Handler historically returns the same semantic field names.
        code = norm_code(r.get("SwIndexCode") or r.get("swindexcode") or r.get("IndexCode"))
        date = norm_date(r.get("BargainDate") or r.get("bargaindate") or r.get("Date"))
        close = finite_positive(r.get("CloseIndex") or r.get("closeindex") or r.get("Close"))
        if len(code) != 6 or not date or close is None:
            continue
        out.append({
            "industry_code": code + ".SI",
            "trade_date": date,
            "close": close,
            "raw_row": r,
        })
    return out


def make_request(family: str, scheme: str, where: str) -> tuple[str, str, dict | None, dict | None]:
    host = f"{scheme}://www.swsindex.com"
    fields = "SwIndexCode,SwIndexName,BargainDate,CloseIndex,OpenIndex,MaxIndex,MinIndex,BargainAmount,Markup,BargainSum"
    if family == "A_HANDLER_SWINDEXHISTORY":
        url = host + "/handler.aspx"
        form = {
            "tablename": "swindexhistory",
            "key": "id",
            "p": "1",
            "where": where,
            "orderby": "swindexcode asc,BargainDate_1",
            "fieldlist": fields,
            "pagecount": "2000",
            "timed": str(int(time.time() * 1000)),
        }
        return "POST", url, None, form
    if family == "B_EXCEL2_SWINDEXHISTORY":
        url = host + "/excel2.aspx"
        params = {"ctable": "swindexhistory", "where": where}
        return "GET", url, params, None
    if family == "C_HANDLER_V_REPORT_DAY":
        url = host + "/handler.aspx"
        form = {
            "tablename": "V_Report",
            "key": "id",
            "p": "1",
            "where": where,
            "orderby": "swindexcode asc,BargainDate_1",
            "fieldlist": fields,
            "pagecount": "2000",
            "timed": str(int(time.time() * 1000)),
        }
        return "POST", url, None, form
    raise ValueError(family)


def parse_call(family: str, call: RawCall) -> list[dict]:
    if family == "B_EXCEL2_SWINDEXHISTORY":
        return normalize_rows(parse_excel_html(call.final_raw))
    return normalize_rows(parse_handler(call.final_raw))


def exact_matches(rows: list[dict], code: str, date: str) -> list[dict]:
    return [r for r in rows if r["industry_code"] == code and r["trade_date"] == date]


def pick_overlap(base: pd.DataFrame) -> list[tuple[str, str]]:
    base = base.copy()
    base["trade_date"] = base["trade_date"].astype(str)
    wanted = [
        ("801020.SI", 2020), ("801020.SI", 2021),
        ("801010.SI", 2020), ("801030.SI", 2021), ("801040.SI", 2021),
        ("801960.SI", 2021), ("801960.SI", 2022), ("801960.SI", 2023),
        ("801010.SI", 2022), ("801030.SI", 2023), ("801040.SI", 2024),
        ("801010.SI", 2024), ("801030.SI", 2025), ("801040.SI", 2025),
        ("801960.SI", 2025), ("801010.SI", 2026),
    ]
    out = []
    for code, year in wanted:
        g = base.loc[
            base["industry_code"].eq(code)
            & base["trade_date"].str.startswith(str(year))
        ].sort_values("trade_date")
        if g.empty:
            continue
        # deterministic middle valid frozen row, avoiding any known gap by construction
        row = g.iloc[len(g)//2]
        out.append((code, str(row["trade_date"])))
    return out


def query_exact(session: OfficialSession, *, family: str, scheme: str,
                code: str, date: str, prefix: str) -> tuple[RawCall, list[dict]]:
    where = where_exact(code, date, v_report=(family == "C_HANDLER_V_REPORT_DAY"))
    method, url, params, form = make_request(family, scheme, where)
    rid = f"{prefix}_{family}_{scheme}_{norm_code(code)}_{date}"
    call = session.call(
        request_id=rid, family=family, scheme=scheme, method=method,
        url=url, params=params, form=form
    )
    rows = parse_call(family, call)
    return call, rows


def query_many_for_date(session: OfficialSession, *, family: str, scheme: str,
                        codes: list[str], date: str, prefix: str) -> tuple[RawCall, list[dict]]:
    where = where_many(codes, date, v_report=(family == "C_HANDLER_V_REPORT_DAY"))
    method, url, params, form = make_request(family, scheme, where)
    rid = f"{prefix}_{family}_{scheme}_{date}"
    call = session.call(
        request_id=rid, family=family, scheme=scheme, method=method,
        url=url, params=params, form=form
    )
    return call, parse_call(family, call)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--required-keys", type=Path, required=True)
    ap.add_argument("--base-panel", type=Path, required=True)
    ap.add_argument("--price-basis", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    raw_dir = args.out / "raw"

    required_df = pd.read_csv(args.required_keys, dtype=str)
    base_df = pd.read_csv(args.base_panel, dtype=str)
    price = json.loads(args.price_basis.read_text(encoding="utf-8"))
    if price.get("status") != "PASS_CANDIDATE_PRICE_BASIS_DEFINITION":
        raise RuntimeError("price basis checkpoint not PASS")

    required = set(map(tuple, required_df[["industry_code", "trade_date"]].itertuples(index=False, name=None)))
    base_keys = set(map(tuple, base_df[["industry_code", "trade_date"]].itertuples(index=False, name=None)))
    if len(required) != REQUIRED_COUNT or len(base_keys) != FROZEN_COUNT:
        raise RuntimeError((len(required), len(base_keys)))
    missing = sorted(required - base_keys)
    if len(missing) != MISSING_COUNT:
        raise RuntimeError(len(missing))
    for t in TARGETS:
        if t not in missing:
            raise RuntimeError(f"not a current exact missing key: {t}")

    base_close = {
        (str(r.industry_code), str(r.trade_date)): float(r.close)
        for r in base_df.itertuples(index=False)
    }
    session = OfficialSession(raw_dir)
    result = {
        "artifact": "DAO2_C_LEGACY_SW_HISTORY_EXACT_GAP_PROBE_V1",
        "version": "1.0",
        "status": "RUNNING",
        "provider": "SWS_LEGACY_OFFICIAL",
        "historical_implementations": HISTORICAL_IMPLEMENTATIONS,
        "frozen_inputs": {
            "required": len(required),
            "frozen_base": len(base_keys),
            "missing": len(missing),
            "frozen_base_rewritten": False,
            "price_basis_status": price.get("status"),
        },
        "targeted_capability": {
            "targets": [{"industry_code": c, "trade_date": d} for c, d in TARGETS],
            "families": FAMILIES,
            "schemes": SCHEMES,
        },
        "capability_requests": [],
        "overlap_validation": {},
        "recovery": {},
        "decision": {},
    }

    successful_variants = []
    for family in FAMILIES:
        for scheme in SCHEMES:
            variant = {
                "family": family,
                "scheme": scheme,
                "targets": [],
                "network_failures": 0,
                "exact_target_hits": 0,
            }
            circuit_open = False
            for code, date in TARGETS:
                if circuit_open:
                    variant["targets"].append({
                        "industry_code": code, "trade_date": date,
                        "status": "SKIPPED_PROVIDER_CIRCUIT_OPEN",
                    })
                    continue
                call, rows = query_exact(
                    session, family=family, scheme=scheme,
                    code=code, date=date, prefix="cap"
                )
                matches = exact_matches(rows, code, date)
                row_evidence = {
                    "industry_code": code,
                    "trade_date": date,
                    "request_id": call.request_id,
                    "http_status": call.final_status,
                    "final_url": call.final_url,
                    "content_type": call.final_content_type,
                    "redirect_chain": call.hops,
                    "raw_sha256": call.final_sha256,
                    "error": call.error,
                    "parsed_row_count": len(rows),
                    "exact_match_count": len(matches),
                    "exact_matches": matches,
                    "field_validation_pass": (
                        len(matches) == 1
                        and matches[0]["industry_code"] == code
                        and matches[0]["trade_date"] == date
                        and finite_positive(matches[0]["close"]) is not None
                    ),
                }
                variant["targets"].append(row_evidence)
                if call.error and not call.hops:
                    variant["network_failures"] += 1
                    # fail fast for dead DNS/transport but preserve evidence from both first targets
                    if variant["network_failures"] >= 2:
                        circuit_open = True
                if row_evidence["field_validation_pass"]:
                    variant["exact_target_hits"] += 1
                time.sleep(0.35)
            variant["capability_pass"] = variant["exact_target_hits"] > 0
            result["capability_requests"].append(variant)
            if variant["capability_pass"]:
                successful_variants.append(variant)

    if not successful_variants:
        statuses = []
        for v in result["capability_requests"]:
            for t in v["targets"]:
                statuses.append((t.get("http_status"), t.get("error"), t.get("parsed_row_count", 0)))
        if statuses and all((s[1] and s[0] is None) or s[2] == 0 for s in statuses):
            code = "LEGACY_SW_HISTORY_ROUTE_CLOSED_OR_EMPTY"
        else:
            code = "LEGACY_SW_HISTORY_TARGET_ROWS_UNAVAILABLE"
        result["status"] = code
        result["decision"] = {
            "route_closed": True,
            "recovery_allowed": False,
            "code": code,
            "reason": "No legacy official endpoint variant returned a unique exact target SwIndexCode/BargainDate/finite-positive CloseIndex row.",
        }
        (args.out / "probe.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result["decision"], ensure_ascii=False))
        return

    # Prefer family order A > B > C, then https > http, then target hit count.
    family_rank = {x: i for i, x in enumerate(FAMILIES)}
    scheme_rank = {"https": 0, "http": 1}
    successful_variants.sort(key=lambda v: (family_rank[v["family"]], scheme_rank[v["scheme"]], -v["exact_target_hits"]))
    chosen = successful_variants[0]
    family, scheme = chosen["family"], chosen["scheme"]

    overlaps = pick_overlap(base_df)
    if len(overlaps) < 10:
        raise RuntimeError(f"insufficient deterministic overlaps: {len(overlaps)}")
    overlap_rows, overlap_failures = [], []
    for code, date in overlaps:
        call, rows = query_exact(
            session, family=family, scheme=scheme,
            code=code, date=date, prefix="overlap"
        )
        matches = exact_matches(rows, code, date)
        if len(matches) != 1:
            overlap_failures.append({
                "industry_code": code, "trade_date": date,
                "reason": "EXACT_ROW_NOT_UNIQUE",
                "match_count": len(matches),
                "raw_sha256": call.final_sha256,
                "request_id": call.request_id,
            })
            continue
        accepted = float(base_close[(code, date)])
        legacy = float(matches[0]["close"])
        abs_diff = abs(legacy - accepted)
        rel = abs_diff / abs(accepted) if accepted else None
        bp = rel * 10000 if rel is not None else None
        overlap_rows.append({
            "industry_code": code,
            "trade_date": date,
            "accepted_close": accepted,
            "legacy_close": legacy,
            "absolute_diff": abs_diff,
            "relative_diff": rel,
            "bp_diff": bp,
            "endpoint_family": family,
            "scheme": scheme,
            "raw_sha256": call.final_sha256,
            "request_id": call.request_id,
        })
        time.sleep(0.35)

    exact_pass = len(overlap_rows) >= 10 and not overlap_failures and all(r["absolute_diff"] <= 1e-8 for r in overlap_rows)
    tolerance_pass = len(overlap_rows) >= 10 and not overlap_failures and all(
        r["absolute_diff"] <= 0.01 and (r["bp_diff"] is not None and r["bp_diff"] <= 0.01)
        for r in overlap_rows
    )
    overlap_pass = exact_pass or tolerance_pass
    result["overlap_validation"] = {
        "chosen_family": family,
        "chosen_scheme": scheme,
        "requested_rows": len(overlaps),
        "compared_rows": len(overlap_rows),
        "failures": overlap_failures,
        "rows": overlap_rows,
        "covers_sw2014_era": any(r["trade_date"] <= "20211210" for r in overlap_rows),
        "covers_sw2021_era": any(r["trade_date"] >= "20211213" for r in overlap_rows),
        "industry_codes_compared": sorted({r["industry_code"] for r in overlap_rows}),
        "years_compared": sorted({r["trade_date"][:4] for r in overlap_rows}),
        "exact_pass": exact_pass,
        "tolerance_contract": {"max_abs_diff": 0.01, "max_bp_diff": 0.01},
        "tolerance_pass": tolerance_pass,
        "pass": overlap_pass,
    }

    if not overlap_pass:
        result["status"] = "LEGACY_SW_SECTOR_CLOSE_SEMANTIC_MISMATCH"
        result["decision"] = {
            "route_closed": True,
            "recovery_allowed": False,
            "code": "LEGACY_SW_SECTOR_CLOSE_SEMANTIC_MISMATCH",
            "reason": "Legacy official capability returned target rows, but 10+ frozen-base overlap validation did not satisfy exact/tolerance contract.",
        }
        (args.out / "probe.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result["decision"], ensure_ascii=False))
        return

    # Stage 3: only exact missing keys, batched by the 10 actual gap dates.
    missing_by_date: dict[str, list[str]] = {}
    for code, date in missing:
        missing_by_date.setdefault(date, []).append(code)

    recovered = []
    recovery_requests = []
    for date in sorted(missing_by_date):
        codes = sorted(missing_by_date[date])
        call, rows = query_many_for_date(
            session, family=family, scheme=scheme,
            codes=codes, date=date, prefix="recover"
        )
        row_map = {}
        for r in rows:
            k = (r["industry_code"], r["trade_date"])
            row_map.setdefault(k, []).append(r)
        admitted_this = 0
        for code in codes:
            key = (code, date)
            matches = row_map.get(key, [])
            if len(matches) != 1:
                continue
            close = finite_positive(matches[0]["close"])
            if close is None:
                continue
            recovered.append({
                "industry_code": code,
                "trade_date": date,
                "close": close,
                "source_provider": "SWS_LEGACY_OFFICIAL",
                "source_trade_date": date,
                "fill_method": "NONE",
                "synthetic": False,
                "endpoint_family": family,
                "scheme": scheme,
                "raw_response_sha256": call.final_sha256,
                "request_id": call.request_id,
            })
            admitted_this += 1
        recovery_requests.append({
            "trade_date": date,
            "requested_codes": codes,
            "requested_key_count": len(codes),
            "parsed_rows": len(rows),
            "admitted_exact_rows": admitted_this,
            "request_id": call.request_id,
            "http_status": call.final_status,
            "final_url": call.final_url,
            "content_type": call.final_content_type,
            "redirect_chain": call.hops,
            "raw_sha256": call.final_sha256,
            "error": call.error,
        })
        time.sleep(0.35)

    rec_df = pd.DataFrame(recovered)
    if not rec_df.empty:
        rec_df.to_csv(args.out / "recovered_legacy_rows.csv", index=False)

    rec_keys = set(map(tuple, rec_df[["industry_code", "trade_date"]].itertuples(index=False, name=None))) if not rec_df.empty else set()
    exact_recovery = rec_keys == set(missing) and len(rec_df) == len(missing)
    duplicates = int(rec_df.duplicated(["industry_code", "trade_date"], keep=False).sum()) if not rec_df.empty else 0
    same_date = bool(rec_df.empty or rec_df["trade_date"].astype(str).eq(rec_df["source_trade_date"].astype(str)).all())
    fills_none = bool(rec_df.empty or rec_df["fill_method"].eq("NONE").all())
    synthetic_false = bool(rec_df.empty or (~rec_df["synthetic"].astype(bool)).all())
    finite = bool(rec_df.empty or pd.to_numeric(rec_df["close"], errors="coerce").notna().all() and (pd.to_numeric(rec_df["close"], errors="coerce") > 0).all())

    combined = pd.concat([base_df, rec_df], ignore_index=True, sort=False)
    combined_keys = set(map(tuple, combined[["industry_code", "trade_date"]].astype(str).itertuples(index=False, name=None)))
    combined_dup = int(combined.duplicated(["industry_code", "trade_date"], keep=False).sum())
    final_missing = sorted(required - combined_keys)
    combined.to_csv(args.out / "sector_close_formal_legacy_recovered.csv.gz", index=False, compression="gzip")

    final_pass = (
        exact_recovery
        and len(combined_keys) == REQUIRED_COUNT
        and not final_missing
        and combined_dup == 0
        and duplicates == 0
        and same_date and fills_none and synthetic_false and finite
    )

    result["recovery"] = {
        "chosen_family": family,
        "chosen_scheme": scheme,
        "requests": recovery_requests,
        "recovered_exact_rows": len(rec_df),
        "expected_missing_rows": len(missing),
        "exact_missing_key_set_recovered": exact_recovery,
        "duplicate_recovered_keys": duplicates,
        "same_date_provenance": same_date,
        "fill_method_none": fills_none,
        "forward_fill": False,
        "synthetic": False if synthetic_false else True,
        "finite_positive_close": finite,
        "combined_required": REQUIRED_COUNT,
        "combined_observed": len(combined_keys),
        "combined_missing": len(final_missing),
        "combined_duplicate_keys": combined_dup,
        "final_missing_sample": [{"industry_code": c, "trade_date": d} for c, d in final_missing[:50]],
        "price_basis_status": price.get("status"),
        "pass": final_pass,
    }

    if final_pass:
        result["status"] = "PASS_TARGETED_RECOVERY"
        result["decision"] = {
            "route_closed": False,
            "recovery_allowed": True,
            "code": "LEGACY_SW_TARGETED_RECOVERY_PASS",
            "reason": "Legacy official endpoint capability + overlap validation passed and all 301 exact missing keys were recovered without rewriting the frozen 42,783 rows.",
        }
    else:
        result["status"] = "LEGACY_SW_HISTORY_TARGET_301_INCOMPLETE"
        result["decision"] = {
            "route_closed": True,
            "recovery_allowed": False,
            "code": "LEGACY_SW_HISTORY_TARGET_301_INCOMPLETE",
            "reason": "Legacy official endpoint passed capability/overlap but did not recover all 301 exact missing keys.",
        }

    canonical = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    result["artifact_sha256_without_hash_field"] = sha256(canonical.encode("utf-8"))
    (args.out / "probe.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "decision": result["decision"],
        "capability_success_variants": [
            {"family": v["family"], "scheme": v["scheme"], "exact_target_hits": v["exact_target_hits"]}
            for v in successful_variants
        ],
        "overlap_pass": result["overlap_validation"].get("pass"),
        "recovered": result.get("recovery", {}).get("recovered_exact_rows"),
        "combined_observed": result.get("recovery", {}).get("combined_observed"),
        "combined_missing": result.get("recovery", {}).get("combined_missing"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
