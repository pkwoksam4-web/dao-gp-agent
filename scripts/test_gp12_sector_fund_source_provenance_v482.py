import unittest

from gp12_sector_fund_source_provenance_v482 import build_sector_fund_source_provenance


class SectorFundSourceProvenanceV482Test(unittest.TestCase):
    def fund_admission(self):
        return {
            'artifact':'GP12_FUND_FLOW_SNAPSHOT_ADMISSION_V482',
            'version':'V4.82','strategy_id':'GP_V11',
            'status':'PASS_LOCKED_FUND_FLOW_SNAPSHOT_PAYLOAD_VERIFIED_PARTIAL_WINDOW',
            'formal_window':['2020-06-01','2026-04-17'],
            'source':{
                'repo_id':'ellendan/a-share-21',
                'source_commit':'227be520b89ed737dd65bea4785a41ae39a9b7a4',
                'filename':'all-prices-with-values-250423.csv',
                'expected_size_bytes':2134704074,
                'expected_sha256':'034f6578d1475856c8a74285167e6f167bbb7052d25a1c691d804a9c2bbe6eea',
                'actual_size_bytes':2134704074,
                'actual_sha256':'034f6578d1475856c8a74285167e6f167bbb7052d25a1c691d804a9c2bbe6eea',
                'rows':4934625,'symbols':5148,'first_date':'2021-01-04','last_date':'2025-04-23',
                'flow_columns':['dde_l','l_net_value','net_flow_rate','act_buy_xl','pas_buy_xl','act_sell_xl','pas_sell_xl','act_buy_l','pas_buy_l','act_sell_l','pas_sell_l','act_buy_m','pas_buy_m','act_sell_m','pas_sell_m','buy_l','sell_l'],
            },
            'remote_pointer_identity_verified':True,
            'actual_snapshot_bytes_verified_in_current_recovery':True,
            'single_original_snapshot_policy_verified':True,
            'auto_converted_hf_parquet_allowed':False,
            'formal_window_coverage_complete':False,
            'pit_known_at_semantics_recovered':False,
            'factor_formula_recovered':False,
            'remaining_data_gaps':['FUND_FLOW_FORMAL_WINDOW_COVERAGE_INCOMPLETE','FUND_FLOW_PIT_KNOWN_AT_UNBOUND'],
            'remaining_contract_gaps':['PRICE_FUND_EFFICIENCY_FORMULA_PULSE_FILTER_AND_NORMALIZATION_MISSING'],
            'blocker':'PIT_SECTOR_AND_FUND_FLOW_INPUT_PROVENANCE_INCOMPLETE','blocker_closed':False,
            'model_freeze_allowed':False,'oos_metrics_allowed':False,
        }

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

    def test_verified_payload_is_bound_without_false_closure(self):
        x=build_sector_fund_source_provenance(self.fund_admission())
        self.assertTrue(x['fund_flow']['actual_snapshot_bytes_verified_in_current_recovery'])
        self.assertEqual(x['fund_flow']['verified_rows'],4934625)
        self.assertEqual(x['fund_flow']['verified_symbols'],5148)
        self.assertEqual(x['fund_flow']['verified_coverage'],['2021-01-04','2025-04-23'])
        self.assertNotIn('FUND_FLOW_SOURCE_BYTES_NOT_VERIFIED_IN_CURRENT_RECOVERY',x['remaining_data_gaps'])
        self.assertIn('FUND_FLOW_FORMAL_WINDOW_COVERAGE_INCOMPLETE',x['remaining_data_gaps'])
        self.assertFalse(x['blocker_closed'])
        self.assertFalse(x['model_freeze_allowed'])
        self.assertFalse(x['oos_metrics_allowed'])

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
