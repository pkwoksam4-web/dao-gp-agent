import csv
import hashlib
import pathlib
import tempfile
import unittest

from frozen_calendar_v480 import derive_verified_calendar


class FrozenCalendarHashTests(unittest.TestCase):
    def test_verified_union_returns_frozen_calendar(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / 'daily.csv'
            with p.open('w', encoding='utf-8', newline='') as f:
                w = csv.DictWriter(f, fieldnames=['symbol','date','tradestatus','isST'])
                w.writeheader()
                for date in ['2020-06-01','2020-06-02']:
                    w.writerow({'symbol':'000001.SZ','date':date,'tradestatus':'1','isST':'0'})
            expected = hashlib.sha256(b'2020-06-01\n2020-06-02\n').hexdigest()
            dates = derive_verified_calendar(
                p, expected_sha256=expected, expected_n=2,
                expected_first='2020-06-01', expected_last='2020-06-02')
            self.assertEqual(dates, ['2020-06-01','2020-06-02'])

    def test_hash_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / 'daily.csv'
            with p.open('w', encoding='utf-8', newline='') as f:
                w = csv.DictWriter(f, fieldnames=['symbol','date','tradestatus','isST'])
                w.writeheader()
                w.writerow({'symbol':'000001.SZ','date':'2020-06-01','tradestatus':'1','isST':'0'})
            with self.assertRaises(ValueError):
                derive_verified_calendar(
                    p, expected_sha256='0'*64, expected_n=1,
                    expected_first='2020-06-01', expected_last='2020-06-01')


if __name__ == '__main__':
    unittest.main()
