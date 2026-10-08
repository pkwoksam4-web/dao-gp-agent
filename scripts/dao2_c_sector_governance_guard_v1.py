from __future__ import annotations
import json
from pathlib import Path

BASE = Path("data/dao2/modules")
LOCKED_SOURCE_SHA256 = "97410eb4acf16fd14b16b0a60f4bbe45b3da071f078fdb5dea7c3044120f1786"
LOCKED_SOURCE_PROVIDER = "WIND_ASWSINDEXEOD_DERIVED_CLOSE"
LOCKED_METHOD = "PREV_ACCEPTED_CLOSE_X_SAME_DAY_WIND_RETURN"


def validate_governance(rebuild, admission, wind, series, state, breadth, membership):
    rebuild_series = rebuild["series"]
    explicit_derived_allowed = bool(rebuild_series.get("derived_close_allowed", False))
    allowed_types = set(rebuild_series.get("allowed_provenance_types", []))
    derived_allowed = explicit_derived_allowed or "DERIVED_CLOSE" in allowed_types

    admitted = bool(admission["admission_decision"]["admitted"])
    admitted_rows = int(admission["admission_decision"]["admitted_rows"])

    if not derived_allowed:
        assert admitted is False, "derived close cannot be admitted without explicit rebuild-contract permission"
        assert admitted_rows == 0, "derived admitted_rows must remain zero when migration is not enabled"
    else:
        assert "DERIVED_CLOSE" in allowed_types
        assert admitted is True
        assert admitted_rows == 298
        assert str(admission["status"]).startswith("PASS_DERIVED_CLOSE_ADMISSION_LIMITED_298")
        assert admission["source_carrier"]["sha256"] == LOCKED_SOURCE_SHA256
        assert admission["provenance_contract"]["source_provider"] == LOCKED_SOURCE_PROVIDER
        rc = admission["reconstruction_contract"]
        assert rc["derivation_method"] == LOCKED_METHOD
        assert rc["production_uses_future_data"] is False
        assert rc["next_day_anchor_usage"] == "AUDIT_ONLY_NOT_VALUE_PRODUCTION"
        assert int(rc["observed_unique_rows"]) == 298
        cov = admission["coverage_after_admission"]
        assert int(cov["logical_covered_required_keys"]) == 43081
        assert int(cov["required_keys"]) == 43084
        assert int(cov["remaining_direct_gaps"]) == 3
        assert cov["full_coverage"] is False
        dg = rebuild_series["derived_close_governance"]
        assert dg["admitted"] is True
        assert int(dg["admitted_rows"]) == 298
        assert dg["raw_close"] is False
        assert dg["source_sha256"] == LOCKED_SOURCE_SHA256
        assert dg["production_uses_future_data"] is False

    assert wind["governance"]["admitted_to_sector_series"] is admitted
    assert int(wind["governance"]["admitted_rows"]) == admitted_rows
    if admitted:
        assert str(wind["status"]) == "PASS_GOVERNANCE_ADMITTED_DISTINCT_PROVENANCE"
        assert wind["governance"]["reconstructed_rows_marked_as_raw_close"] is False
        assert int(wind["governance"]["evidence_only_rows"]) == 0
    else:
        assert str(wind["status"]) == "PASS_EVIDENCE_ONLY_NOT_ADMITTED"

    sw = series["exact_audit"]["wind_derived_close_reconstruction"]
    assert int(sw["admitted_rows"]) == admitted_rows
    if admitted:
        assert str(sw["status"]) == "PASS_GOVERNANCE_ADMITTED_DISTINCT_PROVENANCE"
        assert sw["raw_close"] is False
        assert sw.get("governance_admission_required") is False
    else:
        assert str(sw["status"]) == "PASS_EVIDENCE_ONLY_NOT_ADMITTED"
        assert sw.get("governance_admission_required") is True

    ss = state["progress"]["sector_series"]
    stw = ss["wind_derived_close_reconstruction"]
    assert int(stw["admitted_rows"]) == admitted_rows
    assert int(ss["missing_required_keys"]) == int(series["validation"]["missing_required_keys"])
    assert int(ss["required_sector_date_keys"]) == int(series["validation"]["required_key_count"])
    if admitted:
        assert int(ss["observed_required_keys"]) == 43081
        assert int(ss["missing_required_keys"]) == 3
        assert int(series["validation"]["admitted_derived_close_rows"]) == 298
        assert str(series["validation"]["admissible_coverage"]) == "43081/43084"
        assert str(stw["status"]) == "PASS_GOVERNANCE_ADMITTED_DISTINCT_PROVENANCE"
        assert stw["raw_close"] is False
        assert ss["full_formal_coverage_proven"] is False

    assert membership["status"] == "PASS_SUBCOMPONENT"
    assert membership["blocker_closed_within_module"] is True
    assert "SECTOR_MEMBERSHIP_PIT_UNBOUND" not in breadth.get("blockers", [])
    assert breadth["dependencies"]["sector_membership_required_status"] == "PASS_SUBCOMPONENT"
    assert breadth.get("derivation_allowed") is False

    return {
        "valid": True,
        "derived_close_admitted": admitted,
        "derived_close_admitted_rows": admitted_rows,
        "series_missing_required_keys": int(ss["missing_required_keys"]),
        "series_observed_required_keys": int(ss["observed_required_keys"]),
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
