import math
import unittest

from gp12_main_net_flow_tushare_v1 import (
    audit_symbol_rows,
    normalize_moneyflow_records,
    summarize_formal_audit,
)


class MainNetFlowTushareContractTests(unittest.TestCase):
    def test_normalizes_large_and_extra_large_net_flow_to_cny(self):
        rows = normalize_moneyflow_records(
            "000001.SZ",
            [{
                "ts_code": "000001.SZ",
                "trade_date": "20200601",
                "buy_lg_amount": 120.5,
                "sell_lg_amount": 20.25,
                "buy_elg_amount": 50.0,
                "sell_elg_amount": 10.25,
                "net_mf_amount": 140.0,
            }],
        )
        self.assertEqual(rows, [{
            "symbol": "000001.SZ",
            "date": "2020-06-01",
            "main_net_flow_cny": 1_400_000.0,
            "known_at": "2020-06-01T15:00:00+08:00",
            "source": "TUSHARE_MONEYFLOW_LG_ELG_ACTIVE_BUY_MINUS_SELL",
        }])

    def test_zero_and_negative_main_flow_are_valid(self):
        rows = normalize_moneyflow_records(
            "600000.SH",
            [
                {"ts_code":"600000.SH","trade_date":"20200601","buy_lg_amount":1,"sell_lg_amount":2,"buy_elg_amount":3,"sell_elg_amount":2,"net_mf_amount":0},
                {"ts_code":"600000.SH","trade_date":"20200602","buy_lg_amount":1,"sell_lg_amount":3,"buy_elg_amount":1,"sell_elg_amount":4,"net_mf_amount":-5},
            ],
        )
        self.assertEqual(rows[0]["main_net_flow_cny"], 0.0)
        self.assertEqual(rows[1]["main_net_flow_cny"], -50_000.0)

    def test_rejects_identity_missing_fields_and_nonfinite_values(self):
        with self.assertRaises(ValueError):
            normalize_moneyflow_records("000001.SZ", [{
                "ts_code":"600000.SH","trade_date":"20200601",
                "buy_lg_amount":1,"sell_lg_amount":1,"buy_elg_amount":1,"sell_elg_amount":1,
            }])
        with self.assertRaises(ValueError):
            normalize_moneyflow_records("000001.SZ", [{
                "ts_code":"000001.SZ","trade_date":"20200601",
                "buy_lg_amount":1,"sell_lg_amount":1,"buy_elg_amount":float("nan"),"sell_elg_amount":1,
            }])

    def test_symbol_audit_requires_exact_sorted_unique_date_axis(self):
        expected = ["2020-06-01", "2020-06-02"]
        good = [
            {"date":"2020-06-01","main_net_flow_cny":0.0},
            {"date":"2020-06-02","main_net_flow_cny":-1.0},
        ]
        report = audit_symbol_rows("000001.SZ", expected, good)
        self.assertTrue(report["symbol_pass"])
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["pit_scope"], "SESSION_CLOSE_NO_LOOKAHEAD_POLICY")
        self.assertFalse(report["same_session_main_net_flow_usable_before_close"])
        self.assertFalse(report["historical_provider_publication_timestamp_proven"])

        bad = audit_symbol_rows("000001.SZ", expected, [
            {"date":"2020-06-02","main_net_flow_cny":1.0},
            {"date":"2020-06-02","main_net_flow_cny":2.0},
            {"date":"2020-06-03","main_net_flow_cny":3.0},
        ])
        self.assertFalse(bad["symbol_pass"])
        self.assertIn("MAIN_NET_FLOW_DUPLICATE_DATE", bad["blockers"])
        self.assertIn("MAIN_NET_FLOW_DATE_ORDER_INVALID", bad["blockers"])
        self.assertIn("MAIN_NET_FLOW_DATE_GAP", bad["blockers"])
        self.assertIn("MAIN_NET_FLOW_EXTRA_DATE", bad["blockers"])

    def test_formal_summary_is_fail_closed_until_844_and_exact_total_rows(self):
        one = {
            "symbol":"000001.SZ","symbol_pass":True,"row_n":2,
            "coverage_exact":True,"pit_policy_valid":True,"blockers":[],
        }
        report = summarize_formal_audit([one], expected_trade_rows=1_011_607)
        self.assertFalse(report["main_net_flow_candidate_pit_verified"])
        self.assertFalse(report["model_freeze_allowed"])
        self.assertFalse(report["oos_metrics_allowed"])
        self.assertIn("MAIN_NET_FLOW_FORMAL_SYMBOL_COVERAGE_INCOMPLETE", report["blockers"])
        self.assertIn("MAIN_NET_FLOW_TOTAL_ROW_COVERAGE_MISMATCH", report["blockers"])


if __name__ == "__main__":
    unittest.main()
