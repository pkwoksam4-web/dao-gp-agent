import unittest

from gp12_sector_fund_source_provenance_v482 import build_sector_fund_source_provenance


class SectorFundSourceProvenanceV482Test(unittest.TestCase):
    def test_known_historical_source_clues_are_bound_without_false_closure(self):
        x = build_sector_fund_source_provenance()
        self.assertEqual(x["status"], "PARTIAL_SOURCE_PROVENANCE_BOUND")
        self.assertTrue(x["fund_flow"]["candidate_snapshot_identity_locked"])
        self.assertEqual(x["fund_flow"]["repo_id"], "ellendan/a-share-21")
        self.assertEqual(x["fund_flow"]["filename"], "all-prices-with-values-250423.csv")
        self.assertEqual(x["fund_flow"]["expected_size_bytes"], 2134704074)
        self.assertEqual(x["fund_flow"]["expected_sha256"], "034f6578d1475856c8a74285167e6f167bbb7052d25a1c691d804a9c2bbe6eea")
        self.assertEqual(len(x["fund_flow"]["preserved_flow_columns"]), 17)
        self.assertFalse(x["fund_flow"]["formal_window_coverage_complete"])
        self.assertFalse(x["fund_flow"]["pit_provenance_complete"])
        self.assertTrue(x["sector"]["adapter_path_recovered"])
        self.assertEqual(x["sector"]["passthrough_columns"], ["citic_l1", "citic_l3"])
        self.assertFalse(x["sector"]["source_snapshot_identity_locked"])
        self.assertFalse(x["sector"]["pit_membership_verified"])
        self.assertFalse(x["historical_factor_formula_recovered"])
        self.assertFalse(x["blocker_closed"])
        self.assertFalse(x["model_freeze_allowed"])
        self.assertFalse(x["oos_metrics_allowed"])

    def test_candidate_fund_snapshot_cannot_cover_full_formal_window(self):
        x = build_sector_fund_source_provenance()
        self.assertEqual(x["formal_window"], ["2020-06-01", "2026-04-17"])
        self.assertEqual(x["fund_flow"]["documented_public_coverage"], ["2021-01-01", "2025-02-27"])
        self.assertIn("FUND_FLOW_FORMAL_WINDOW_COVERAGE_INCOMPLETE", x["remaining_data_gaps"])

    def test_sector_passthrough_is_not_pit_membership_proof(self):
        x = build_sector_fund_source_provenance()
        self.assertIn("SECTOR_SOURCE_SNAPSHOT_IDENTITY_UNBOUND", x["remaining_data_gaps"])
        self.assertIn("SECTOR_PIT_MEMBERSHIP_UNVERIFIED", x["remaining_data_gaps"])

    def test_formula_gap_is_kept_separate_from_data_gap(self):
        x = build_sector_fund_source_provenance()
        self.assertEqual(x["remaining_contract_gaps"], [
            "SECTOR_RS_BREADTH_SLOPE_NORMALIZATION_AND_AGGREGATION_MISSING",
            "PRICE_FUND_EFFICIENCY_FORMULA_PULSE_FILTER_AND_NORMALIZATION_MISSING",
        ])
        self.assertFalse(x["data_completion_would_close_blocker_by_itself"])


if __name__ == "__main__":
    unittest.main()
