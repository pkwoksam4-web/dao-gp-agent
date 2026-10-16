import json
import unittest
from pathlib import Path

from market_structure_schedule_v1 import validate_schedule


HERE = Path(__file__).resolve().parent


def load_schedule():
    return json.loads((HERE / "market_structure_regime_schedule_v1.json").read_text(encoding="utf-8"))


class MarketStructureScheduleV1Tests(unittest.TestCase):
    def test_repository_schedule_is_structurally_valid_but_not_formal_complete(self):
        result = validate_schedule(load_schedule())
        self.assertTrue(result["valid"])
        self.assertEqual(result["reasons"], [])
        self.assertFalse(result["formal_evaluation_scope_complete"])
        self.assertFalse(result["production_authorized"])
        self.assertEqual(len(result["schedule_hash"]), 64)

    def test_hash_is_deterministic_across_event_and_baseline_order(self):
        schedule_a = load_schedule()
        schedule_b = load_schedule()
        schedule_b["events"] = list(reversed(schedule_b["events"]))
        schedule_b["baseline_states"] = list(reversed(schedule_b["baseline_states"]))
        self.assertEqual(
            validate_schedule(schedule_a)["schedule_hash"],
            validate_schedule(schedule_b)["schedule_hash"],
        )

    def test_duplicate_event_id_fails_closed(self):
        schedule = load_schedule()
        schedule["events"].append(dict(schedule["events"][0]))
        result = validate_schedule(schedule)
        self.assertFalse(result["valid"])
        self.assertIn("DUPLICATE_EVENT_ID", result["reasons"])

    def test_unbound_source_fails_closed(self):
        schedule = load_schedule()
        schedule["events"][0]["source_bound"] = False
        result = validate_schedule(schedule)
        self.assertFalse(result["valid"])
        self.assertIn("EVENT_SOURCE_NOT_BOUND", result["reasons"])

    def test_post_cutoff_event_cannot_enter_active_event_list(self):
        schedule = load_schedule()
        schedule["events"].append(
            {
                "event_id": "ILLEGAL_POST_CUTOFF_EVENT",
                "effective_date": "2026-04-24",
                "first_affected_session": "2026-04-24",
                "axes": ["BOARD_PRICE_LIMIT_REGIME"],
                "scope": "TEST",
                "change": {"test": True},
                "authority": "Test Authority",
                "source_urls": ["https://example.com/authority"],
                "source_bound": True,
                "causal_use": "DIRECT_EXECUTION",
            }
        )
        result = validate_schedule(schedule)
        self.assertFalse(result["valid"])
        self.assertIn("EVENT_AFTER_FORMAL_WINDOW", result["reasons"])

    def test_partial_schedule_cannot_claim_formal_scope_complete(self):
        schedule = load_schedule()
        schedule["formal_evaluation_scope_complete"] = True
        result = validate_schedule(schedule)
        self.assertFalse(result["valid"])
        self.assertIn("PARTIAL_SCHEDULE_CANNOT_BE_FORMAL_COMPLETE", result["reasons"])

    def test_formal_window_is_frozen(self):
        schedule = load_schedule()
        schedule["formal_window"]["end"] = "2026-04-24"
        result = validate_schedule(schedule)
        self.assertFalse(result["valid"])
        self.assertIn("FORMAL_WINDOW_MISMATCH", result["reasons"])


if __name__ == "__main__":
    unittest.main()
