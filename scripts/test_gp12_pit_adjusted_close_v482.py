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


if __name__ == '__main__':
    unittest.main()
