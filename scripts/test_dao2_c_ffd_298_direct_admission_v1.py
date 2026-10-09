from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

BASE = Path("data/dao2/modules")
PATCH = BASE / "C_SECTOR_FFD_298_DIRECT_PATCH_V1.csv"
CHECKPOINT = BASE / "C_SECTOR_FFD_298_DIRECT_BINDING_CHECKPOINT_V1.json"
LEDGER = BASE / "C_301_GAP_LEDGER_V1.json"


class FFD298DirectAdmissionTests(unittest.TestCase):
    def test_298_direct_patch_is_exact_frozen_gap_subset_and_not_derived(self):
        self.assertTrue(PATCH.exists(), "298-row direct patch must exist")
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        schema = ledger["row_schema"]
        rows = [dict(zip(schema, r)) for r in ledger["rows"]]
        expected = {
            (str(r["sector_code"]), str(r["trade_date"])): r
            for r in rows
            if r.get("gap_class") == "DERIVED_CLOSE_EVIDENCE_ONLY"
            and r.get("current_provenance_type") == "DERIVED_CLOSE"
        }
        self.assertEqual(len(expected), 298)

        with PATCH.open("r", encoding="utf-8", newline="") as fh:
            patch = list(csv.DictReader(fh))
        self.assertEqual(len(patch), 298)
        keys = [(r["industry_code"], r["trade_date"]) for r in patch]
        self.assertEqual(len(set(keys)), 298)
        self.assertEqual(set(keys), set(expected))
        self.assertTrue(all(r["source_provider"] == "FFD / FinDesk" for r in patch))
        self.assertTrue(all(r["source_trade_date"] == r["trade_date"] for r in patch))
        self.assertTrue(all(r["fill_method"] == "NONE" for r in patch))
        self.assertTrue(all(r["provenance_type"] == "RAW_CLOSE" for r in patch))
        self.assertTrue(all(len(r["source_raw_sha256"]) == 64 for r in patch))
        self.assertTrue(all(r["source_artifact_id"] == "11605290540" for r in patch))
        self.assertTrue(all(r["vendor_contract_version"] == "0.8.15-consensus-estimates-20261008-r2" for r in patch))
        self.assertTrue(all(r["vendor_contract_raw_sha256"] == "274630e658eab0025e437543fddbe2a1db09d03da07bb830288816472a9dc05a" for r in patch))
        for r in patch:
            candidate = expected[(r["industry_code"], r["trade_date"])]["candidate_close_2dp"]
            self.assertAlmostEqual(round(float(r["close"]), 2), round(float(candidate), 2), places=2)

    def test_checkpoint_preserves_frozen_governance(self):
        self.assertTrue(CHECKPOINT.exists(), "298-row binding checkpoint must exist")
        cp = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        self.assertEqual(cp["status"], "PASS_BINDING_DIRECT_298_NOT_DERIVED")
        self.assertEqual(cp["admission"]["admitted_direct_rows"], 298)
        self.assertEqual(cp["admission"]["admitted_derived_rows"], 0)
        self.assertFalse(cp["governance"]["contract_lowered"])
        self.assertFalse(cp["governance"]["verifier_modified_for_ffd"])
        self.assertFalse(cp["governance"]["derived_close_migrated"])
        self.assertFalse(cp["governance"]["breadth_reopened"])
        self.assertEqual(cp["source"]["artifact_id"], 11605290540)
        self.assertEqual(cp["source"]["artifact_digest"], "sha256:7a54393f8495fda174c7ff1a376f4c4f0d8173fd6feb088af785b898da21f569")
        self.assertEqual(cp["source"]["result_content_sha256"], "617283bd986e1ba0d0ddb27c457a1088c39d246374cc022de9731563da14bc61")
        self.assertEqual(cp["validation"]["found_rows"], 298)
        self.assertEqual(cp["validation"]["missing_rows"], 0)
        self.assertEqual(cp["validation"]["extra_rows"], 0)
        self.assertEqual(cp["validation"]["crosscheck_exact_2dp_rows"], 298)
        self.assertEqual(cp["validation"]["crosscheck_mismatch_rows"], 0)
        self.assertTrue(cp["validation"]["all_http_200"])
        self.assertTrue(cp["validation"]["all_unadjusted"])
        self.assertTrue(cp["validation"]["all_no_recalculation"])


if __name__ == "__main__":
    unittest.main()
