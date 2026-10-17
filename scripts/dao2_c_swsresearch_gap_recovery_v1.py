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
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
EXPECTED_GAPS = 301
EXPECTED_DERIVED_CANDIDATES = 298
EXPECTED_DIRECT_UNRESOLVED = {
    ("801020.SI", "20210806"),
    ("801020.SI", "20211008"),
    ("801020.SI", "20211022"),
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def extract_gap_rows(ledger: dict) -> list[dict]:
    schema = ledger.get("row_schema")
    raw_rows = ledger.get("rows")
    if not isinstance(schema, list) or not isinstance(raw_rows, list):
        raise ValueError("gap ledger missing row_schema/rows")
    if len(schema) != len(set(schema)):
        raise ValueError("gap ledger row_schema contains duplicate names")
    out = []
    for raw in raw_rows:
        if not isinstance(raw, list) or len(raw) != len(schema):
            raise ValueError("gap ledger row does not match row_schema")
        row = dict(zip(schema, raw))
        trade_date = norm_date(row.get("trade_date"))
        if not trade_date:
            raise ValueError("gap ledger row has invalid trade_date")
        row["trade_date"] = trade_date
        out.append(row)
    return out


def normalize_trend_rows(raw: bytes, *, expected_code: str) -> list[dict]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return []
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    expected_code = str(expected_code).replace(".SI", "").strip()
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
        if code != expected_code or not date or None in (o, h, l, c):
            continue
        out.append(
            {
                "sector_code": code + ".SI",
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


def compare_recovered_to_ledger_candidates(gaps: list[dict], recovered: list[dict]) -> dict:
    idx = {(r["sector_code"], r["trade_date"]): r for r in recovered}
    candidate_rows = 0
    matched = 0
    mismatches = []
    missing = []
    for gap in gaps:
        candidate = gap.get("candidate_close_2dp")
        if candidate is None:
            continue
        candidate_rows += 1
        key = (str(gap["sector_code"]), str(gap["trade_date"]))
        row = idx.get(key)
        if row is None:
            missing.append({"sector_code": key[0], "trade_date": key[1], "candidate_close_2dp": candidate})
            continue
        observed = round(float(row["close"]), 2)
        expected = round(float(candidate), 2)
        if observed == expected:
            matched += 1
        else:
            mismatches.append(
                {
                    "sector_code": key[0],
                    "trade_date": key[1],
                    "candidate_close_2dp": expected,
                    "official_close_2dp": observed,
                    "abs_diff": abs(observed - expected),
                }
            )
    return {
        "candidate_rows": candidate_rows,
        "matched_2dp": matched,
        "mismatched_2dp": len(mismatches),
        "missing_candidate_rows": len(missing),
        "mismatches": mismatches,
        "missing": missing,
    }


def official_http_meta(response: requests.Response, raw: bytes) -> dict:
    host = (urlparse(response.url).hostname or "").lower()
    official = host == "swsresearch.com" or host.endswith(".swsresearch.com")
    return {
        "status": int(response.status_code),
        "final_url": response.url,
        "final_host": host,
        "official_host": official,
        "content_type": response.headers.get("Content-Type"),
        "raw_bytes": len(raw),
        "raw_sha256": sha256(raw),
    }


def load_frozen_base(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, compression="infer")
    required = {"industry_code", "trade_date", "close"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"frozen base missing columns: {missing}")
    df = df.copy()
    df["industry_code"] = df["industry_code"].astype(str).str.strip().str.upper()
    df["trade_date"] = (
        df["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True).str.replace("-", "", regex=False)
    )
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df.dropna(subset=["close"])


def audit_frozen_overlap(source_by_code: dict[str, list[dict]], base: pd.DataFrame, probed_codes: set[str]) -> dict:
    source_idx = {}
    for rows in source_by_code.values():
        for r in rows:
            source_idx[(r["sector_code"], r["trade_date"])] = round(float(r["close"]), 2)

    subset = base[base["industry_code"].isin({c + ".SI" for c in probed_codes})]
    checked = 0
    matched = 0
    missing_source = 0
    mismatches = []
    missing_examples = []
    for r in subset.itertuples(index=False):
        key = (str(r.industry_code), str(r.trade_date))
        observed = source_idx.get(key)
        if observed is None:
            missing_source += 1
            if len(missing_examples) < 50:
                missing_examples.append({"sector_code": key[0], "trade_date": key[1], "frozen_close": round(float(r.close), 2)})
            continue
        checked += 1
        expected = round(float(r.close), 2)
        if observed == expected:
            matched += 1
        elif len(mismatches) < 100:
            mismatches.append(
                {
                    "sector_code": key[0],
                    "trade_date": key[1],
                    "official_close_2dp": observed,
                    "frozen_close_2dp": expected,
                    "abs_diff": abs(observed - expected),
                }
            )
    return {
        "frozen_rows_for_probed_codes": int(len(subset)),
        "source_intersection_rows": checked,
        "matched_2dp": matched,
        "mismatched_2dp": checked - matched,
        "source_missing_for_frozen_rows": missing_source,
        "match_rate_on_intersection": (matched / checked) if checked else None,
        "mismatch_examples": mismatches,
        "missing_source_examples": missing_examples,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gap-ledger", required=True)
    ap.add_argument("--base-panel", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    raw_dir = out / "raw"
    raw_dir.mkdir(exist_ok=True)

    ledger_path = Path(args.gap_ledger)
    ledger_bytes = ledger_path.read_bytes()
    ledger = json.loads(ledger_bytes.decode("utf-8"))
    gaps = extract_gap_rows(ledger)
    if len(gaps) != EXPECTED_GAPS:
        raise ValueError(f"expected {EXPECTED_GAPS} ledger gaps, got {len(gaps)}")
    gap_keys = {(str(r["sector_code"]), str(r["trade_date"])) for r in gaps}
    if len(gap_keys) != EXPECTED_GAPS:
        raise ValueError("gap ledger keys are not unique")

    probed_codes = sorted({code.replace(".SI", "") for code, _ in gap_keys})
    base = load_frozen_base(Path(args.base_panel))

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json,text/plain,*/*"})

    calls = []
    source_by_code: dict[str, list[dict]] = {}
    recovered = []
    transport_failures = []
    for code in probed_codes:
        try:
            response = session.get(
                URL,
                params={"swindexcode": code, "period": "DAY"},
                timeout=(10, 45),
                verify=False,
            )
            raw = response.content
            (raw_dir / f"{code}_DAY.response.bin").write_bytes(raw)
            hmeta = official_http_meta(response, raw)
            rows = normalize_trend_rows(raw, expected_code=code)
            source_by_code[code] = rows
            calls.append({"swindexcode": code, "http": hmeta, "normalized_rows": len(rows)})
            if hmeta["status"] != 200 or not hmeta["official_host"]:
                transport_failures.append({"swindexcode": code, "http": hmeta})
                continue
            for r in rows:
                if (r["sector_code"], r["trade_date"]) in gap_keys:
                    rr = dict(r)
                    rr.update(
                        {
                            "source_provider": "AKShare index_hist_sw",
                            "source_endpoint": URL,
                            "source_trade_date": r["trade_date"],
                            "fill_method": "NONE",
                            "synthetic": False,
                            "raw_close": True,
                            "source_raw_sha256": hmeta["raw_sha256"],
                        }
                    )
                    recovered.append(rr)
        except Exception as exc:
            failure = {"swindexcode": code, "error": f"{type(exc).__name__}:{exc}"}
            calls.append(failure)
            transport_failures.append(failure)
            source_by_code[code] = []

    recovered.sort(key=lambda r: (r["trade_date"], r["sector_code"]))
    recovered_keys = {(r["sector_code"], r["trade_date"]) for r in recovered}
    missing_keys = sorted(gap_keys - recovered_keys)
    duplicate_count = len(recovered) - len(recovered_keys)
    candidate_audit = compare_recovered_to_ledger_candidates(gaps, recovered)
    overlap_audit = audit_frozen_overlap(source_by_code, base, set(probed_codes))

    pd.DataFrame(recovered).to_csv(out / "recovered_gap_rows.csv", index=False)
    (out / "recovered_gap_rows.json").write_text(json.dumps(recovered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    expected_missing = sorted(EXPECTED_DIRECT_UNRESOLVED)
    missing_exactly_expected = missing_keys == expected_missing
    candidate_exact = (
        candidate_audit["candidate_rows"] == EXPECTED_DERIVED_CANDIDATES
        and candidate_audit["matched_2dp"] == EXPECTED_DERIVED_CANDIDATES
        and candidate_audit["mismatched_2dp"] == 0
        and candidate_audit["missing_candidate_rows"] == 0
    )
    overlap_identity = (
        overlap_audit["source_intersection_rows"] > 0
        and overlap_audit["mismatched_2dp"] == 0
        and overlap_audit["match_rate_on_intersection"] == 1.0
    )
    pass_candidate = (
        not transport_failures
        and len(recovered_keys) == EXPECTED_DERIVED_CANDIDATES
        and duplicate_count == 0
        and missing_exactly_expected
        and candidate_exact
        and overlap_identity
    )

    result = {
        "artifact": "DAO2_C_SWSRESEARCH_301_GAP_RECOVERY_V1",
        "version": "1.0",
        "module_id": "C",
        "component": "sector_series",
        "checked_at_utc": now_utc(),
        "source": {
            "provider_contract_name": "AKShare index_hist_sw",
            "upstream": "SWSResearch official index_publish/trend",
            "endpoint": URL,
            "official_public_direct_ohlc": True,
        },
        "input": {
            "gap_ledger": str(ledger_path),
            "gap_ledger_sha256": sha256(ledger_bytes),
            "gap_rows": len(gaps),
            "unique_gap_keys": len(gap_keys),
            "unique_sector_codes": len(probed_codes),
        },
        "recovery": {
            "recovered_rows": len(recovered),
            "unique_recovered_keys": len(recovered_keys),
            "duplicate_recovered_rows": duplicate_count,
            "missing_rows": len(missing_keys),
            "missing_keys": [{"sector_code": c, "trade_date": d} for c, d in missing_keys],
            "expected_remaining_direct_keys": [{"sector_code": c, "trade_date": d} for c, d in expected_missing],
            "missing_exactly_expected_three": missing_exactly_expected,
        },
        "candidate_close_audit": candidate_audit,
        "frozen_base_overlap_audit": overlap_audit,
        "http_calls": calls,
        "transport_failures": transport_failures,
        "governance": {
            "probe_only": True,
            "admitted_rows": 0,
            "series_checkpoint_changed_to_pass": False,
            "breadth_gate_open": False,
            "frozen_42783_rewritten": False,
            "derived_close_admitted": 0,
            "note": "Recovered values are direct same-day OHLC candidates from the contract-listed AKShare index_hist_sw upstream. Admission requires a separate materialization/verifier step; this probe does not mutate the frozen Series base.",
        },
        "status": "PASS_298_DIRECT_RAW_CANDIDATES_THREE_UNRESOLVED" if pass_candidate else "FAIL_RECOVERY_OR_IDENTITY_GATE",
        "decision": "READY_FOR_PARTIAL_RAW_ADMISSION_REVIEW" if pass_candidate else "DO_NOT_ADMIT",
    }
    (out / "recovery_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if pass_candidate else 4


if __name__ == "__main__":
    raise SystemExit(main())
