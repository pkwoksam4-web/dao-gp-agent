from __future__ import annotations

import importlib
import unittest


def _subject():
    try:
        return importlib.import_module('gp12_pit_full_audit_v482')
    except ModuleNotFoundError as exc:
        raise AssertionError('gp12_pit_full_audit_v482 production module is missing') from exc


class PitFullAuditContracts(unittest.TestCase):
    def test_special_ratio_is_derivable_before_ex_date_from_previous_close(self):
        m = _subject()
        raw = [
            {'date': '2025-11-26', 'close': 8.40},
            {'date': '2025-11-27', 'close': 8.52},
            {'date': '2025-11-28', 'close': 8.10},
        ]
        special = {
            'symbol': '000697.SZ',
            'ex_date': '2025-11-28',
            'formula_availability_date': '2025-11-25',
            'expected_prev_close': 8.52,
            'adjusted_reference_price': 8.05,
            'corrected_event_ratio': 8.05 / 8.52,
        }
        out = m.validate_special_prev_close('000697.SZ', raw, special, tolerance_bp=0.01)
        self.assertEqual(out['status'], 'PASS_SPECIAL_PREV_CLOSE_PIT')
        self.assertEqual(out['previous_trade_date'], '2025-11-27')
        self.assertAlmostEqual(out['previous_close'], 8.52, places=12)
        self.assertLessEqual(out['previous_close_diff_bp'], 0.01)

    def test_special_formula_after_previous_market_close_fails_closed(self):
        m = _subject()
        raw = [
            {'date': '2025-11-27', 'close': 8.52},
            {'date': '2025-11-28', 'close': 8.10},
        ]
        special = {
            'symbol': '000697.SZ',
            'ex_date': '2025-11-28',
            'formula_availability_date': '2025-11-28',
            'expected_prev_close': 8.52,
            'adjusted_reference_price': 8.05,
            'corrected_event_ratio': 8.05 / 8.52,
        }
        with self.assertRaisesRegex(ValueError, 'SPECIAL_FORMULA_NOT_AVAILABLE_BY_PREV_CLOSE'):
            m.validate_special_prev_close('000697.SZ', raw, special, tolerance_bp=0.01)


if __name__ == '__main__':
    unittest.main()
