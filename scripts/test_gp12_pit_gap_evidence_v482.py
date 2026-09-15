from __future__ import annotations

import datetime as dt
import importlib
import unittest


EXPECTED_GAPS = {
    ('000564.SZ', '2021-12-31'),
    ('300117.SZ', '2020-07-20'),
    ('300117.SZ', '2021-08-20'),
    ('600070.SH', '2020-07-10'),
    ('600070.SH', '2021-07-07'),
    ('600190.SH', '2020-07-02'),
    ('600190.SH', '2021-06-25'),
    ('600190.SH', '2022-06-24'),
    ('600190.SH', '2024-06-26'),
}


def _subject():
    try:
        return importlib.import_module('gp12_pit_gap_evidence_v482')
    except ModuleNotFoundError as exc:
        raise AssertionError('gp12_pit_gap_evidence_v482 production module is missing') from exc


class PitGapEvidenceTests(unittest.TestCase):
    def test_gap_target_identity_is_exact(self):
        m = _subject()
        self.assertEqual(set(m.GAP_KEYS), EXPECTED_GAPS)

    def test_official_record_requires_pre_exdate_implementation_and_matching_ratio(self):
        m = _subject()
        event = {
            'symbol': '300117.SZ',
            'ex_date': '2020-07-20',
            'cash_per_share': 0.003,
            'stock_ratio': 0.0,
            'capitalization_ratio': 0.0,
            'rights_ratio': 0.0,
            'rights_price': None,
            'prev_actual_close': 3.23,
            'event_ratio': (3.23 - 0.003) / 3.23,
        }
        announcement = {
            'announcementId': '1234567890',
            'announcementTitle': '2019年年度权益分派实施公告',
            'announcementTime': int(dt.datetime(2020, 7, 13, tzinfo=dt.timezone.utc).timestamp() * 1000),
        }
        terms = {
            'cash_per_share': 0.003,
            'cap_ratio': None,
            'formula_share_change_ratio': None,
        }
        out = m.validate_official_gap_record(
            event, announcement, 'a' * 64, terms, threshold_bp=5.0)
        self.assertEqual(out['status'], 'PASS_OFFICIAL_PIT_AVAILABILITY')
        self.assertEqual(out['availability_date'], '2020-07-13')
        self.assertLessEqual(out['event_diff_bp'], 1e-9)

        late = dict(announcement)
        late['announcementTime'] = int(dt.datetime(2020, 7, 21, tzinfo=dt.timezone.utc).timestamp() * 1000)
        with self.assertRaisesRegex(ValueError, 'EVENT_NOT_PIT_AVAILABLE'):
            m.validate_official_gap_record(event, late, 'a' * 64, terms, threshold_bp=5.0)

    def test_restructuring_capitalization_implementation_title_is_narrowly_accepted(self):
        m = _subject()
        cap = 2.2035714
        event = {
            'symbol': '000564.SZ',
            'ex_date': '2021-12-31',
            'cash_per_share': 0.0,
            'stock_ratio': 0.0,
            'capitalization_ratio': cap,
            'rights_ratio': 0.0,
            'rights_price': None,
            'prev_actual_close': 4.28,
            'event_ratio': 1.0 / (1.0 + cap),
        }
        announcement = {
            'announcementId': '1212058139',
            'announcementTitle': '关于重整计划资本公积金转增股本事项实施的公告',
            'announcementTime': int(dt.datetime(2021, 12, 27, tzinfo=dt.timezone.utc).timestamp() * 1000),
        }
        terms = {
            'cash_per_share': None,
            'cap_ratio': cap,
            'formula_share_change_ratio': None,
        }
        out = m.validate_official_gap_record(event, announcement, 'b' * 64, terms)
        self.assertEqual(out['status'], 'PASS_OFFICIAL_PIT_AVAILABILITY')
        self.assertEqual(out['availability_date'], '2021-12-27')


if __name__ == '__main__':
    unittest.main()
