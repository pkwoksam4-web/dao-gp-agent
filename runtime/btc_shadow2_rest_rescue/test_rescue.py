import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import rescue


class RescueTests(unittest.TestCase):
    def test_frozen_specs_exact(self):
        specs = rescue.frozen_specs()
        self.assertEqual(list(specs), ["oi", "basis", "funding"])
        self.assertEqual(specs["oi"]["endpoint"], "https://fapi.binance.com/futures/data/openInterestHist")
        self.assertEqual(specs["oi"]["fixed"], {"symbol": "BTCUSDT", "period": "5m", "limit": 500})
        self.assertEqual(specs["oi"]["start_ms"], 1790726400000)
        self.assertEqual(specs["oi"]["end_exclusive_ms"], 1791158400000)
        self.assertEqual(specs["basis"]["endpoint"], "https://fapi.binance.com/futures/data/basis")
        self.assertEqual(specs["basis"]["fixed"], {"pair": "BTCUSDT", "contractType": "PERPETUAL", "period": "5m", "limit": 500})
        self.assertEqual(specs["basis"]["start_ms"], 1791072000000)
        self.assertEqual(specs["basis"]["end_exclusive_ms"], 1791158400000)
        self.assertEqual(specs["funding"]["endpoint"], "https://fapi.binance.com/fapi/v1/fundingRate")
        self.assertEqual(specs["funding"]["fixed"], {"symbol": "BTCUSDT", "limit": 1000})
        self.assertEqual(specs["funding"]["start_ms"], 1786650900000)
        self.assertEqual(specs["funding"]["end_exclusive_ms"], 1791158400000)

    def test_oi_paginates_by_last_timestamp_plus_5m(self):
        specs = rescue.frozen_specs()
        oi = specs["oi"]
        calls = []
        start = oi["start_ms"]
        pages = [500, 500, 440]

        def fake(url, params):
            calls.append((url, dict(params)))
            idx = len(calls) - 1
            n = pages[idx]
            first = params["startTime"]
            rows = [{"timestamp": first + i * 300000, "sumOpenInterest": "1", "sumOpenInterestValue": "1"} for i in range(n)]
            return json.dumps(rows).encode(), {"http_status": 200, "retrieved_at_utc": "2026-10-09T00:00:00+00:00", "content_type": "application/json"}

        with tempfile.TemporaryDirectory() as td:
            result = rescue.capture_kind("oi", oi, Path(td), fetcher=fake)

        self.assertTrue(result["transport_complete"])
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0][1]["startTime"], start)
        self.assertEqual(calls[1][1]["startTime"], start + 500 * 300000)
        self.assertEqual(calls[2][1]["startTime"], start + 1000 * 300000)

    def test_failure_in_one_kind_does_not_block_other_kinds(self):
        seen = []
        specs = rescue.frozen_specs()

        def fake(url, params):
            kind = "oi" if "openInterestHist" in url else "basis" if "/basis" in url else "funding"
            seen.append(kind)
            if kind == "oi":
                raise OSError("synthetic network failure")
            if kind == "basis":
                rows = [{"timestamp": specs["basis"]["start_ms"] + i * 300000, "basis": "1", "basisRate": "0.00001", "futuresPrice": "100001", "indexPrice": "100000"} for i in range(288)]
            else:
                rows = [{"fundingTime": specs["funding"]["start_ms"], "fundingRate": "0.0001", "markPrice": "100000"}]
            return json.dumps(rows).encode(), {"http_status": 200, "retrieved_at_utc": "2026-10-09T00:00:00+00:00", "content_type": "application/json"}

        with tempfile.TemporaryDirectory() as td:
            report = rescue.capture_all(Path(td), fetcher=fake)
            self.assertTrue((Path(td) / "REST_CAPTURE_REPORT.json").exists())

        self.assertFalse(report["pass"])
        self.assertEqual(report["status"], "REST_TRANSPORT_INCOMPLETE")
        self.assertIn("oi", seen)
        self.assertIn("basis", seen)
        self.assertIn("funding", seen)
        self.assertFalse(report["rest"]["oi"]["transport_complete"])
        self.assertTrue(report["rest"]["basis"]["transport_complete"])
        self.assertTrue(report["rest"]["funding"]["transport_complete"])
        self.assertFalse(report["flow_alpha_allowed"])
        self.assertFalse(report["dataset_coverage_proven"])

    def test_raw_body_and_meta_hash_are_preserved(self):
        spec = rescue.frozen_specs()["basis"]
        body = b'[{"timestamp":1791072000000,"basis":"1","basisRate":"0.00001","futuresPrice":"100001","indexPrice":"100000"}]'

        def fake(url, params):
            return body, {"http_status": 200, "retrieved_at_utc": "2026-10-09T01:02:03+00:00", "content_type": "application/json"}

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = rescue.capture_kind("basis", spec, root, fetcher=fake)
            raw = root / "rest" / "basis" / "page_000.json"
            meta = root / "rest" / "basis" / "page_000.meta.json"
            self.assertEqual(raw.read_bytes(), body)
            data = json.loads(meta.read_text())

        self.assertTrue(result["transport_complete"])
        self.assertEqual(data["raw_body_sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(data["request_params"]["pair"], "BTCUSDT")
        self.assertEqual(data["retrieved_at_utc"], "2026-10-09T01:02:03+00:00")


if __name__ == "__main__":
    unittest.main()
