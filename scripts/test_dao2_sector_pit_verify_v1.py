from __future__ import annotations

import unittest

from dao2_sector_pit_verify_v1 import (
    required_sector_keys,
    validate_membership,
    validate_series,
    verify_candidate_package,
)


class MembershipTests(unittest.TestCase):
    def test_valid_switch_contract_passes(self):
        rows = [
            {
                "ts_code": "000001.SZ",
                "industry_code": "801010.SI",
                "in_date": "20200101",
                "out_date": "20211210",
                "taxonomy_version": "SW2014_projected",
                "mapping_method": "unchanged_l1_identity",
            },
            {
                "ts_code": "000001.SZ",
                "industry_code": "801010.SI",
                "in_date": "20211213",
                "out_date": "",
                "taxonomy_version": "SW2021",
                "mapping_method": "native_sw2021",
            },
        ]
        got = validate_membership(rows, [])
        self.assertEqual(got["status"], "PASS")
        self.assertTrue(got["taxonomy_switch_valid"])

    def test_projected_row_cannot_cross_switch(self):
        rows = [
            {
                "ts_code": "000001.SZ",
                "industry_code": "801010.SI",
                "in_date": "20200101",
                "out_date": "20211213",
                "taxonomy_version": "SW2014_projected",
                "mapping_method": "unchanged_l1_identity",
            }
        ]
        got = validate_membership(rows, [])
        self.assertEqual(got["status"], "FAIL")
        self.assertIn("row_1:sw2014_projected_extends_after_20211210", got["errors"])

    def test_unresolved_rows_fail_closed(self):
        rows = [
            {
                "ts_code": "000001.SZ",
                "industry_code": "801010.SI",
                "in_date": "20211213",
                "out_date": "",
                "taxonomy_version": "SW2021",
                "mapping_method": "native_sw2021",
            }
        ]
        got = validate_membership(rows, [{"ts_code": "000002.SZ"}])
        self.assertEqual(got["status"], "FAIL")
        self.assertIn("unresolved_membership_rows_present:1", got["errors"])


class SeriesTests(unittest.TestCase):
    def test_exact_same_date_no_fill_passes(self):
        expected = {("801010.SI", "20200102"), ("801010.SI", "20200103")}
        rows = [
            {
                "industry_code": "801010.SI",
                "trade_date": date,
                "close": "100",
                "source_provider": "tushare",
                "source_trade_date": date,
                "fill_method": "NONE",
            }
            for _, date in sorted(expected)
        ]
        got = validate_series(rows, expected)
        self.assertEqual(got["status"], "PASS")
        self.assertTrue(got["full_coverage"])
        self.assertTrue(got["no_forward_fill_proven"])

    def test_missing_required_date_fails(self):
        expected = {("801010.SI", "20200102"), ("801010.SI", "20200103")}
        rows = [
            {
                "industry_code": "801010.SI",
                "trade_date": "20200102",
                "close": "100",
                "source_provider": "akshare",
                "source_trade_date": "20200102",
                "fill_method": "NONE",
            }
        ]
        got = validate_series(rows, expected)
        self.assertEqual(got["status"], "FAIL")
        self.assertEqual(got["missing_required_keys"], 1)

    def test_forward_fill_or_date_proxy_fails(self):
        expected = {("801010.SI", "20200103")}
        rows = [
            {
                "industry_code": "801010.SI",
                "trade_date": "20200103",
                "close": "100",
                "source_provider": "akshare",
                "source_trade_date": "20200102",
                "fill_method": "FFILL",
            }
        ]
        got = validate_series(rows, expected)
        self.assertEqual(got["status"], "FAIL")
        self.assertFalse(got["no_forward_fill_proven"])


class PackageTests(unittest.TestCase):
    def test_breadth_gate_opens_only_after_membership_and_series_pass(self):
        formal = [{"trade_date": "20211210"}, {"trade_date": "20211213"}]
        membership = [
            {
                "ts_code": "000001.SZ",
                "industry_code": "801010.SI",
                "in_date": "20211210",
                "out_date": "20211210",
                "taxonomy_version": "SW2014_projected",
                "mapping_method": "unchanged_l1_identity",
            },
            {
                "ts_code": "000001.SZ",
                "industry_code": "801010.SI",
                "in_date": "20211213",
                "out_date": "",
                "taxonomy_version": "SW2021",
                "mapping_method": "native_sw2021",
            },
        ]
        expected = required_sector_keys(membership, ["20211210", "20211213"])
        series = [
            {
                "industry_code": code,
                "trade_date": date,
                "close": "100",
                "source_provider": "tushare",
                "source_trade_date": date,
                "fill_method": "NONE",
            }
            for code, date in sorted(expected)
        ]
        got = verify_candidate_package(formal, membership, [], series)
        self.assertEqual(got["status"], "PASS_CANDIDATE_INPUTS")
        self.assertTrue(got["sector_breadth_derivation_allowed"])
        self.assertFalse(got["historical_gp_v11_recovery_claim_allowed"])

    def test_unresolved_membership_keeps_breadth_gate_closed(self):
        formal = [{"trade_date": "20211213"}]
        membership = [
            {
                "ts_code": "000001.SZ",
                "industry_code": "801010.SI",
                "in_date": "20211213",
                "out_date": "",
                "taxonomy_version": "SW2021",
                "mapping_method": "native_sw2021",
            }
        ]
        series = [
            {
                "industry_code": "801010.SI",
                "trade_date": "20211213",
                "close": "100",
                "source_provider": "tushare",
                "source_trade_date": "20211213",
                "fill_method": "NONE",
            }
        ]
        got = verify_candidate_package(formal, membership, [{"ts_code": "000002.SZ"}], series)
        self.assertEqual(got["status"], "BLOCKED")
        self.assertFalse(got["sector_breadth_derivation_allowed"])


if __name__ == "__main__":
    unittest.main()
