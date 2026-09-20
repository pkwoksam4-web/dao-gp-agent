import unittest
from dao2_module_state_guard_v1 import validate

BASE={
 "artifact":"DAO2_MODULE_TEST_STATE_V1",
 "module_id":"A",
 "status":"ACTIVE",
 "governance":{"fail_closed":True,"forward_fill":False,"silent_proxy_substitution":False,"model_freeze_allowed":False,"oos_metrics_allowed":False}
}

class Tests(unittest.TestCase):
    def test_active_state(self):
        self.assertTrue(validate(dict(BASE))["valid"])
    def test_final_requires_verified_checkpoint(self):
        x=dict(BASE); x["status"]="PASS"
        with self.assertRaises(AssertionError): validate(x)
    def test_oos_cannot_open(self):
        x={**BASE,"governance":{**BASE["governance"],"oos_metrics_allowed":True}}
        with self.assertRaises(AssertionError): validate(x)

if __name__=="__main__":
    unittest.main()
