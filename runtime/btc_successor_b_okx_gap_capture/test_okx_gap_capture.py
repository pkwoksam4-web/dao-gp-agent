import json
import tempfile
import unittest
from pathlib import Path

import okx_gap_capture as m


def row(ts, close='1'):
    return [str(ts), '100', '101', '99', '100', '1', '1', '100', close]


class GapCaptureTests(unittest.TestCase):
    def test_frozen_contract(self):
        self.assertEqual(m.EXPERIMENT_ID, 'BTC-FLOW-SUCCESSOR-20261009-B')
        self.assertEqual(m.INST_ID, 'BTC-USDT-SWAP')
        self.assertEqual(m.BAR, '5m')
        self.assertEqual(m.START_MS, 1786218900000)
        self.assertEqual(m.END_EXCLUSIVE_MS, 1786650900000)
        self.assertEqual(m.EXPECTED_ROWS, 1440)

    def test_exact_grid_passes(self):
        all_rows = [row(ts) for ts in range(m.START_MS, m.END_EXCLUSIVE_MS, m.STEP_MS)]
        all_rows.sort(key=lambda r: int(r[0]), reverse=True)
        def fetcher(endpoint, params):
            after = int(params['after'])
            eligible = [r for r in all_rows if int(r[0]) < after]
            body = json.dumps({'code':'0','msg':'','data':eligible[:m.LIMIT]}).encode()
            return body, {'http_status':200}
        with tempfile.TemporaryDirectory() as td:
            rep = m.capture_all(Path(td), fetcher=fetcher)
            self.assertTrue(rep['pass'])
            self.assertEqual(rep['rows_in_window'], 1440)
            self.assertEqual(rep['missing_slots'], 0)
            self.assertEqual(rep['duplicate_timestamps'], 0)
            self.assertEqual(rep['pages_captured'], 15)

    def test_missing_one_bar_fails_closed(self):
        all_rows = [row(ts) for ts in range(m.START_MS, m.END_EXCLUSIVE_MS, m.STEP_MS)]
        del all_rows[123]
        all_rows.sort(key=lambda r: int(r[0]), reverse=True)
        def fetcher(endpoint, params):
            after = int(params['after'])
            eligible = [r for r in all_rows if int(r[0]) < after]
            body = json.dumps({'code':'0','msg':'','data':eligible[:m.LIMIT]}).encode()
            return body, {'http_status':200}
        with tempfile.TemporaryDirectory() as td:
            rep = m.capture_all(Path(td), fetcher=fetcher)
            self.assertFalse(rep['pass'])
            self.assertEqual(rep['missing_slots'], 1)
            self.assertIn('GRID_MISSING_SLOTS', rep['reasons'])

    def test_unclosed_bar_fails_closed(self):
        all_rows = [row(ts) for ts in range(m.START_MS, m.END_EXCLUSIVE_MS, m.STEP_MS)]
        all_rows[100][8] = '0'
        all_rows.sort(key=lambda r: int(r[0]), reverse=True)
        def fetcher(endpoint, params):
            after = int(params['after'])
            eligible = [r for r in all_rows if int(r[0]) < after]
            return json.dumps({'code':'0','msg':'','data':eligible[:m.LIMIT]}).encode(), {'http_status':200}
        with tempfile.TemporaryDirectory() as td:
            rep = m.capture_all(Path(td), fetcher=fetcher)
            self.assertFalse(rep['pass'])
            self.assertIn('OKX_UNCLOSED_BAR_PRESENT', rep['reasons'])

if __name__ == '__main__':
    unittest.main()
