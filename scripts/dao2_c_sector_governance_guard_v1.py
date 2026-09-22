from __future__ import annotations
import json
from pathlib import Path

BASE = Path("data/dao2/modules")

def validate_governance(rebuild, admission, wind, series, state, breadth, membership):
    rebuild_series = rebuild["series"]
    explicit_derived_allowed = bool(rebuild_series.get("derived_close_allowed", False))
    allowed_types = set(rebuild_series.get("allowed_provenance_types", []))
    derived_allowed = explicit_derived_allowed or "DERIVED_CLOSE" in allowed_types

    admitted = bool(admission["admission_decision"]["admitted"])
    admitted_rows = int(admission["admission_decision"]["admitted_rows"])

    if rebuild_series.get("synthetic_rows_allowed") is False and not derived_allowed:
        assert admitted is False, "derived close cannot be admitted under frozen rebuild contract"
        assert admitted_rows == 0, "derived admitted_rows must remain zero"
        assert not str(admission.get("status", "")).startswith("PASS_DERIVED_CLOSE_ADMISSION")

    assert wind["governance"]["admitted_to_sector_series"] is admitted
    if not admitted:
        assert str(wind["status"]) == "PASS_EVIDENCE_ONLY_NOT_ADMITTED"

    sw = series["exact_audit"]["wind_derived_close_reconstruction"]
    assert int(sw["admitted_rows"]) == admitted_rows
    if not admitted:
        assert str(sw["status"]) == "PASS_EVIDENCE_ONLY_NOT_ADMITTED"
        assert sw.get("governance_admission_required") is True

    ss = state["progress"]["sector_series"]
    stw = ss["wind_derived_close_reconstruction"]
    assert int(stw["admitted_rows"]) == admitted_rows
    assert int(ss["missing_required_keys"]) == int(series["validation"]["missing_required_keys"])
    assert int(ss["required_sector_date_keys"]) == int(series["validation"]["required_key_count"])
    if not admitted:
        assert str(stw["status"]) == "PASS_EVIDENCE_ONLY_NOT_ADMITTED"
        assert stw.get("governance_admission_required") is True

    assert membership["status"] == "PASS_SUBCOMPONENT"
    assert membership["blocker_closed_within_module"] is True
    assert "SECTOR_MEMBERSHIP_PIT_UNBOUND" not in breadth.get("blockers", [])
    assert breadth["dependencies"]["sector_membership_required_status"] == "PASS_SUBCOMPONENT"

    return {
        "valid": True,
        "derived_close_admitted": admitted,
        "derived_close_admitted_rows": admitted_rows,
        "series_missing_required_keys": int(ss["missing_required_keys"]),
        "membership_status": membership["status"],
        "breadth_status": breadth["status"],
    }

def load(name):
    return json.loads((BASE / name).read_text(encoding="utf-8"))

def main():
    result = validate_governance(
        load("C_SECTOR_REBUILD_CONTRACT_V1.json"),
        load("C_SECTOR_DERIVED_CLOSE_ADMISSION_CONTRACT_V1.json"),
        load("C_SECTOR_WIND_DERIVED_CLOSE_EVIDENCE_V1.json"),
        load("C_SECTOR_SERIES_CHECKPOINT_V1.json"),
        load("C_SECTOR_PIT_STATE_V1.json"),
        load("C_SECTOR_BREADTH_CHECKPOINT_V1.json"),
        load("C_SECTOR_MEMBERSHIP_PIT_CHECKPOINT_V1.json"),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
