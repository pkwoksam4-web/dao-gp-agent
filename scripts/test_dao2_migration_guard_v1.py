import json
import unittest
from pathlib import Path
from dao2_migration_guard_v1 import validate_state

ROOT = Path(__file__).resolve().parents[1]

class Dao2MigrationGuardTests(unittest.TestCase):
    def test_migration_state_inherits_turnover_closure_and_remains_fail_closed(self):
        state = json.loads((ROOT / "data" / "DAO2_MIGRATION_STATE_V1.json").read_text(encoding="utf-8"))
        report = validate_state(state)
        self.assertTrue(report["migration_state_valid"])
        self.assertEqual(report["blocker_count"], 8)
        self.assertEqual(report["main_net_flow_unresolved_rows"], 16)
        self.assertFalse(report["model_freeze_allowed"])
        self.assertFalse(report["oos_metrics_allowed"])

    def test_guard_rejects_accidental_oos_open(self):
        state = json.loads((ROOT / "data" / "DAO2_MIGRATION_STATE_V1.json").read_text(encoding="utf-8"))
        state["formal"]["oos_metrics_allowed"] = True
        with self.assertRaises(AssertionError):
            validate_state(state)

    def test_guard_rejects_turnover_regression(self):
        state = json.loads((ROOT / "data" / "DAO2_MIGRATION_STATE_V1.json").read_text(encoding="utf-8"))
        state["gp12"]["turnover_closure"]["missing_n"] = 1
        with self.assertRaises(AssertionError):
            validate_state(state)

if __name__ == "__main__":
    unittest.main()
