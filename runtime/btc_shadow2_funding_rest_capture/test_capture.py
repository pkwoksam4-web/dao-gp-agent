import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import capture


class Response:
    status = 200

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class CaptureTests(unittest.TestCase):
    def row(self, ts):
        return {"symbol": "BTCUSDT", "fundingTime": ts, "fundingRate": "0.0001", "markPrice": "60000", "rateType": "Regular"}

    def test_valid_capture_preserves_raw_and_hashes_it(self):
        start = capture.utc_midnight(date(2026, 10, 1))
        body = json.dumps([self.row(start), self.row(start + 28_800_000)]).encode()
        with tempfile.TemporaryDirectory() as td:
            metadata = capture.capture(date(2026, 10, 1), date(2026, 10, 5), Path(td), lambda *a, **k: Response(body))
            self.assertEqual(metadata["capture_validation"], "PASS")
            self.assertEqual(metadata["raw_sha256"], hashlib.sha256(body).hexdigest())
            self.assertEqual((Path(td) / "funding_history_raw.json").read_bytes(), body)
            self.assertEqual(metadata["row_count"], 2)
            self.assertFalse(metadata["coverage_claim"])

    def test_out_of_range_row_fails_closed(self):
        before_start = capture.utc_midnight(date(2026, 10, 1)) - 1
        body = json.dumps([self.row(before_start)]).encode()
        with tempfile.TemporaryDirectory() as td:
            metadata = capture.capture(date(2026, 10, 1), date(2026, 10, 5), Path(td), lambda *a, **k: Response(body))
            self.assertEqual(metadata["capture_validation"], "FAIL")
            self.assertIn("ROW_0_OUT_OF_RANGE", metadata["validation_errors"])

    def test_duplicate_timestamp_fails_closed(self):
        start = capture.utc_midnight(date(2026, 10, 1))
        body = json.dumps([self.row(start), self.row(start)]).encode()
        with tempfile.TemporaryDirectory() as td:
            metadata = capture.capture(date(2026, 10, 1), date(2026, 10, 5), Path(td), lambda *a, **k: Response(body))
            self.assertIn("DUPLICATE_FUNDING_TIME", metadata["validation_errors"])

    def test_wrong_symbol_fails_closed(self):
        start = capture.utc_midnight(date(2026, 10, 1))
        row = self.row(start)
        row["symbol"] = "ETHUSDT"
        body = json.dumps([row]).encode()
        with tempfile.TemporaryDirectory() as td:
            metadata = capture.capture(date(2026, 10, 1), date(2026, 10, 5), Path(td), lambda *a, **k: Response(body))
            self.assertIn("ROW_0_SYMBOL_MISMATCH", metadata["validation_errors"])

    def test_invalid_date_order_rejected(self):
        with tempfile.TemporaryDirectory() as td, self.assertRaises(ValueError):
            capture.capture(date(2026, 10, 5), date(2026, 10, 1), Path(td))


if __name__ == "__main__":
    unittest.main()
