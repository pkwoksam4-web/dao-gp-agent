#!/usr/bin/env python3
import argparse
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pandas as pd


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def sha256_path(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact-zip", required=True)
    ap.add_argument("--repo-root", default=".")
    args = ap.parse_args()
    root = Path(args.repo_root).resolve()
    modules = root / "data" / "dao2" / "modules"

    series_path = modules / "C_SECTOR_SERIES_CHECKPOINT_V1.json"
    wind_path = modules / "C_SECTOR_WIND_DERIVED_CLOSE_EVIDENCE_V1.json"
    price_path = modules / "C_SECTOR_PRICE_BASIS_BINDING_V1.json"
    membership_path = modules / "C_SECTOR_MEMBERSHIP_PIT_CHECKPOINT_V1.json"
    direct_path = modules / "C_SECTOR_801020_DIRECT_CLOSE_SEARCH_V1.json"
    state_path = modules / "C_SECTOR_PIT_STATE_V1.json"

    series = load_json(series_path)
    wind = load_json(wind_path)
    price = load_json(price_path)
    membership = load_json(membership_path)
    direct = load_json(direct_path)
    state = load_json(state_path)

    artifact_id = int(series["exact_audit"]["wind_derived_close_reconstruction"]["artifact_id"])
    artifact_digest = series["exact_audit"]["wind_derived_close_reconstruction"]["artifact_digest"]
    workflow_run_id = int(series["exact_audit"]["wind_derived_close_reconstruction"]["workflow_run_id"])

    with zipfile.ZipFile(args.artifact_zip) as z:
        recon = pd.read_csv(io.BytesIO(z.read("wind_two_sided_reconstruction.csv")), dtype=str)
        unresolved = pd.read_csv(io.BytesIO(z.read("wind_unresolved.csv")), dtype=str)
        result = json.loads(z.read("result.json").decode("utf-8"))

    assert len(recon) == 298
    assert len(unresolved) == 3
    assert recon[["industry_code", "trade_date"]].duplicated().sum() == 0
    assert unresolved[["industry_code", "trade_date"]].duplicated().sum() == 0
    recon_keys = set(map(tuple, recon[["industry_code", "trade_date"]].values))
    direct_keys = set(map(tuple, unresolved[["industry_code", "trade_date"]].values))
    assert recon_keys.isdisjoint(direct_keys)
    checkpoint_direct = set(map(tuple, series["exact_audit"]["direct_unresolved_keys"]))
    assert direct_keys == checkpoint_direct
    assert recon["unique_2dp"].str.lower().eq("true").all()

    required = int(series["validation"]["required_key_count"])
    admissible = int(series["exact_audit"]["frozen_observed_required_keys"])
    missing = int(series["validation"]["missing_required_keys"])
    assert (required, admissible, missing) == (43084, 42783, 301)
    assert int(series["exact_audit"]["admitted_derived_close_rows"]) == 0

    source = result["source"]
    basis = price["bound_semantics"]["canonical_value"]
    basis_status = price["status"]
    sw2014_last = membership["binding_semantics"]["sw2014_last_trade_date"].replace("-", "")

    row_schema = [
        "sector_code", "trade_date", "source_repository", "source_commit", "source_path",
        "source_blob_sha", "source_sha256", "derivation_provenance", "taxonomy", "price_basis",
        "status", "gap_class", "current_provenance_type", "admitted", "raw_close_required",
        "candidate_close_2dp", "two_sided_unique_2dp"
    ]
    rows = []
    for _, r in recon.sort_values(["trade_date", "industry_code"]).iterrows():
        d = r.trade_date
        rows.append([
            r.industry_code, d, source["repository"], source["commit"], source["path"],
            source["git_blob_sha"], source["sha256"], source["derivation_provenance"],
            "SW2014_DATE_EFFECTIVE" if d <= sw2014_last else "SW2021_DATE_EFFECTIVE",
            basis, "EVIDENCE_ONLY_NOT_ADMITTED", "DERIVED_CLOSE_EVIDENCE_ONLY", "DERIVED_CLOSE",
            False, True, float(r.candidate_close_2dp), True,
        ])
    for _, r in unresolved.sort_values(["trade_date", "industry_code"]).iterrows():
        d = r.trade_date
        rows.append([
            r.industry_code, d, None, None, None, None, None, None,
            "SW2014_DATE_EFFECTIVE" if d <= sw2014_last else "SW2021_DATE_EFFECTIVE",
            basis, "DIRECT_RAW_REQUIRED", "DIRECT_RAW_REQUIRED", None, False, True, None, None,
        ])
    rows.sort(key=lambda r: (r[1], r[0]))
    keys = [(r[0], r[1]) for r in rows]
    assert len(rows) == 301
    assert len(set(keys)) == 301
    assert sum(r[11] == "DERIVED_CLOSE_EVIDENCE_ONLY" for r in rows) == 298
    assert sum(r[11] == "DIRECT_RAW_REQUIRED" for r in rows) == 3

    ledger = {
        "artifact": "DAO2_C_301_GAP_LEDGER_V1",
        "version": "1.0",
        "module_id": "C",
        "component": "sector_series",
        "status": "PASS_LEDGER_COMPLETE_SERIES_STILL_BLOCKED",
        "construction": {
            "method": "UNION_REAL_ARTIFACT_MEMBERS_NO_MANUAL_GAP_KEYS",
            "series_checkpoint": str(series_path.relative_to(root)),
            "wind_evidence": str(wind_path.relative_to(root)),
            "workflow_run_id": workflow_run_id,
            "artifact_id": artifact_id,
            "artifact_digest": artifact_digest,
            "derived_member": "wind_two_sided_reconstruction.csv",
            "direct_member": "wind_unresolved.csv",
            "manual_gap_key_insertion": False,
        },
        "frozen_state": {
            "required": required,
            "admissible": admissible,
            "missing": missing,
            "admitted_derived_close_rows": 0,
            "coverage_changed_by_ledger": False,
        },
        "validation": {
            "rows": 301,
            "unique_sector_code_trade_date": 301,
            "duplicate": 0,
            "derived_close_evidence_only": 298,
            "direct_raw_required": 3,
            "admitted_derived_close_rows": 0,
        },
        "row_schema": row_schema,
        "rows": rows,
        "governance": {
            "derived_governance_migration_active": False,
            "raw_close_requirement_retained_for_all_301": True,
            "frozen_42783_base_immutable": True,
            "breadth_status": "BLOCKED_PENDING_SERIES_PASS",
            "breadth_derivation_allowed": False,
        },
    }
    ledger_path = modules / "C_301_GAP_LEDGER_V1.json"
    dump_json(ledger_path, ledger)

    providers = "Wind|iFind|RiceQuant RQData|Founder DataCube|Tushare sw_daily with entitlement"
    raw_fields = "code|trade_date|open|high|low|close|pre_close(optional)|taxonomy|price_basis|provider|raw_filename|export_timestamp|sha256"
    anchors = direct["frozen_overlap_anchors"]
    vendor_path = modules / "C_301_GAP_VENDOR_SCOPE_V1.csv"
    header = [
        "sector_code", "trade_date", "gap_class", "priority", "status", "taxonomy", "price_basis",
        "raw_close_required", "accepted_providers", "required_raw_fields", "neighbor_prev_date",
        "neighbor_prev_close", "neighbor_next_date", "neighbor_next_close"
    ]
    with vendor_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            code, d = r[0], r[1]
            gap, status, taxonomy = r[11], r[10], r[8]
            if gap == "DIRECT_RAW_REQUIRED":
                priority = "P1_DIRECT_RAW_IMMEDIATE"
                a = anchors[d]
                prev = a["previous"][-1]
                nxt = a["next"][0]
                neighbor = [prev[0], prev[1], nxt[0], nxt[1]]
            else:
                priority = "P2_AUTHORITATIVE_RAW_CLOSE_298_REQUIRED"
                neighbor = ["", "", "", ""]
            w.writerow([code, d, gap, priority, status, taxonomy, basis, "true", providers, raw_fields, *neighbor])

    ledger_sha = sha256_path(ledger_path)
    vendor_sha = sha256_path(vendor_path)

    # Documentation-only consistency repair: evidence is not admitted under contract v1.2.
    gov = wind["governance"]
    gov["admitted_rows"] = 0
    gov["evidence_only_rows"] = 298
    gov["provenance_type"] = "DERIVED_CLOSE"
    gov.pop("admitted_provenance_type", None)
    implications = wind["implications"]
    implications.pop("logical_coverage_after_admission", None)
    implications["potential_coverage_if_future_governance_migration_passes"] = "43081/43084"
    dump_json(wind_path, wind)

    ledger_ref = {
        "status": "PASS_LEDGER_COMPLETE_SERIES_STILL_BLOCKED",
        "ledger_path": str(ledger_path.relative_to(root)),
        "ledger_sha256": ledger_sha,
        "vendor_scope_path": str(vendor_path.relative_to(root)),
        "vendor_scope_sha256": vendor_sha,
        "rows": 301,
        "unique_keys": 301,
        "duplicate": 0,
        "derived_evidence_only": 298,
        "direct_raw_required": 3,
        "admitted_derived_close_rows": 0,
        "coverage_changed": False,
    }
    series["exact_audit"]["gap_ledger_v1"] = ledger_ref
    dump_json(series_path, series)
    state["progress"]["sector_series"]["gap_ledger_v1"] = ledger_ref
    state["progress"]["sector_series"]["admissible_coverage"] = "42783/43084"
    state["progress"]["sector_series"]["admitted_derived_close_rows"] = 0
    state["progress"]["sector_breadth"]["status"] = "BLOCKED_PENDING_SERIES_PASS"
    state["progress"]["sector_breadth"]["derivation_allowed"] = False
    dump_json(state_path, state)

    print(json.dumps({
        "ledger_rows": 301,
        "unique_keys": 301,
        "duplicate": 0,
        "derived_evidence_only": 298,
        "direct_raw_required": 3,
        "admitted_derived_close_rows": 0,
        "ledger_sha256": ledger_sha,
        "vendor_scope_sha256": vendor_sha,
    }, indent=2))


if __name__ == "__main__":
    main()
