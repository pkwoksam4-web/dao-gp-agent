import importlib.util
from pathlib import Path
import sys
import unittest

MODULE_PATH = Path(__file__).with_name("dao2_a_l2_reconstruction_harness_v1.py")
MODULE_NAME = "dao2_a_l2_reconstruction_harness_v1"
spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
m = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[MODULE_NAME] = m
spec.loader.exec_module(m)


class L2HarnessTests(unittest.TestCase):
    def test_bucket_boundaries(self):
        self.assertEqual(m._bucket(49_999.99), "sm")
        self.assertEqual(m._bucket(50_000.0), "md")
        self.assertEqual(m._bucket(199_999.99), "md")
        self.assertEqual(m._bucket(200_000.0), "lg")
        self.assertEqual(m._bucket(999_999.99), "lg")
        self.assertEqual(m._bucket(1_000_000.0), "elg")

    def test_shenzhen_original_order_bucket_aggregation(self):
        orders = [
            m.CanonicalOrder("000001.SZ", "20230320", 101, "B", 10.0, 30_000),
            m.CanonicalOrder("000001.SZ", "20230320", 202, "S", 12.0, 100_000),
        ]
        trades = [
            m.CanonicalTrade("000001.SZ", "20230320", 1, "B", 10.0, 10_000, 999, 101),
            m.CanonicalTrade("000001.SZ", "20230320", 2, "B", 10.0, 5_000, 998, 101),
            m.CanonicalTrade("000001.SZ", "20230320", 3, "S", 12.0, 20_000, 202, 997),
        ]
        out = m.reconstruct(orders, trades, "000001.SZ", "20230320")
        self.assertEqual(out["buy_lg_amount"], 15.0)
        self.assertEqual(out["buy_elg_amount"], 0.0)
        self.assertEqual(out["sell_lg_amount"], 0.0)
        self.assertEqual(out["sell_elg_amount"], 24.0)
        self.assertFalse(out["strict_admission_allowed"])
        self.assertEqual(out["identity_status"], "PENDING_JESSICA_EXACT_OVERLAP")

    def test_missing_active_order_fails_closed(self):
        orders = [m.CanonicalOrder("000001.SZ", "20230320", 101, "B", 10.0, 30_000)]
        trades = [m.CanonicalTrade("000001.SZ", "20230320", 1, "B", 10.0, 1_000, 999, 404)]
        with self.assertRaises(m.ReconstructionError):
            m.reconstruct(orders, trades, "000001.SZ", "20230320")

    def test_side_mismatch_fails_closed(self):
        orders = [m.CanonicalOrder("000001.SZ", "20230320", 101, "S", 10.0, 30_000)]
        trades = [m.CanonicalTrade("000001.SZ", "20230320", 1, "B", 10.0, 1_000, 999, 101)]
        with self.assertRaises(m.ReconstructionError):
            m.reconstruct(orders, trades, "000001.SZ", "20230320")

    def test_shanghai_strict_mode_rejected(self):
        orders = [m.CanonicalOrder("600001.SH", "20230320", 101, "B", 10.0, 30_000)]
        trades = [m.CanonicalTrade("600001.SH", "20230320", 1, "B", 10.0, 1_000, 999, 101)]
        with self.assertRaises(m.ReconstructionError):
            m.reconstruct(orders, trades, "600001.SH", "20230320")

    def test_unknown_side_rejected(self):
        with self.assertRaises(m.ReconstructionError):
            m._normalize_side("U")


if __name__ == "__main__":
    unittest.main()
