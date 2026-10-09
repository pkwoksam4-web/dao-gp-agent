import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import archive_capture


def make_zip(member: str, payload: bytes = b'x\n') -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(member, payload)
    return bio.getvalue()


class ArchiveCaptureTests(unittest.TestCase):
    def test_frozen_objects_exact_count_and_boundaries(self):
        objs = archive_capture.frozen_objects()
        self.assertEqual(len(objs), 212)
        self.assertEqual({o['family'] for o in objs}, {'klines','markPriceKlines','indexPriceKlines','metrics'})
        self.assertEqual(objs[0]['date'], '2026-08-13')
        self.assertEqual(objs[-1]['date'], '2026-10-04')
        self.assertIn('/daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08-13.zip', objs[0]['url'])
        metric = [o for o in objs if o['family']=='metrics' and o['date']=='2026-10-04'][0]
        self.assertTrue(metric['url'].endswith('/daily/metrics/BTCUSDT/BTCUSDT-metrics-2026-10-04.zip'))
        self.assertEqual(metric['member'], 'BTCUSDT-metrics-2026-10-04.csv')

    def test_capture_one_requires_official_checksum_and_exact_member(self):
        obj = [o for o in archive_capture.frozen_objects() if o['family']=='klines' and o['date']=='2026-10-04'][0]
        body = make_zip(obj['member'], b'a,b\n1,2\n')
        sha = hashlib.sha256(body).hexdigest()
        sidecar = f'{sha}  {obj["filename"]}\n'.encode()

        def fake(url):
            if url.endswith('.CHECKSUM'):
                return sidecar, {'http_status': 200, 'retrieved_at_utc': '2026-10-09T00:00:00Z'}
            return body, {'http_status': 200, 'retrieved_at_utc': '2026-10-09T00:00:01Z'}

        with tempfile.TemporaryDirectory() as td:
            result = archive_capture.capture_one(obj, Path(td), fetcher=fake)
            raw = Path(td) / obj['family'] / obj['date'] / obj['filename']
            self.assertEqual(raw.read_bytes(), body)
        self.assertTrue(result['pass'])
        self.assertEqual(result['zip_sha256'], sha)
        self.assertTrue(result['checksum_match'])
        self.assertTrue(result['zip_integrity_ok'])
        self.assertTrue(result['member_identity_ok'])

    def test_wrong_member_fails_closed(self):
        obj = [o for o in archive_capture.frozen_objects() if o['family']=='metrics'][0]
        body = make_zip('wrong.csv')
        sha = hashlib.sha256(body).hexdigest()
        sidecar = f'{sha}  {obj["filename"]}\n'.encode()
        def fake(url):
            return (sidecar if url.endswith('.CHECKSUM') else body), {'http_status': 200, 'retrieved_at_utc': '2026-10-09T00:00:00Z'}
        with tempfile.TemporaryDirectory() as td:
            result = archive_capture.capture_one(obj, Path(td), fetcher=fake)
        self.assertFalse(result['pass'])
        self.assertFalse(result['member_identity_ok'])
        self.assertIn('ZIP_MEMBER_IDENTITY_FAIL', result['reasons'])

    def test_capture_all_continues_after_one_transport_failure(self):
        objs = archive_capture.frozen_objects()[:2]
        good = make_zip(objs[1]['member'])
        good_sha = hashlib.sha256(good).hexdigest()
        def fake(url):
            if objs[0]['date'] in url:
                raise OSError('synthetic')
            if url.endswith('.CHECKSUM'):
                return f'{good_sha}  {objs[1]["filename"]}\n'.encode(), {'http_status': 200, 'retrieved_at_utc': 'x'}
            return good, {'http_status': 200, 'retrieved_at_utc': 'x'}
        with tempfile.TemporaryDirectory() as td:
            report = archive_capture.capture_all(Path(td), objects=objs, fetcher=fake)
            self.assertTrue((Path(td)/'ARCHIVE_CAPTURE_REPORT.json').exists())
        self.assertFalse(report['pass'])
        self.assertEqual(report['objects_expected'], 2)
        self.assertEqual(report['objects_passed'], 1)
        self.assertFalse(report['dataset_coverage_proven'])
        self.assertFalse(report['flow_alpha_allowed'])


if __name__ == '__main__':
    unittest.main()
