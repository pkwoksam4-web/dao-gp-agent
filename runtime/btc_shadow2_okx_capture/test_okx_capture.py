import json
import tempfile
import unittest
from pathlib import Path

import okx_capture


class OKXCaptureTests(unittest.TestCase):
    def test_frozen_contract(self):
        self.assertEqual(okx_capture.ENDPOINT, 'https://www.okx.com/api/v5/market/history-candles')
        self.assertEqual(okx_capture.INST_ID, 'BTC-USDT-SWAP')
        self.assertEqual(okx_capture.BAR, '5m')
        self.assertEqual(okx_capture.LIMIT, 100)
        self.assertEqual(okx_capture.START_MS, 1786650900000)
        self.assertEqual(okx_capture.END_EXCLUSIVE_MS, 1791158400000)
        self.assertEqual(okx_capture.EXPECTED_ROWS, 15025)

    def test_full_exact_grid_passes_and_paginates_backwards(self):
        grid = list(range(okx_capture.START_MS, okx_capture.END_EXCLUSIVE_MS, okx_capture.STEP_MS))
        calls = []
        def fake(endpoint, params):
            self.assertEqual(endpoint, okx_capture.ENDPOINT)
            self.assertEqual(params['instId'], okx_capture.INST_ID)
            self.assertEqual(params['bar'], okx_capture.BAR)
            self.assertEqual(params['limit'], okx_capture.LIMIT)
            after = int(params['after'])
            calls.append(after)
            older = [t for t in grid if t < after]
            chunk = list(reversed(older[-okx_capture.LIMIT:]))
            rows = [[str(t),'1','2','0.5','1.5','10','0.1','15','1'] for t in chunk]
            body = json.dumps({'code':'0','msg':'','data':rows}).encode()
            return body, {'http_status':200,'retrieved_at_utc':'2026-10-09T00:00:00Z'}
        with tempfile.TemporaryDirectory() as td:
            report = okx_capture.capture_all(Path(td), fetcher=fake)
            self.assertTrue((Path(td)/'OKX_CAPTURE_REPORT.json').exists())
            self.assertTrue((Path(td)/'okx_btc_usdt_swap_5m.csv.gz').exists())
        self.assertTrue(report['pass'])
        self.assertEqual(report['rows_in_window'], okx_capture.EXPECTED_ROWS)
        self.assertEqual(report['duplicate_timestamps'], 0)
        self.assertEqual(report['missing_slots'], 0)
        self.assertEqual(report['extra_slots'], 0)
        self.assertTrue(report['all_closed'])
        self.assertGreater(len(calls), 1)
        self.assertTrue(all(b < a for a,b in zip(calls, calls[1:])))
        self.assertFalse(report['flow_alpha_allowed'])

    def test_missing_bar_fails_closed(self):
        missing = okx_capture.START_MS + 10 * okx_capture.STEP_MS
        grid = [t for t in range(okx_capture.START_MS, okx_capture.END_EXCLUSIVE_MS, okx_capture.STEP_MS) if t != missing]
        def fake(endpoint, params):
            after = int(params['after'])
            older = [t for t in grid if t < after]
            chunk = list(reversed(older[-okx_capture.LIMIT:]))
            rows = [[str(t),'1','2','0.5','1.5','10','0.1','15','1'] for t in chunk]
            return json.dumps({'code':'0','msg':'','data':rows}).encode(), {'http_status':200,'retrieved_at_utc':'x'}
        with tempfile.TemporaryDirectory() as td:
            report = okx_capture.capture_all(Path(td), fetcher=fake)
        self.assertFalse(report['pass'])
        self.assertEqual(report['missing_slots'], 1)
        self.assertIn('GRID_MISSING_SLOTS', report['reasons'])
        self.assertFalse(report['dataset_coverage_proven'])

    def test_api_error_writes_fail_report(self):
        def fake(endpoint, params):
            return json.dumps({'code':'50011','msg':'Rate limit reached','data':[]}).encode(), {'http_status':200,'retrieved_at_utc':'x'}
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            report=okx_capture.capture_all(root, fetcher=fake)
            self.assertTrue((root/'OKX_CAPTURE_REPORT.json').exists())
            self.assertTrue((root/'pages'/'page_000.json').exists())
        self.assertFalse(report['pass'])
        self.assertIn('OKX_API_CODE_NONZERO', report['reasons'])


if __name__ == '__main__':
    unittest.main()
