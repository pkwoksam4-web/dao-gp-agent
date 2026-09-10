import unittest

from gp12_override_timing_admission_v482 import (
    audit_override_timing,
    merge_standard_overrides,
)


class GP12OverrideTimingAdmissionV482Test(unittest.TestCase):
    def _standard_override(self):
        return {
            "symbol": "000001.SZ",
            "ex_date": "2024-05-20",
            "corrected_event_ratio": 0.98,
            "announcement_id": "123",
            "pdf_sha256": "abc",
        }

    def _standard_evidence(self):
        return {
            "symbol": "000001.SZ",
            "ex_date": "2024-05-20",
            "announcement": {"announcementId": "123", "announcementTime": 1715817600000},
            "pdf_evidence": {"sha256": "abc"},
        }

    def _special(self, symbol="000002.SZ", ex_date="2024-06-20", adjunct_date="2024-06-19"):
        return {
            "symbol": symbol,
            "ex_date": ex_date,
            "adjusted_reference_price": 8.0,
            "status": "PASS_CNINFO_MATERIALIZED",
            "provenance": {
                "announcement_id": "900",
                "adjunct_url": f"finalpage/{adjunct_date}/900.PDF",
                "materialized_sha256": "specialsha",
            },
        }

    def test_complete_standard_and_special_pass(self):
        result = audit_override_timing(
            standard_overrides=[self._standard_override()],
            standard_evidence=[self._standard_evidence()],
            special_overrides=[self._special()],
            sameday_proofs=[],
        )
        self.assertEqual(result["status"], "PASS_OVERRIDE_TIMING_ADMISSION")
        self.assertEqual(result["standard_pass_n"], 1)
        self.assertEqual(result["special_pass_n"], 1)
        self.assertEqual(result["total_pass_n"], 2)
        self.assertEqual(result["missing_n"], 0)
        self.assertEqual(result["late_n"], 0)

    def test_standard_announcement_id_mismatch_fails_closed(self):
        evidence = self._standard_evidence()
        evidence["announcement"]["announcementId"] = "999"
        result = audit_override_timing(
            [self._standard_override()], [evidence], [], []
        )
        self.assertEqual(result["status"], "REVIEW_OVERRIDE_TIMING_ADMISSION")
        self.assertEqual(result["missing_n"], 1)

    def test_standard_sha_mismatch_fails_closed(self):
        evidence = self._standard_evidence()
        evidence["pdf_evidence"]["sha256"] = "wrong"
        result = audit_override_timing(
            [self._standard_override()], [evidence], [], []
        )
        self.assertEqual(result["status"], "REVIEW_OVERRIDE_TIMING_ADMISSION")
        self.assertEqual(result["missing_n"], 1)

    def test_standard_late_announcement_fails_closed(self):
        evidence = self._standard_evidence()
        evidence["announcement"]["announcementTime"] = 1716249600000  # 2024-05-21 UTC
        result = audit_override_timing(
            [self._standard_override()], [evidence], [], []
        )
        self.assertEqual(result["status"], "REVIEW_OVERRIDE_TIMING_ADMISSION")
        self.assertEqual(result["late_n"], 1)

    def test_same_day_special_requires_preopen_proof(self):
        special = self._special("000697.SZ", "2025-11-28", "2025-11-28")
        result = audit_override_timing([], [], [special], [])
        self.assertEqual(result["status"], "REVIEW_OVERRIDE_TIMING_ADMISSION")
        self.assertEqual(result["missing_preopen_n"], 1)

    def test_same_day_special_with_preopen_proof_passes(self):
        special = self._special("000697.SZ", "2025-11-28", "2025-11-28")
        proof = {
            "symbol": "000697.SZ",
            "ex_date": "2025-11-28",
            "announcement_id": "900",
            "status": "PASS",
            "published_before_ex_open": True,
            "announcement_time_asia_shanghai": "2025-11-28T00:00:00+08:00",
            "ex_date_open_asia_shanghai": "2025-11-28T09:30:00+08:00",
        }
        result = audit_override_timing([], [], [special], [proof])
        self.assertEqual(result["status"], "PASS_OVERRIDE_TIMING_ADMISSION")
        self.assertEqual(result["special_pass_n"], 1)
        self.assertEqual(result["same_day_preopen_pass_n"], 1)

    def test_same_day_special_at_or_after_open_fails_closed(self):
        special = self._special("000697.SZ", "2025-11-28", "2025-11-28")
        proof = {
            "symbol": "000697.SZ",
            "ex_date": "2025-11-28",
            "announcement_id": "900",
            "status": "PASS",
            "published_before_ex_open": False,
            "announcement_time_asia_shanghai": "2025-11-28T09:30:00+08:00",
            "ex_date_open_asia_shanghai": "2025-11-28T09:30:00+08:00",
        }
        result = audit_override_timing([], [], [special], [proof])
        self.assertEqual(result["status"], "REVIEW_OVERRIDE_TIMING_ADMISSION")
        self.assertEqual(result["late_n"], 1)

    def test_reparsed_override_may_bind_id_and_sha_from_unique_evidence(self):
        override = {
            "symbol": "000541.SZ",
            "ex_date": "2021-07-16",
            "corrected_event_ratio": 0.98,
        }
        evidence = {
            "symbol": "000541.SZ",
            "ex_date": "2021-07-16",
            "announcement": {"announcementId": "777", "announcementTime": 1625961600000},
            "pdf_evidence": {"sha256": "reparsedsha"},
        }
        result = audit_override_timing([override], [evidence], [], [])
        self.assertEqual(result["status"], "PASS_OVERRIDE_TIMING_ADMISSION")
        self.assertEqual(result["standard_pass_n"], 1)

    def test_duplicate_stage_override_with_conflicting_ratio_is_rejected(self):
        a = self._standard_override()
        b = dict(a, corrected_event_ratio=0.97)
        with self.assertRaisesRegex(ValueError, "conflicting standard override"):
            merge_standard_overrides([[a], [b]])

    def test_duplicate_stage_override_with_same_ratio_deduplicates(self):
        a = self._standard_override()
        b = dict(a)
        merged = merge_standard_overrides([[a], [b]])
        self.assertEqual(len(merged), 1)


if __name__ == "__main__":
    unittest.main()
