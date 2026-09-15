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
        self.assertEqual(out['ratio_availability_date'], '2025-11-27')
        self.assertAlmostEqual(out['previous_close'], 8.52, places=12)
        self.assertLessEqual(out['previous_close_diff_bp'], 0.01)

    def test_special_formula_between_previous_close_and_ex_date_is_valid(self):
        m = _subject()
        raw = [
            {'date': '2025-12-25', 'close': 7.90},
            {'date': '2025-12-29', 'close': 6.90},
        ]
        special = {
            'symbol': '000430.SZ',
            'ex_date': '2025-12-29',
            'formula_availability_date': '2025-12-27',
            'expected_prev_close': 7.90,
            'adjusted_reference_price': 6.87,
            'corrected_event_ratio': 6.87 / 7.90,
        }
        out = m.validate_special_prev_close('000430.SZ', raw, special, tolerance_bp=0.01)
        self.assertEqual(out['status'], 'PASS_SPECIAL_PREV_CLOSE_PIT')
        self.assertEqual(out['previous_trade_date'], '2025-12-25')
        self.assertEqual(out['ratio_availability_date'], '2025-12-27')

    def test_special_formula_on_ex_date_fails_closed(self):
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
        with self.assertRaisesRegex(ValueError, 'SPECIAL_RATIO_NOT_AVAILABLE_BEFORE_EX_DATE'):
            m.validate_special_prev_close('000697.SZ', raw, special, tolerance_bp=0.01)

    def test_final_override_assembly_is_exact_and_pairs_availability(self):
        m = _subject()
        stages = [
            [{'symbol': '000001.SZ', 'ex_date': '2024-01-02', 'corrected_event_ratio': 0.9}],
            [{'symbol': '000002.SZ', 'ex_date': '2024-02-02', 'corrected_event_ratio': 0.8}],
        ]
        specials = [
            {'symbol': '000003.SZ', 'ex_date': '2024-03-02', 'corrected_event_ratio': 0.7},
        ]
        availability = {
            ('000001.SZ', '2024-01-02'): '2023-12-20',
            ('000002.SZ', '2024-02-02'): '2024-01-20',
            ('000003.SZ', '2024-03-02'): '2024-02-20',
        }
        out = m.merge_final_override_ratios(
            stages,
            specials,
            availability,
            expected_standard_n=2,
            expected_special_n=1,
        )
        self.assertEqual(out['standard_n'], 2)
        self.assertEqual(out['special_n'], 1)
        self.assertEqual(out['total_n'], 3)
        self.assertEqual(out['ratios'][('000003.SZ', '2024-03-02')], 0.7)
        self.assertEqual(out['availability'][('000003.SZ', '2024-03-02')], '2024-02-20')

    def test_final_override_assembly_rejects_collision(self):
        m = _subject()
        stages = [[{'symbol': '000001.SZ', 'ex_date': '2024-01-02', 'corrected_event_ratio': 0.9}]]
        specials = [{'symbol': '000001.SZ', 'ex_date': '2024-01-02', 'corrected_event_ratio': 0.8}]
        availability = {('000001.SZ', '2024-01-02'): '2023-12-20'}
        with self.assertRaisesRegex(ValueError, 'override collision'):
            m.merge_final_override_ratios(
                stages, specials, availability,
                expected_standard_n=1, expected_special_n=1,
            )

    def test_audit_universe_preserves_na_and_closes_only_pit_adjusted_close(self):
        m = _subject()
        raw_by_symbol = {
            '000001.SZ': [
                {'date': '2024-01-01', 'close': 100.0},
                {'date': '2024-01-02', 'close': 50.0},
                {'date': '2024-01-03', 'close': 55.0},
            ],
        }
        factors_by_symbol = {
            '000001.SZ': [
                {'d': '2024-01-01', 'f': 2.0},
                {'d': '2024-01-02', 'f': 1.0},
            ],
        }
        frozen_records = [
            {'symbol': '000001.SZ', 'events': [
                {'ex_date': '2024-01-02', 'event_ratio': 0.6, 'source': 'NOMINAL'}
            ]},
            {'symbol': '600074.SH', 'events': []},
        ]
        manifest = {
            'nominal_events': [
                {'symbol': '000001.SZ', 'ex_date': '2024-01-02', 'availability_date': '2023-12-15'}
            ],
            'standard_overrides': [],
            'special_overrides': [{
                'symbol': '000001.SZ', 'ex_date': '2024-01-02',
                'formula_availability_date': '2023-12-20',
                'expected_prev_close': 100.0,
                'adjusted_reference_price': 50.0,
                'corrected_event_ratio': 0.5,
            }],
        }
        out = m.audit_universe(
            raw_by_symbol=raw_by_symbol,
            factors_by_symbol=factors_by_symbol,
            frozen_records=frozen_records,
            standard_stages=[],
            special_rows=manifest['special_overrides'],
            manifest=manifest,
            na_symbols=['600074.SH'],
            expected_standard_n=0,
            expected_special_n=1,
            threshold_bp=0.000001,
        )
        self.assertEqual(out['universe_n'], 2)
        self.assertEqual(out['formal_symbol_n'], 1)
        self.assertEqual(out['na_symbols'], ['600074.SH'])
        self.assertEqual(out['constant_scale_pass_n'], 1)
        self.assertEqual(out['constant_scale_fail_n'], 0)
        self.assertEqual(out['special_prev_close_pass_n'], 1)
        self.assertTrue(out['adjusted_close_pit_verified'])
        self.assertFalse(out['candidate_approval'])
        self.assertFalse(out['model_freeze_allowed'])
        self.assertFalse(out['oos_metrics_allowed'])


if __name__ == '__main__':
    unittest.main()
