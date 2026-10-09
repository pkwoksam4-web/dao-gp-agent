import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import binance_gap_capture as m


def fake_fetcher(url):
    if url.endswith('.CHECKSUM'):
        zip_url = url[:-9]
        body, _ = fake_fetcher(zip_url)
        filename = zip_url.rsplit('/', 1)[-1]
        return f"{hashlib.sha256(body).hexdigest()}  {filename}\n".encode(), {'http_status': 200}
    filename = url.rsplit('/', 1)[-1]
    member = filename[:-4] + '.csv'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(member, b'header\nrow\n')
    return buf.getvalue(), {'http_status': 200}


class BinanceGapCaptureTests(unittest.TestCase):
    def test_frozen_gap_contract(self):
        objects = m.frozen_objects()
        self.assertEqual(m.EXPERIMENT_ID, 'BTC-FLOW-SUCCESSOR-20261009-B')
        self.assertEqual(len(objects), 20)
        self.assertEqual(sorted({o['date'] for o in objects}), [
            '2026-08-08','2026-08-09','2026-08-10','2026-08-11','2026-08-12'])
        self.assertEqual(sorted({o['family'] for o in objects}), [
            'indexPriceKlines','klines','markPriceKlines','metrics'])

    def test_reused_archive_validator_passes_all_20(self):
        with tempfile.TemporaryDirectory() as td:
            rep = m.capture_all(Path(td), fetcher=fake_fetcher, workers=4)
            self.assertTrue(rep['pass'])
            self.assertEqual(rep['experiment_id'], 'BTC-FLOW-SUCCESSOR-20261009-B')
            self.assertEqual(rep['objects_expected'], 20)
            self.assertEqual(rep['objects_passed'], 20)
            self.assertEqual(rep['date_start'], '2026-08-08')
            self.assertEqual(rep['date_end'], '2026-08-12')
            self.assertFalse(rep['dataset_coverage_proven'])
            self.assertFalse(rep['flow_alpha_allowed'])

if __name__ == '__main__':
    unittest.main()
