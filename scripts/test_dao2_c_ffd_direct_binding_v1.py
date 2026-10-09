import csv
import json
import unittest
from pathlib import Path

from dao2_sector_pit_verify_v1 import validate_series

BASE = Path("data/dao2/modules")


def load(name):
    return json.loads((BASE / name).read_text(encoding="utf-8"))


class FFDDirectBindingTests(unittest.TestCase):
    def test_ffd_binding_must_satisfy_existing_direct_gate_without_provider_whitelist_change(self):
        search = load("C_SECTOR_801020_DIRECT_CLOSE_SEARCH_V1.json")
        public = load("C_SECTOR_FFD_PUBLIC_HISTORY_CONTRACT_EVIDENCE_V1.json")
        ffd = load("C_SECTOR_FFD_801020_DIRECT_OHLC_EVIDENCE_V1.json")
        audit = load("C_SECTOR_FFD_801020_BINDING_AUDIT_V1.json")

        gate = search["admission_gate"]
        self.assertTrue(gate["source_repo_or_vendor_identity_required"])
        self.assertTrue(gate["raw_or_direct_historical_close_only"])
        self.assertTrue(gate["neighboring_overlap_exact_match_required"])
        self.assertNotIn("authoritative_provider_whitelist", gate)

        hc = public["history_interface"]
        self.assertEqual(public["binding_scope"]["vendor_identity"], "FFD / FinDesk")
        self.assertTrue(hc["public_stable_interface"])
        self.assertEqual(hc["status"], "available")
        self.assertIn("index", hc["markets"])
        self.assertEqual(hc["granularity"], "日线")
        self.assertEqual(hc["coverage_status"], "stable")
        self.assertEqual(hc["default_adjust"], "不复权")
        self.assertTrue(hc["ohlc_supported"])
        self.assertTrue(public["binding_scope"]["does_not_claim_upstream_brand"])
        self.assertTrue(public["binding_scope"]["does_not_equate_ffd_to_wind_ifind_tushare"])

        self.assertEqual(ffd["validation"]["target_rows_found"], 3)
        self.assertEqual(ffd["validation"]["neighbor_rows_found"], 6)
        self.assertEqual(ffd["validation"]["neighbor_anchor_exact_matches"], 6)
        self.assertEqual(ffd["validation"]["neighbor_anchor_mismatches"], 0)
        self.assertFalse(ffd["validation"]["direct_close_inference_used"])
        self.assertFalse(ffd["validation"]["rounded_return_used"])
        self.assertFalse(ffd["probe"]["conversion_or_recalculation_by_ffd"])
        self.assertEqual(ffd["probe"]["price_adjustment"], "none")
        self.assertTrue(ffd["probe"]["coverage_complete"])
        self.assertEqual(ffd["probe"]["missing_cells"], 0)
        self.assertEqual(len(ffd["raw_response_hashes"]), 3)

        target_identity = search["target_identity"]
        self.assertEqual(target_identity["candidate_code"], "801020.SI")
        self.assertEqual(target_identity["historical_name"], "采掘")
        self.assertEqual(target_identity["sw2014_valid_through"], "20211210")

        self.assertEqual(audit["decision"], "PASS_BINDING")
        self.assertEqual(audit["formal_status"], "FFD_DIRECT_OHLC_PASS_BINDING")
        self.assertFalse(audit["governance"]["contract_lowered"])
        self.assertFalse(audit["governance"]["verifier_modified_for_ffd"])
        self.assertFalse(audit["governance"]["derived_close_migrated"])

    def test_three_ffd_direct_rows_pass_existing_series_row_semantics(self):
        ffd = load("C_SECTOR_FFD_801020_DIRECT_OHLC_EVIDENCE_V1.json")
        targets = [r for r in ffd["rows"] if r["role"] == "target"]
        rows = [
            {
                "industry_code": "801020.SI",
                "trade_date": r["trade_date"],
                "close": str(r["close"]),
                "source_provider": "FFD / FinDesk",
                "source_trade_date": r["trade_date"],
                "fill_method": "NONE",
                "provenance_type": "RAW_CLOSE",
            }
            for r in targets
        ]
        expected = {(r["industry_code"], r["trade_date"]) for r in rows}
        got = validate_series(rows, expected)
        self.assertEqual(got["status"], "PASS")
        self.assertTrue(got["full_coverage"])
        self.assertEqual(got["derived_close_rows_rejected"], 0)

    def test_partial_admission_accounts_only_three_direct_rows_and_keeps_breadth_closed(self):
        series = load("C_SECTOR_SERIES_CHECKPOINT_V1.json")
        state = load("C_SECTOR_PIT_STATE_V1.json")
        checkpoint = load("C_SECTOR_FFD_801020_BINDING_CHECKPOINT_V1.json")
        patch_path = BASE / "C_SECTOR_FFD_801020_DIRECT_PATCH_V1.csv"
        with patch_path.open("r", encoding="utf-8-sig", newline="") as fh:
            patch_rows = list(csv.DictReader(fh))

        self.assertEqual(len(patch_rows), 3)
        self.assertEqual({r["trade_date"] for r in patch_rows}, {"20210806", "20211008", "20211022"})
        self.assertTrue(all(r["source_provider"] == "FFD / FinDesk" for r in patch_rows))
        self.assertTrue(all(r["source_trade_date"] == r["trade_date"] for r in patch_rows))
        self.assertTrue(all(r["fill_method"] == "NONE" for r in patch_rows))
        self.assertTrue(all(r["provenance_type"] == "RAW_CLOSE" for r in patch_rows))

        self.assertEqual(checkpoint["status"], "PASS_BINDING_PARTIAL_ADMISSION")
        self.assertEqual(checkpoint["admission"]["admitted_direct_rows"], 3)
        self.assertEqual(checkpoint["admission"]["admitted_derived_rows"], 0)
        self.assertEqual(checkpoint["admission"]["admissible_before"], 42783)
        self.assertEqual(checkpoint["admission"]["admissible_after"], 42786)
        self.assertEqual(checkpoint["admission"]["missing_after"], 298)
        self.assertFalse(checkpoint["admission"]["series_pass"])
        self.assertFalse(checkpoint["admission"]["breadth_derivation_allowed"])

        self.assertEqual(series["validation"]["admissible_coverage"], "42786/43084")
        self.assertEqual(series["validation"]["missing_required_keys"], 298)
        self.assertEqual(series["validation"]["admitted_direct_recovery_rows"], 3)
        self.assertEqual(series["validation"]["admitted_derived_close_rows"], 0)
        self.assertFalse(series["validation"]["full_formal_coverage_proven"])

        ss = state["progress"]["sector_series"]
        self.assertEqual(ss["admissible_coverage"], "42786/43084")
        self.assertEqual(ss["missing_required_keys"], 298)
        self.assertEqual(ss["admitted_direct_recovery_rows"], 3)
        self.assertEqual(ss["admitted_derived_close_rows"], 0)
        self.assertEqual(ss["unresolved_direct_keys"], [])
        self.assertFalse(state["progress"]["sector_breadth"]["derivation_allowed"])


if __name__ == "__main__":
    unittest.main()
