import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import prewarmup_capture as m


def fake_binance_fetcher(url):
    if url.endswith('.CHECKSUM'):
        zip_url = url[:-9]
        body, _ = fake_binance_fetcher(zip_url)
        filename = zip_url.rsplit('/', 1)[-1]
        return f"{hashlib.sha256(body).hexdigest()}  {filename}\n".encode(), {'http_status': 200}
    filename = url.rsplit('/', 1)[-1]
    member = filename[:-4] + '.csv'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(member, b'header\nrow\n')
    return buf.getvalue(), {'http_status': 200}


def okx_row(ts, confirm='1'):
    return [str(ts), '100', '101', '99', '100', '1', '1', '100', confirm]


class PrewarmupCaptureTests(unittest.TestCase):
    def test_frozen_contract(self):
        self.assertEqual(m.EXPERIMENT_ID, 'BTC-FLOW-SUCCESSOR-20261009-B')
        self.assertEqual(m.BINANCE_START_DATE.isoformat(), '2026-08-03')
        self.assertEqual(m.BINANCE_END_DATE.isoformat(), '2026-08-07')
        self.assertEqual(len(m.binance_objects()), 20)
        self.assertEqual(m.OKX_START_MS, 1785715200000)
        self.assertEqual(m.OKX_END_EXCLUSIVE_MS, 1786218900000)
        self.assertEqual(m.OKX_EXPECTED_ROWS, 1679)

    def test_binance_reuses_validator_and_stays_fail_closed_for_research(self):
        with tempfile.TemporaryDirectory() as td:
            rep = m.capture_binance(Path(td), fetcher=fake_binance_fetcher, workers=4)
            self.assertTrue(rep['pass'])
            self.assertEqual(rep['objects_passed'], 20)
            self.assertFalse(rep['dataset_coverage_proven'])
            self.assertFalse(rep['flow_alpha_allowed'])

    def test_okx_exact_1679_grid_passes(self):
        rows = [okx_row(ts) for ts in range(m.OKX_START_MS, m.OKX_END_EXCLUSIVE_MS, m.OKX_STEP_MS)]
        rows.sort(key=lambda r: int(r[0]), reverse=True)
        def fetcher(endpoint, params):
            after = int(params['after'])
            eligible = [r for r in rows if int(r[0]) < after]
            return json.dumps({'code':'0','msg':'','data':eligible[:m.OKX_LIMIT]}).encode(), {'http_status':200}
        with tempfile.TemporaryDirectory() as td:
            rep = m.capture_okx(Path(td), fetcher=fetcher)
            self.assertTrue(rep['pass'])
            self.assertEqual(rep['rows_in_window'], 1679)
            self.assertEqual(rep['missing_slots'], 0)
            self.assertFalse(rep['flow_alpha_allowed'])

    def test_okx_missing_one_bar_fails(self):
        rows = [okx_row(ts) for ts in range(m.OKX_START_MS, m.OKX_END_EXCLUSIVE_MS, m.OKX_STEP_MS)]
        del rows[333]
        rows.sort(key=lambda r: int(r[0]), reverse=True)
        def fetcher(endpoint, params):
            after = int(params['after'])
            eligible = [r for r in rows if int(r[0]) < after]
            return json.dumps({'code':'0','msg':'','data':eligible[:m.OKX_LIMIT]}).encode(), {'http_status':200}
        with tempfile.TemporaryDirectory() as td:
            rep = m.capture_okx(Path(td), fetcher=fetcher)
            self.assertFalse(rep['pass'])
            self.assertEqual(rep['missing_slots'], 1)

if __name__ == '__main__':
    unittest.main()
