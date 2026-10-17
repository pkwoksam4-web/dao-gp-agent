import unittest
from dao2_label_status_contract_v1 import derive_status, validate

class LabelStatusContractTests(unittest.TestCase):
    def test_static_contract(self):
        result = validate()
        self.assertTrue(result["valid"])
        self.assertEqual(result["label_provenance"], "BOUND")
        self.assertEqual(result["status_semantics"], "COMPLETE")

    def test_status_composition(self):
        self.assertEqual(
            derive_status(is_st_raw="0", tradestatus_raw="1", close="10.00", up_limit="10.00"),
            {"is_st":False,"tradable":True,"upper_limit":True,"status_entry_eligible":False},
        )
        self.assertTrue(
            derive_status(is_st_raw="0", tradestatus_raw="1", close="9.99", up_limit="10.00")["status_entry_eligible"]
        )
        self.assertFalse(
            derive_status(is_st_raw="1", tradestatus_raw="1", close="9.99", up_limit="10.00")["status_entry_eligible"]
        )

    def test_nontradable_has_no_limit_close_event(self):
        row = derive_status(is_st_raw="0", tradestatus_raw="0", close=None, up_limit=None)
        self.assertFalse(row["tradable"])
        self.assertFalse(row["upper_limit"])
        self.assertFalse(row["status_entry_eligible"])

    def test_unknown_or_missing_tradable_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            derive_status(is_st_raw="?", tradestatus_raw="1", close="9", up_limit="10")
        with self.assertRaises(ValueError):
            derive_status(is_st_raw="0", tradestatus_raw="?", close="9", up_limit="10")
        with self.assertRaises(ValueError):
            derive_status(is_st_raw="0", tradestatus_raw="1", close=None, up_limit="10")
        with self.assertRaises(ValueError):
            derive_status(is_st_raw="0", tradestatus_raw="1", close="9", up_limit=None)

if __name__ == "__main__":
    unittest.main()
