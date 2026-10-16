import unittest

from universe_pit_snapshot_v1 import build_universe_snapshot


POLICY = {
    "liquidity_policy_version": "LIQUIDITY_TEST_V1",
    "new_listing_policy_version": "NEW_LISTING_TEST_V1",
}


def record(symbol="000001.SZ"):
    return {
        "symbol": symbol,
        "observed_at": "2026-10-16T15:00:00+08:00",
        "pit_valid": True,
        "listed_at_asof": True,
        "delisting_status_at_asof": "NORMAL",
        "st_status_at_asof": "NORMAL",
        "suspension_status_at_asof": "TRADING",
        "board_at_asof": "MAIN_SZ",
        "listing_date": "2010-01-01",
        "listing_age_sessions": 3000,
        "liquidity_policy_version": "LIQUIDITY_TEST_V1",
        "new_listing_policy_version": "NEW_LISTING_TEST_V1",
        "liquidity_eligible_at_asof": True,
        "new_listing_eligible_at_asof": True,
        "price_limit_rule_id": "TEST_RULE_V1",
        "provenance": {"membership": "fixture://membership", "policy": "fixture://policy"},
    }


class UniversePitSnapshotV1Tests(unittest.TestCase):
    def test_hash_is_deterministic_across_record_order(self):
        a = record("000001.SZ")
        b = record("600000.SH")
        first = build_universe_snapshot([a, b], "2026-10-16T15:01:00+08:00", dict(POLICY))
        second = build_universe_snapshot([b, a], "2026-10-16T15:01:00+08:00", dict(POLICY))
        self.assertTrue(first["universe_pit_valid"])
        self.assertEqual(first["universe_snapshot_hash"], second["universe_snapshot_hash"])
        self.assertEqual(first["eligible_symbols"], ["000001.SZ", "600000.SH"])

    def test_not_yet_listed_and_delisted_symbols_are_excluded(self):
        not_listed = record("001999.SZ")
        not_listed["listed_at_asof"] = False
        delisted = record("600999.SH")
        delisted["delisting_status_at_asof"] = "DELISTED"
        result = build_universe_snapshot([not_listed, delisted], "2026-10-16T15:01:00+08:00", dict(POLICY))
        self.assertEqual(result["eligible_symbols"], [])
        self.assertIn("001999.SZ", result["ineligible_symbols_with_reasons"])
        self.assertIn("NOT_LISTED_AT_ASOF", result["ineligible_symbols_with_reasons"]["001999.SZ"])
        self.assertIn("DELISTED_AT_ASOF", result["ineligible_symbols_with_reasons"]["600999.SH"])

    def test_missing_policy_identity_fails_closed(self):
        policy = dict(POLICY)
        policy["liquidity_policy_version"] = ""
        result = build_universe_snapshot([record()], "2026-10-16T15:01:00+08:00", policy)
        self.assertFalse(result["universe_pit_valid"])
        self.assertIsNone(result["universe_snapshot_hash"])
        self.assertIn("LIQUIDITY_POLICY_VERSION_MISSING", result["reasons"])

    def test_post_cutoff_mutable_record_becomes_unresolved(self):
        item = record()
        item["observed_at"] = "2026-10-16T15:02:00+08:00"
        result = build_universe_snapshot([item], "2026-10-16T15:01:00+08:00", dict(POLICY))
        self.assertEqual(result["eligible_symbols"], [])
        self.assertEqual(result["unresolved_symbols"], ["000001.SZ"])
        self.assertIn("POST_CUTOFF_RECORD", result["record_reasons"]["000001.SZ"])

    def test_unresolved_liquidity_or_new_listing_policy_cannot_be_eligible(self):
        item = record()
        item["liquidity_eligible_at_asof"] = "UNAVAILABLE"
        result = build_universe_snapshot([item], "2026-10-16T15:01:00+08:00", dict(POLICY))
        self.assertEqual(result["eligible_symbols"], [])
        self.assertEqual(result["unresolved_symbols"], ["000001.SZ"])
        self.assertIn("POLICY_RESULT_UNAVAILABLE", result["record_reasons"]["000001.SZ"])

    def test_policy_version_mismatch_is_unresolved_not_current_rule_fallback(self):
        item = record()
        item["liquidity_policy_version"] = "OTHER_POLICY"
        result = build_universe_snapshot([item], "2026-10-16T15:01:00+08:00", dict(POLICY))
        self.assertEqual(result["eligible_symbols"], [])
        self.assertEqual(result["unresolved_symbols"], ["000001.SZ"])
        self.assertIn("POLICY_VERSION_MISMATCH", result["record_reasons"]["000001.SZ"])

    def test_ineligible_policy_result_is_recorded_not_dropped(self):
        item = record()
        item["new_listing_eligible_at_asof"] = False
        result = build_universe_snapshot([item], "2026-10-16T15:01:00+08:00", dict(POLICY))
        self.assertEqual(result["eligible_symbols"], [])
        self.assertIn("000001.SZ", result["ineligible_symbols_with_reasons"])
        self.assertIn("NEW_LISTING_POLICY_INELIGIBLE", result["ineligible_symbols_with_reasons"]["000001.SZ"])


if __name__ == "__main__":
    unittest.main()
