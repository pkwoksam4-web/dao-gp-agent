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

    def test_audit_symbol_path_uses_final_events_and_requires_constant_scale(self):
        m = _subject()
        raw = [
            {'date': '2024-01-01', 'close': 100.0},
            {'date': '2024-01-02', 'close': 50.0},
            {'date': '2024-01-03', 'close': 55.0},
        ]
        factors = [
            {'d': '2024-01-01', 'f': 2.0},
            {'d': '2024-01-02', 'f': 1.0},
        ]
        frozen = [{'ex_date': '2024-01-02', 'event_ratio': 0.6, 'source': 'NOMINAL'}]
        nominal = {('000001.SZ', '2024-01-02'): '2023-12-20'}
        overrides = {('000001.SZ', '2024-01-02'): 0.5}
        override_availability = {('000001.SZ', '2024-01-02'): '2023-12-28'}
        result = m.audit_symbol_path(
            symbol='000001.SZ', raw_rows=raw, qfq_factors=factors,
            frozen_events=frozen, nominal_availability=nominal,
            overrides=overrides, override_availability=override_availability,
            threshold_bp=0.000001,
        )
        self.assertEqual(result['status'], 'PASS_CONSTANT_SCALE')
        self.assertEqual(result['rows'], 3)
        self.assertAlmostEqual(result['scale'], 0.5, places=12)
        self.assertLessEqual(result['max_diff_bp'], 0.000001)
        self.assertEqual(result['final_event_n'], 1)
        self.assertEqual(result['final_override_n'], 1)


if __name__ == '__main__':
    unittest.main()
