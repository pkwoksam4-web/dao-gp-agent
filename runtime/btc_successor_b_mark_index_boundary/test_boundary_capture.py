import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

import boundary_capture as m


def fake_fetcher(url):
    if url.endswith('.CHECKSUM'):
        body, _ = fake_fetcher(url[:-9])
        fn = url[:-9].rsplit('/', 1)[-1]
        return f"{hashlib.sha256(body).hexdigest()}  {fn}\n".encode(), {'http_status': 200}
    fn = url.rsplit('/', 1)[-1]
    member = fn[:-4] + '.csv'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(member, b'header\nrow\n')
    return buf.getvalue(), {'http_status': 200}


class BoundaryCaptureTests(unittest.TestCase):
    def test_contract(self):
        objs = m.frozen_objects()
        self.assertEqual(m.EXPERIMENT_ID, 'BTC-FLOW-SUCCESSOR-20261009-B')
        self.assertEqual(len(objs), 2)
        self.assertEqual({o['family'] for o in objs}, {'markPriceKlines', 'indexPriceKlines'})
        self.assertEqual({o['date'] for o in objs}, {'2026-08-02'})

    def test_reuses_checksum_zip_validator(self):
        with tempfile.TemporaryDirectory() as td:
            rep = m.capture_all(Path(td), fetcher=fake_fetcher, workers=2)
            self.assertTrue(rep['pass'])
            self.assertEqual(rep['objects_passed'], 2)
            self.assertFalse(rep['dataset_coverage_proven'])
            self.assertFalse(rep['flow_alpha_allowed'])

if __name__ == '__main__':
    unittest.main()
