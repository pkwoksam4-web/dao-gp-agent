import unittest

from baseline_series_v1 import build_baseline_series


def make_dates(n):
    return [f"2025-01-{i+1:02d}" if i < 31 else f"2025-02-{i-30:02d}" for i in range(n)]


def monotone_dates(n):
    # Lexicographically sortable synthetic session IDs; parser should not assume calendar continuity.
    return [f"S{i:04d}" for i in range(n)]


def make_closes(n, start=100.0):
    closes = [start]
    for i in range(1, n):
        r = 0.001 if i % 3 else -0.0004
        closes.append(closes[-1] * (1.0 + r))
    return closes


class BaselineSeriesV1Tests(unittest.TestCase):
    def test_series_is_fail_closed_until_minimum_history(self):
        rows, meta = build_baseline_series(monotone_dates(275), make_closes(275))
        self.assertEqual(len(rows), 275)
        self.assertIsNone(rows[270]["risk_evidence_score"])
        self.assertIsNotNone(rows[271]["risk_evidence_score"])
        self.assertEqual(meta["row_count"], 275)

    def test_appending_future_data_does_not_change_prior_rows(self):
        dates = monotone_dates(280)
        closes = make_closes(280)
        short_rows, _ = build_baseline_series(dates[:276], closes[:276])
        full_rows, _ = build_baseline_series(dates, closes)
        self.assertEqual(short_rows, full_rows[:276])

    def test_duplicate_or_nonincreasing_session_id_is_rejected(self):
        dates = monotone_dates(275)
        dates[200] = dates[199]
        with self.assertRaises(ValueError):
            build_baseline_series(dates, make_closes(275))

    def test_metadata_hash_is_deterministic_and_sensitive_to_input(self):
        dates = monotone_dates(275)
        closes = make_closes(275)
        _, meta1 = build_baseline_series(dates, closes)
        _, meta2 = build_baseline_series(dates, closes)
        self.assertEqual(meta1["input_sha256"], meta2["input_sha256"])
        closes2 = list(closes)
        closes2[-1] *= 1.001
        _, meta3 = build_baseline_series(dates, closes2)
        self.assertNotEqual(meta1["input_sha256"], meta3["input_sha256"])


if __name__ == "__main__":
    unittest.main()
