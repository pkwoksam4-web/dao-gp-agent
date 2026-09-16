from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

import gp12_sohu_reference_panel_v1 as sut


class SohuReferencePanelContractTests(unittest.TestCase):
    def _raw(self):
        return pd.DataFrame([
            {"symbol": "000001.SZ", "date": "2024-01-02", "close": 9.21},
            {"symbol": "000001.SZ", "date": "2024-01-03", "close": 9.20},
            {"symbol": "000002.SZ", "date": "2024-01-02", "close": 10.00},
        ])

    def _fetcher(self, symbol, start, end, **kwargs):
        source = {
            "000001.SZ": [
                {"symbol": symbol, "date": "2024-01-02", "close": 9.21,
                 "change_cny": -0.18, "pct_percent": -1.92,
                 "turnover_percent": 0.60, "reference_close_cny": 9.39,
                 "source": "SOHU_HISHQ_REFERENCE_V1"},
                {"symbol": symbol, "date": "2024-01-03", "close": 9.20,
                 "change_cny": -0.01, "pct_percent": -0.11,
                 "turnover_percent": 0.50, "reference_close_cny": 9.21,
                 "source": "SOHU_HISHQ_REFERENCE_V1"},
            ],
            "000002.SZ": [
                {"symbol": symbol, "date": "2024-01-02", "close": 10.00,
                 "change_cny": 0.10, "pct_percent": 1.01,
                 "turnover_percent": 0.70, "reference_close_cny": 9.90,
                 "source": "SOHU_HISHQ_REFERENCE_V1"},
            ],
        }
        return [row for row in source[symbol] if start <= row["date"] <= end]

    def test_validate_expected_axis_requires_unique_symbol_dates(self):
        raw = self._raw()
        axis = sut.validate_expected_axis(raw, expected_symbol_n=2, expected_row_n=3)
        self.assertEqual(len(axis), 3)
        bad = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            sut.validate_expected_axis(bad, expected_symbol_n=2, expected_row_n=4)

    def test_collect_symbol_crosschecks_pinned_close(self):
        expected = self._raw().query("symbol == '000001.SZ'").copy()
        frame, audit = sut.collect_symbol(expected, fetcher=self._fetcher)
        self.assertEqual(audit["status"], "PASS_SYMBOL_REFERENCE")
        self.assertEqual(len(frame), 2)
        self.assertEqual(audit["close_mismatch_n"], 0)

        def bad_fetcher(symbol, start, end, **kwargs):
            rows = self._fetcher(symbol, start, end, **kwargs)
            rows[0] = {**rows[0], "close": 9.22}
            return rows

        with self.assertRaisesRegex(ValueError, "close mismatch"):
            sut.collect_symbol(expected, fetcher=bad_fetcher)

    def test_merge_shards_requires_exact_axis(self):
        expected = self._raw()
        shard0 = pd.DataFrame(self._fetcher("000001.SZ", "2024-01-02", "2024-01-03"))
        shard1 = pd.DataFrame(self._fetcher("000002.SZ", "2024-01-02", "2024-01-02"))
        merged, audit = sut.merge_reference_frames(expected, [shard0, shard1])
        self.assertEqual(audit["status"], "PASS_EXACT_REFERENCE_PANEL")
        self.assertEqual(len(merged), 3)
        with self.assertRaisesRegex(ValueError, "missing"):
            sut.merge_reference_frames(expected, [shard0])

    def test_materialize_and_merge_shard_artifacts_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw_path = root / "raw.parquet"
            self._raw().to_parquet(raw_path, index=False)
            shards_root = root / "shards"
            for shard_index in range(2):
                report = sut.materialize_shard(
                    raw_path,
                    shard_index=shard_index,
                    shard_count=2,
                    out_dir=shards_root / f"s{shard_index}",
                    workers=1,
                    fetcher=self._fetcher,
                    expected_symbol_n=2,
                    expected_row_n=3,
                )
                self.assertEqual(report["status"], "PASS_SHARD_REFERENCE")
            final_dir = root / "final"
            report = sut.merge_shard_artifacts(
                raw_path,
                shards_root=shards_root,
                out_dir=final_dir,
                expected_symbol_n=2,
                expected_row_n=3,
                expected_shard_count=2,
            )
            self.assertEqual(report["status"], "PASS_FULL_REFERENCE_PANEL")
            self.assertEqual(report["reference_rows"], 3)
            self.assertTrue((final_dir / "SOHU_REFERENCE_FULL_V1.parquet").exists())
            self.assertTrue((final_dir / "SOHU_REFERENCE_FULL_AUDIT_V1.json").exists())


if __name__ == "__main__":
    unittest.main()
