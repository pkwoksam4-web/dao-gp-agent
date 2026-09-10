import unittest

from gp12_event_timing_admission_v482 import audit_event_timing


class GP12EventTimingAdmissionV482Test(unittest.TestCase):
    def _expected(self):
        return [
            {"symbol": "000001.SZ", "ex_date": "2024-01-10", "source": "SRC_A"},
            {"symbol": "000002.SZ", "ex_date": "2024-02-20", "source": "SRC_B"},
            {"symbol": "000003.SZ", "ex_date": "2024-03-15", "source": "SRC_B"},
        ]

    def _observed(self):
        return [
            {
                "symbol": "000001.SZ",
                "ex_date": "2024-01-10",
                "source": "SRC_A",
                "pit_date": "2024-01-05",
                "evidence_id": "e1",
            },
            {
                "symbol": "000002.SZ",
                "ex_date": "2024-02-20",
                "source": "SRC_B",
                "pit_date": "2024-02-20",
                "evidence_id": "e2",
            },
            {
                "symbol": "000003.SZ",
                "ex_date": "2024-03-15",
                "source": "SRC_B",
                "pit_date": "2024-03-01",
                "evidence_id": "e3",
            },
        ]

    def test_complete_partition_passes(self):
        result = audit_event_timing(
            self._expected(),
            self._observed(),
            required_source_counts={"SRC_A": 1, "SRC_B": 2},
        )
        self.assertEqual(result["status"], "PASS_EVENT_TIMING_ADMISSION")
        self.assertEqual(result["expected_n"], 3)
        self.assertEqual(result["covered_n"], 3)
        self.assertEqual(result["missing_n"], 0)
        self.assertEqual(result["extra_n"], 0)
        self.assertEqual(result["late_n"], 0)
        self.assertEqual(result["source_counts"], {"SRC_A": 1, "SRC_B": 2})

    def test_missing_event_fails_closed(self):
        result = audit_event_timing(self._expected(), self._observed()[:-1])
        self.assertEqual(result["status"], "REVIEW_EVENT_TIMING_ADMISSION")
        self.assertEqual(result["missing_n"], 1)
        self.assertEqual(result["covered_n"], 2)

    def test_late_event_fails_closed(self):
        observed = self._observed()
        observed[1] = dict(observed[1], pit_date="2024-02-21")
        result = audit_event_timing(self._expected(), observed)
        self.assertEqual(result["status"], "REVIEW_EVENT_TIMING_ADMISSION")
        self.assertEqual(result["late_n"], 1)
        self.assertEqual(result["late_rows"][0]["symbol"], "000002.SZ")

    def test_duplicate_expected_key_is_rejected(self):
        expected = self._expected() + [dict(self._expected()[0])]
        with self.assertRaisesRegex(ValueError, "duplicate expected event key"):
            audit_event_timing(expected, self._observed())

    def test_duplicate_observed_key_is_rejected(self):
        observed = self._observed() + [dict(self._observed()[0])]
        with self.assertRaisesRegex(ValueError, "duplicate observed event key"):
            audit_event_timing(self._expected(), observed)

    def test_required_source_partition_mismatch_fails_closed(self):
        result = audit_event_timing(
            self._expected(),
            self._observed(),
            required_source_counts={"SRC_A": 2, "SRC_B": 1},
        )
        self.assertEqual(result["status"], "REVIEW_EVENT_TIMING_ADMISSION")
        self.assertFalse(result["source_partition_exact"])


if __name__ == "__main__":
    unittest.main()
