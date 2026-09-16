from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import gp12_upper_limit_special_v1 as sut


class UpperLimitSpecialContractTests(unittest.TestCase):
    def _manifest(self):
        return {
            "artifact": "GP12_UPPER_LIMIT_SPECIAL_NO_LIMIT_DATES_V1",
            "version": "1.0",
            "status": "NEW_RECONSTRUCTION_CANDIDATE",
            "historical_gp_v11_source_recovered": False,
            "model_freeze_allowed": False,
            "oos_metrics_allowed": False,
            "events": [
                {
                    "symbol": "000995.SZ",
                    "date": "2020-12-16",
                    "event_type": "RESTORED_LISTING_FIRST_DAY",
                    "no_price_limit": True,
                    "evidence_url": "https://example.com/a"
                },
                {
                    "symbol": "600462.SH",
                    "date": "2025-06-24",
                    "event_type": "DELISTING_ARRANGEMENT_FIRST_DAY",
                    "no_price_limit": True,
                    "evidence_url": "https://example.com/b"
                }
            ]
        }

    def test_manifest_loads_unique_exact_symbol_dates(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.json"
            p.write_text(json.dumps(self._manifest()), encoding="utf-8")
            m = sut.load_manifest(p)
        self.assertEqual(m["artifact"], "GP12_UPPER_LIMIT_SPECIAL_NO_LIMIT_DATES_V1")
        self.assertEqual(
            sut.special_no_limit_dates(m),
            {("000995.SZ", "2020-12-16"), ("600462.SH", "2025-06-24")},
        )

    def test_duplicate_symbol_date_fails_closed(self):
        m = self._manifest()
        m["events"].append(dict(m["events"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate special date"):
            sut.validate_manifest(m)

    def test_only_explicit_supported_event_types_are_allowed(self):
        m = self._manifest()
        m["events"][0]["event_type"] = "MAYBE_SPECIAL"
        with self.assertRaisesRegex(ValueError, "unsupported event_type"):
            sut.validate_manifest(m)

    def test_truth_no_limit_sentinel_accepts_both_known_large_markers(self):
        self.assertTrue(sut.is_no_limit_sentinel(1000000.0))
        self.assertTrue(sut.is_no_limit_sentinel(99999.999))
        self.assertFalse(sut.is_no_limit_sentinel(1000.0))

    def test_candidate_gate_flags_remain_false(self):
        m = self._manifest()
        sut.validate_manifest(m)
        self.assertFalse(m["historical_gp_v11_source_recovered"])
        self.assertFalse(m["model_freeze_allowed"])
        self.assertFalse(m["oos_metrics_allowed"])


if __name__ == "__main__":
    unittest.main()
