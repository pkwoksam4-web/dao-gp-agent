from __future__ import annotations

import hashlib
import json
import unittest
from datetime import date, timedelta

from scripts import live_pit_ingest as ingest


def sample_rows():
    first = date(2026, 7, 31)
    expected = []
    cursor = first
    while len(expected) < 31:
        if cursor.weekday() < 5:
            expected.append(cursor.isoformat())
        cursor += timedelta(days=1)
    rows = []
    for i, td in enumerate(expected):
        raw_json = json.dumps({"close": 100 + i}, separators=(",", ":"))
        mode = "LIVE_PIT" if td == expected[-1] else "HISTORICAL_RECOVERY_NON_LIVE"
        metadata = {"mode": mode, "live_shadow_eligible": td == expected[-1]}
        if td != expected[-1]:
            metadata["lookback_tag"] = "HISTORICAL_LOOKBACK"
        rows.append({
            "trade_date": td, "source_id": f"source-{i}", "raw_json": raw_json,
            "source_raw_hash": hashlib.sha256(raw_json.encode()).hexdigest(),
            "retrieved_at": "2026-08-31T08:00:00+00:00",
            "persisted_at": f"{td}T08:00:00+00:00",
            "source_metadata_json": json.dumps(metadata),
        })
    return expected, rows


class LivePitProvenanceTests(unittest.TestCase):
    def test_runtime_attests_every_lookback_bar_and_current_bar(self):
        attester = getattr(ingest, "validate_feature_window_provenance", None)
        self.assertTrue(callable(attester), "runtime lookback provenance attester is required")
        expected, rows = sample_rows()
        attestation = attester("000636.SZ", expected, rows, expected[-1])
        self.assertEqual(len(attestation["bars"]), 31)
        self.assertEqual(attestation["bars"][0]["lookback_tag"], "HISTORICAL_LOOKBACK")
        self.assertEqual(attestation["bars"][0]["retrieved_at"], "2026-08-31T08:00:00+00:00")
        self.assertEqual(attestation["bars"][0]["persisted_at"], f"{expected[0]}T08:00:00+00:00")
        self.assertEqual(attestation["bars"][0]["bar_sha256"], rows[0]["source_raw_hash"])
        self.assertNotIn("lookback_tag", attestation["bars"][-1])

    def test_runtime_rejects_a_lookback_bar_without_historical_lookback_tag(self):
        attester = getattr(ingest, "validate_feature_window_provenance", None)
        self.assertTrue(callable(attester), "runtime lookback provenance attester is required")
        expected, rows = sample_rows()
        metadata = json.loads(rows[0]["source_metadata_json"])
        metadata.pop("lookback_tag", None)
        rows[0]["source_metadata_json"] = json.dumps(metadata)
        with self.assertRaisesRegex(RuntimeError, "HISTORICAL_LOOKBACK_TAG_MISSING"):
            attester("000636.SZ", expected, rows, expected[-1])

    def test_runtime_rejects_a_lookback_bar_without_matching_source_hash(self):
        attester = getattr(ingest, "validate_feature_window_provenance", None)
        self.assertTrue(callable(attester), "runtime lookback provenance attester is required")
        expected, rows = sample_rows()
        rows[0]["source_raw_hash"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "BAR_HASH_MISMATCH"):
            attester("000636.SZ", expected, rows, expected[-1])



    def test_runtime_rejects_bar_persisted_after_its_decision_cutoff(self):
        attester = getattr(ingest, "validate_feature_window_provenance", None)
        self.assertTrue(callable(attester), "runtime lookback provenance attester is required")
        expected, rows = sample_rows()
        # 16:10 Asia/Shanghai on 2026-07-31 is 08:10 UTC.
        rows[0]["persisted_at"] = "2026-07-31T08:11:00+00:00"
        with self.assertRaisesRegex(RuntimeError, "BAR_PERSISTED_AFTER_DECISION_CUTOFF"):
            attester("000636.SZ", expected, rows, expected[-1])

    def test_runtime_rejects_legacy_bar_with_unknown_persisted_at(self):
        attester = getattr(ingest, "validate_feature_window_provenance", None)
        self.assertTrue(callable(attester), "runtime lookback provenance attester is required")
        expected, rows = sample_rows()
        rows[0]["persisted_at"] = None
        with self.assertRaisesRegex(RuntimeError, "BAR_PROVENANCE_MISSING"):
            attester("000636.SZ", expected, rows, expected[-1])

    def test_runtime_query_uses_database_persisted_at_not_source_retrieval_time_as_ingest_time(self):
        source = Path("scripts/live_pit_ingest.py").read_text(encoding="utf-8")
        self.assertIn("mb.persisted_at", source)
        self.assertNotIn("s.retrieved_at AS ingested_at", source)

    def test_migration_preserves_old_rows_and_database_stamps_new_inserts(self):
        migration = Path("db/migrations/20261028_market_bars_persisted_at.sql").read_text(encoding="utf-8").lower()
        self.assertIn("add column if not exists persisted_at timestamptz", migration)
        self.assertIn("alter column persisted_at set default now()", migration)
        self.assertIn("new.persisted_at := clock_timestamp()", migration)
        self.assertIn("before insert on public.market_bars", migration)
        self.assertNotIn("update public.market_bars", migration)


if __name__ == "__main__":
    unittest.main()
