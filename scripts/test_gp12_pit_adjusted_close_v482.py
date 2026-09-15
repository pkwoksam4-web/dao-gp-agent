from __future__ import annotations

import importlib
import unittest


def _subject():
    try:
        return importlib.import_module('gp12_pit_adjusted_close_v482')
    except ModuleNotFoundError as exc:
        raise AssertionError('gp12_pit_adjusted_close_v482 production module is missing') from exc


class PitAdjustedCloseAvailabilityTests(unittest.TestCase):
    def test_rejects_event_when_final_terms_arrive_after_ex_date(self):
        m = _subject()
        event = {
            'symbol': '600197.SH',
            'ex_date': '2020-07-02',
            'availability_date': '2020-07-03',
            'event_ratio': 0.96,
        }
        with self.assertRaisesRegex(ValueError, 'EVENT_NOT_PIT_AVAILABLE'):
            m.validate_event_availability(event)

    def test_forward_path_applies_event_from_ex_date_only(self):
        m = _subject()
        raw_rows = [
            {'date': '2020-06-30', 'close': 100.0},
            {'date': '2020-07-02', 'close': 90.0},
            {'date': '2020-07-03', 'close': 99.0},
        ]
        events = [{
            'symbol': 'TEST.SZ',
            'ex_date': '2020-07-02',
            'availability_date': '2020-07-01',
            'event_ratio': 0.9,
        }]
        path = m.build_forward_pit_adjusted_path(raw_rows, events)
        self.assertEqual([row['date'] for row in path], ['2020-06-30', '2020-07-02', '2020-07-03'])
        self.assertEqual([round(row['adjusted_close'], 10) for row in path], [100.0, 100.0, 110.0])


if __name__ == '__main__':
    unittest.main()
