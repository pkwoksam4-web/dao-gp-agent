from __future__ import annotations

import pathlib
import unittest

import special_exright_closure_v482 as closure


class SpecialExRightClosureV482Tests(unittest.TestCase):
    def test_validated_override_partition_is_exact_11(self):
        rows = closure.load_override_ledger(pathlib.Path('../data/SPECIAL_EXRIGHT_REFERENCE_V482.json'))
        self.assertEqual(len(rows), 11)
        self.assertEqual(len({(r['symbol'], r['ex_date']) for r in rows}), 11)
        self.assertTrue(all(r['adjusted_reference_price'] > 0 for r in rows))
        self.assertTrue(all(r['formal_promotion'] is False for r in rows))

    def test_corrected_ratio_matches_independent_sina_factor_within_5bp(self):
        frozen = {
            'symbol': '600306.SH',
            'status': 'REVIEW_EXACT_TERMS_AFTER_MISSING_EVENT',
            'events': [{
                'ex_date': '2023-12-26',
                'prev_actual_close': 11.98,
                'event_ratio': 0.5405405405405405,
            }],
            'factor_validation': {
                'worst_rows': [{
                    'date': '2020-06-08',
                    'sina_factor': 0.6794657770991999,
                }]
            },
        }
        override = {
            'symbol': '600306.SH',
            'ex_date': '2023-12-26',
            'adjusted_reference_price': 8.14,
            'expected_prev_close': 11.98,
            'evidence_kind': 'RESTRUCTURING_SPECIAL_EXRIGHT_ANNOUNCEMENT',
            'evidence_url': 'https://example.invalid/validated-fixture',
            'formal_promotion': False,
        }
        result = closure.validate_one(frozen, override, threshold_bp=5.0)
        self.assertEqual(result['status'], 'PASS_SPECIAL_EXRIGHT_V482')
        self.assertLessEqual(result['diff_bp'], 5.0)
        self.assertAlmostEqual(result['corrected_event_ratio'], 8.14 / 11.98, places=12)

    def test_fail_closed_on_symbol_or_date_mismatch(self):
        frozen = {
            'symbol': '600306.SH',
            'events': [{'ex_date': '2023-12-26', 'prev_actual_close': 11.98}],
            'factor_validation': {'worst_rows': [{'sina_factor': 0.6794657770991999}]},
        }
        override = {
            'symbol': '000796.SZ',
            'ex_date': '2023-12-20',
            'adjusted_reference_price': 3.93,
            'expected_prev_close': 4.08,
            'evidence_kind': 'RESTRUCTURING_SPECIAL_EXRIGHT_ANNOUNCEMENT',
            'evidence_url': 'https://example.invalid/validated-fixture',
            'formal_promotion': False,
        }
        with self.assertRaises(ValueError):
            closure.validate_one(frozen, override)


if __name__ == '__main__':
    unittest.main()
