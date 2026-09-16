from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

import gp12_status_panel_v1 as sut


class StatusPanelArtifactContractTests(unittest.TestCase):
    def _panel(self):
        return pd.DataFrame([
            {
                "symbol": "000001.SZ", "date": "2024-01-02", "is_st": False,
                "tradable": True, "special_no_limit": False, "listing_trade_rank": None,
                "reference_close_cny": 10.00, "limit_pct_percent": 10.0,
                "limit_price_cny": 11.00, "upper_limit": True,
            },
            {
                "symbol": "000670.SZ", "date": "2022-08-22", "is_st": False,
                "tradable": True, "special_no_limit": True, "listing_trade_rank": None,
                "reference_close_cny": 2.10, "limit_pct_percent": None,
                "limit_price_cny": None, "upper_limit": False,
            },
            {
                "symbol": "000001.SZ", "date": "2024-01-03", "is_st": False,
                "tradable": False, "special_no_limit": False, "listing_trade_rank": None,
                "reference_close_cny": None, "limit_pct_percent": None,
                "limit_price_cny": None, "upper_limit": False,
            },
        ])

    def test_load_special_evidence_requires_exact_unique_source_backed_entries(self):
        doc = {
            "artifact": "GP12_STATUS_SPECIAL_NO_LIMIT_EVIDENCE_V1",
            "entry_count": 2,
            "entries": [
                {"symbol": "000670.SZ", "date": "2022-08-22", "no_price_limit": True,
                 "event_type": "RESTORED_LISTING_FIRST_TRADING_DAY", "source_url": "https://example.com/a.pdf"},
                {"symbol": "600190.SH", "date": "2025-06-30", "no_price_limit": True,
                 "event_type": "DELISTING_ARRANGEMENT_FIRST_TRADING_DAY", "source_url": "https://example.com/b.pdf"},
            ],
        }
        keys = sut.load_special_no_limit_evidence(doc, expected_entry_count=2)
        self.assertEqual(keys, {("000670.SZ", "2022-08-22"), ("600190.SH", "2025-06-30")})

        bad = json.loads(json.dumps(doc))
        bad["entries"][1]["symbol"] = "000670.SZ"
        bad["entries"][1]["date"] = "2022-08-22"
        with self.assertRaisesRegex(ValueError, "duplicate special evidence"):
            sut.load_special_no_limit_evidence(bad, expected_entry_count=2)

    def test_truth_crosscheck_exact_and_mismatch_fail_closed(self):
        panel = self._panel()
        truth = pd.DataFrame([
            {"code": "000001.SZ", "date": "2024-01-02", "close": 11.00, "prev_close": 10.00, "high_limit": 11.00},
            {"code": "000670.SZ", "date": "2022-08-22", "close": 2.42, "prev_close": 2.10, "high_limit": 1000000.0},
        ])
        summary = sut.crosscheck_upper_limit_truth(
            panel, truth, {("000670.SZ", "2022-08-22")}, require_exact=True
        )
        self.assertEqual(summary["overlap_rows"], 2)
        self.assertEqual(summary["no_limit_mismatch_n"], 0)
        self.assertEqual(summary["price_mismatch_n"], 0)
        self.assertEqual(summary["boolean_mismatch_n"], 0)

        bad = truth.copy()
        bad.loc[0, "high_limit"] = 12.00
        with self.assertRaisesRegex(ValueError, "truth crosscheck mismatch"):
            sut.crosscheck_upper_limit_truth(
                panel, bad, {("000670.SZ", "2022-08-22")}, require_exact=True
            )

    def test_materialize_status_artifact_roundtrip_and_hashes(self):
        panel = self._panel()
        audit = {
            "status": "PASS_EXACT_STATUS_PANEL",
            "lifecycle_rows": 3,
            "lifecycle_symbols": 2,
            "tradable_rows": 2,
            "nontradable_rows": 1,
            "special_no_limit_rows": 1,
            "no_limit_rows": 1,
            "upper_limit_rows": 1,
            "duplicate_symbol_dates": 0,
            "reference_key_mismatch_n": 0,
            "close_mismatch_n": 0,
        }
        with tempfile.TemporaryDirectory() as tmp:
            manifest = sut.materialize_status_artifact(
                panel,
                audit,
                Path(tmp),
                metadata={"origin": "NEW_RECONSTRUCTION_CANDIDATE"},
            )
            parquet = Path(tmp) / "GP12_STATUS_PANEL_V1.parquet"
            audit_path = Path(tmp) / "GP12_STATUS_PANEL_AUDIT_V1.json"
            self.assertTrue(parquet.exists())
            self.assertTrue(audit_path.exists())
            loaded = pd.read_parquet(parquet)
            self.assertEqual(len(loaded), 3)
            doc = json.loads(audit_path.read_text(encoding="utf-8"))
            self.assertEqual(doc["status"], "PASS_EXACT_STATUS_PANEL")
            self.assertEqual(doc["origin"], "NEW_RECONSTRUCTION_CANDIDATE")
            self.assertEqual(manifest["panel_sha256"], doc["panel_sha256"])
            self.assertEqual(manifest["audit_sha256"], doc["audit_sha256"])
            self.assertEqual(len(manifest["panel_sha256"]), 64)
            self.assertEqual(len(manifest["audit_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
