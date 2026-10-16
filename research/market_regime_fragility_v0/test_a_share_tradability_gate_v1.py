import unittest

from a_share_tradability_gate_v1 import evaluate_tradability


BASE_RECORD = {
    "symbol": "000001.SZ",
    "observed_at": "2026-10-16T09:30:00+08:00",
    "decision_cutoff": "2026-10-16T09:31:00+08:00",
    "pit_valid": True,
    "listing_status": "LISTED",
    "st_status": "NORMAL",
    "suspension_status": "TRADING",
    "board": "MAIN_SZ",
    "price_limit_rule_id": "TEST_RULE_V1",
    "limit_state": "NONE",
    "executed_trade_evidence": True,
    "buy_liquidity_observed": "YES",
    "sell_liquidity_observed": "YES",
    "sell_eligible_quantity": 100,
    "provenance": {"market_state": "fixture://market", "liquidity": "fixture://liquidity"},
}


class AShareTradabilityGateV1Tests(unittest.TestCase):
    def test_normal_two_sided_trading_is_rs_eligible(self):
        result = evaluate_tradability(dict(BASE_RECORD))
        self.assertTrue(result["buy_eligible"])
        self.assertTrue(result["sell_eligible"])
        self.assertTrue(result["rs_eligible"])
        self.assertEqual(result["reasons"], [])
        self.assertFalse(result["production_authorized"])

    def test_suspended_security_is_not_tradable_or_rs_eligible(self):
        record = dict(BASE_RECORD)
        record["suspension_status"] = "SUSPENDED"
        result = evaluate_tradability(record)
        self.assertFalse(result["buy_eligible"])
        self.assertFalse(result["sell_eligible"])
        self.assertFalse(result["rs_eligible"])
        self.assertIn("SUSPENDED", result["reasons"])

    def test_locked_limit_up_without_buy_liquidity_is_not_buyable_or_rs_eligible(self):
        record = dict(BASE_RECORD)
        record["limit_state"] = "UP_LOCKED_NO_BUY"
        record["buy_liquidity_observed"] = "NO"
        result = evaluate_tradability(record)
        self.assertFalse(result["buy_eligible"])
        self.assertTrue(result["sell_eligible"])
        self.assertFalse(result["rs_eligible"])
        self.assertIn("BUY_BLOCKED_PRICE_LIMIT", result["reasons"])

    def test_locked_limit_down_without_sell_liquidity_is_not_sellable_or_rs_eligible(self):
        record = dict(BASE_RECORD)
        record["limit_state"] = "DOWN_LOCKED_NO_SELL"
        record["sell_liquidity_observed"] = "NO"
        result = evaluate_tradability(record)
        self.assertTrue(result["buy_eligible"])
        self.assertFalse(result["sell_eligible"])
        self.assertFalse(result["rs_eligible"])
        self.assertIn("SELL_BLOCKED_PRICE_LIMIT", result["reasons"])

    def test_t1_zero_sell_eligible_quantity_blocks_sell(self):
        record = dict(BASE_RECORD)
        record["sell_eligible_quantity"] = 0
        result = evaluate_tradability(record)
        self.assertTrue(result["buy_eligible"])
        self.assertFalse(result["sell_eligible"])
        self.assertFalse(result["rs_eligible"])
        self.assertIn("SELL_BLOCKED_T1", result["reasons"])

    def test_missing_price_limit_rule_fails_closed(self):
        record = dict(BASE_RECORD)
        record["price_limit_rule_id"] = ""
        result = evaluate_tradability(record)
        self.assertIsNone(result["buy_eligible"])
        self.assertIsNone(result["sell_eligible"])
        self.assertFalse(result["rs_eligible"])
        self.assertIn("PRICE_LIMIT_RULE_MISSING", result["reasons"])

    def test_missing_side_liquidity_fails_closed(self):
        record = dict(BASE_RECORD)
        record["buy_liquidity_observed"] = "UNAVAILABLE"
        result = evaluate_tradability(record)
        self.assertIsNone(result["buy_eligible"])
        self.assertIsNone(result["sell_eligible"])
        self.assertFalse(result["rs_eligible"])
        self.assertIn("LIQUIDITY_EVIDENCE_UNAVAILABLE", result["reasons"])

    def test_no_actual_trades_disqualifies_rs_even_if_quotes_exist(self):
        record = dict(BASE_RECORD)
        record["executed_trade_evidence"] = False
        result = evaluate_tradability(record)
        self.assertTrue(result["buy_eligible"])
        self.assertTrue(result["sell_eligible"])
        self.assertFalse(result["rs_eligible"])
        self.assertIn("NO_EXECUTED_TRADE_EVIDENCE", result["reasons"])

    def test_post_cutoff_record_fails_closed(self):
        record = dict(BASE_RECORD)
        record["observed_at"] = "2026-10-16T09:32:00+08:00"
        result = evaluate_tradability(record)
        self.assertIsNone(result["buy_eligible"])
        self.assertIsNone(result["sell_eligible"])
        self.assertFalse(result["rs_eligible"])
        self.assertIn("POST_CUTOFF_EVIDENCE", result["reasons"])


if __name__ == "__main__":
    unittest.main()
