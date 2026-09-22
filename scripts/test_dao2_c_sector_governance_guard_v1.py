import copy
import unittest
from dao2_c_sector_governance_guard_v1 import validate_governance

def fixtures():
    rebuild={"series":{"synthetic_rows_allowed":False}}
    admission={"status":"NOT_ADMITTED_FROZEN_GOVERNANCE_CONFLICT","admission_decision":{"admitted":False,"admitted_rows":0}}
    wind={"status":"PASS_EVIDENCE_ONLY_NOT_ADMITTED","governance":{"admitted_to_sector_series":False}}
    series={
      "exact_audit":{"wind_derived_close_reconstruction":{"status":"PASS_EVIDENCE_ONLY_NOT_ADMITTED","admitted_rows":0,"governance_admission_required":True}},
      "validation":{"missing_required_keys":301,"required_key_count":43084}
    }
    state={"progress":{"sector_series":{
      "required_sector_date_keys":43084,"missing_required_keys":301,
      "wind_derived_close_reconstruction":{"status":"PASS_EVIDENCE_ONLY_NOT_ADMITTED","admitted_rows":0,"governance_admission_required":True}
    }}}
    breadth={"status":"BLOCKED_DEPENDENCIES_AND_FORMULA","blockers":["SECTOR_SERIES_UNBOUND","exact same-day sector breadth ratio definition remains unrecovered"],"dependencies":{"sector_membership_required_status":"PASS_SUBCOMPONENT"}}
    membership={"status":"PASS_SUBCOMPONENT","blocker_closed_within_module":True}
    return rebuild,admission,wind,series,state,breadth,membership

class Tests(unittest.TestCase):
    def test_current_fail_closed_state_passes(self):
        got=validate_governance(*fixtures())
        self.assertTrue(got["valid"])
        self.assertFalse(got["derived_close_admitted"])

    def test_unapproved_derived_admission_fails(self):
        xs=list(fixtures())
        xs[1]=copy.deepcopy(xs[1])
        xs[1]["status"]="PASS_DERIVED_CLOSE_ADMISSION_CONTRACT"
        xs[1]["admission_decision"]={"admitted":True,"admitted_rows":298}
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
