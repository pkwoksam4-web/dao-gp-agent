from __future__ import annotations

import importlib
import unittest


def _subject():
    try:
        return importlib.import_module('gp12_pit_adjusted_close_audit_v482')
    except ModuleNotFoundError as exc:
        raise AssertionError('gp12_pit_adjusted_close_audit_v482 production module is missing') from exc


class PitAdjustedCloseAuditContracts(unittest.TestCase):
    def test_finalize_events_switches_ratio_and_availability_together(self):
        m = _subject()
        frozen = [{
            'ex_date': '2025-11-28',
            'event_ratio': 0.95,
            'source': 'EASTMONEY_F10_PAGEAJAX_IMPLEMENTED',
        }]
        nominal = {('000697.SZ', '2025-11-28'): '2025-11-28'}
        overrides = {('000697.SZ', '2025-11-28'): 8.05 / 8.52}
        override_availability = {('000697.SZ', '2025-11-28'): '2025-11-25'}
        rows = m.finalize_symbol_events(
            '000697.SZ', frozen, nominal, overrides, override_availability)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]['event_ratio'], 8.05 / 8.52, places=12)
        self.assertEqual(rows[0]['availability_date'], '2025-11-25')
        self.assertEqual(rows[0]['availability_kind'], 'FINAL_OVERRIDE')

    def test_finalize_events_fails_when_nominal_availability_is_missing(self):
        m = _subject()
        frozen = [{'ex_date': '2021-05-14', 'event_ratio': 0.99, 'source': 'TEST'}]
        with self.assertRaisesRegex(ValueError, 'MISSING_EVENT_AVAILABILITY'):
            m.finalize_symbol_events('000001.SZ', frozen, {}, {}, {})


if __name__ == '__main__':
    unittest.main()
