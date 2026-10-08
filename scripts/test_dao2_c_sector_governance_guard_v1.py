import copy
import unittest
from dao2_c_sector_governance_guard_v1 import validate_governance, LOCKED_SOURCE_SHA256


def fixtures():
    rebuild={"series":{
        "synthetic_rows_allowed":False,
        "derived_close_allowed":True,
        "allowed_provenance_types":["RAW_CLOSE","DERIVED_CLOSE"],
        "derived_close_governance":{"admitted":True,"admitted_rows":298,"raw_close":False,"source_sha256":LOCKED_SOURCE_SHA256,"production_uses_future_data":False}
    }}
    admission={
        "status":"PASS_DERIVED_CLOSE_ADMISSION_LIMITED_298_SERIES_STILL_BLOCKED",
        "source_carrier":{"sha256":LOCKED_SOURCE_SHA256},
        "provenance_contract":{"source_provider":"WIND_ASWSINDEXEOD_DERIVED_CLOSE"},
        "reconstruction_contract":{"derivation_method":"PREV_ACCEPTED_CLOSE_X_SAME_DAY_WIND_RETURN","production_uses_future_data":False,"next_day_anchor_usage":"AUDIT_ONLY_NOT_VALUE_PRODUCTION","observed_unique_rows":298},
        "admission_decision":{"admitted":True,"admitted_rows":298},
        "coverage_after_admission":{"logical_covered_required_keys":43081,"required_keys":43084,"remaining_direct_gaps":3,"full_coverage":False}
    }
    wind={"status":"PASS_GOVERNANCE_ADMITTED_DISTINCT_PROVENANCE","governance":{"admitted_to_sector_series":True,"admitted_rows":298,"reconstructed_rows_marked_as_raw_close":False,"evidence_only_rows":0}}
    series={
      "exact_audit":{"wind_derived_close_reconstruction":{"status":"PASS_GOVERNANCE_ADMITTED_DISTINCT_PROVENANCE","admitted_rows":298,"governance_admission_required":False,"raw_close":False}},
      "validation":{"missing_required_keys":3,"required_key_count":43084,"admitted_derived_close_rows":298,"admissible_coverage":"43081/43084"}
    }
    state={"progress":{"sector_series":{
      "required_sector_date_keys":43084,"observed_required_keys":43081,"missing_required_keys":3,"full_formal_coverage_proven":False,
      "wind_derived_close_reconstruction":{"status":"PASS_GOVERNANCE_ADMITTED_DISTINCT_PROVENANCE","admitted_rows":298,"governance_admission_required":False,"raw_close":False}
    }}}
    breadth={"status":"BLOCKED_DEPENDENCIES_AND_FORMULA","derivation_allowed":False,"blockers":["SECTOR_SERIES_UNBOUND","exact same-day sector breadth ratio definition remains unrecovered"],"dependencies":{"sector_membership_required_status":"PASS_SUBCOMPONENT"}}
    membership={"status":"PASS_SUBCOMPONENT","blocker_closed_within_module":True}
    return rebuild,admission,wind,series,state,breadth,membership


class Tests(unittest.TestCase):
    def test_current_limited_migration_state_passes(self):
        got=validate_governance(*fixtures())
        self.assertTrue(got["valid"])
        self.assertTrue(got["derived_close_admitted"])
        self.assertEqual(got["derived_close_admitted_rows"],298)
        self.assertEqual(got["series_missing_required_keys"],3)

    def test_unapproved_derived_admission_fails(self):
        xs=list(fixtures())
        xs[0]=copy.deepcopy(xs[0])
        xs[0]["series"]["derived_close_allowed"]=False
        xs[0]["series"]["allowed_provenance_types"]=["RAW_CLOSE"]
        with self.assertRaises(AssertionError):
            validate_governance(*xs)

    def test_source_hash_drift_fails(self):
        xs=list(fixtures())
        xs[1]=copy.deepcopy(xs[1])
        xs[1]["source_carrier"]["sha256"]="0"*64
        with self.assertRaises(AssertionError):
            validate_governance(*xs)

    def test_future_data_production_fails(self):
        xs=list(fixtures())
        xs[1]=copy.deepcopy(xs[1])
        xs[1]["reconstruction_contract"]["production_uses_future_data"]=True
        with self.assertRaises(AssertionError):
            validate_governance(*xs)

    def test_coverage_cannot_claim_pass_with_three_missing(self):
        xs=list(fixtures())
        xs[4]=copy.deepcopy(xs[4])
        xs[4]["progress"]["sector_series"]["missing_required_keys"]=0
        with self.assertRaises(AssertionError):
            validate_governance(*xs)

    def test_closed_membership_cannot_remain_breadth_blocker(self):
        xs=list(fixtures())
        xs[5]=copy.deepcopy(xs[5])
        xs[5]["blockers"].append("SECTOR_MEMBERSHIP_PIT_UNBOUND")
        with self.assertRaises(AssertionError):
            validate_governance(*xs)


if __name__=="__main__":
    unittest.main()
