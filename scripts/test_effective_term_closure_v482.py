from __future__ import annotations

import unittest

import effective_term_closure_v482 as closure


class EffectiveTermClosureV482Tests(unittest.TestCase):
    def test_effective_cash_replaces_nominal_cash_only(self):
        event = {
            'cash_per_share_nominal': 0.3,
            'stock_ratio': 0.0,
            'capitalization_ratio': 0.0,
            'rights_ratio': 0.0,
            'rights_price': None,
            'prev_actual_close': 6.66,
        }
        ratio = closure.corrected_event_ratio(
            event,
            {'cash_per_share': 0.288272, 'cap_ratio': None},
        )
        self.assertAlmostEqual(ratio, (6.66 - 0.288272) / 6.66, places=15)

    def test_full_path_passes_only_after_effective_override(self):
        factors = [
            {'d': '1900-01-01', 'f': 1.0},
            {'d': '2022-06-02', 'f': 0.9673134228187391},
        ]
        record = {
            'symbol': '000100.SZ',
            'events': [{
                'ex_date': '2022-06-02',
                'cash_per_share_nominal': 0.15,
                'stock_ratio': 0.0,
                'capitalization_ratio': 0.0,
                'rights_ratio': 0.0,
                'rights_price': None,
                'prev_actual_close': 4.47,
                'event_ratio': 0.9664429530201342,
            }],
        }
        nominal = closure.recompute_symbol_max_diff_bp(record, factors, {})
        fixed = closure.recompute_symbol_max_diff_bp(
            record,
            factors,
            {('000100.SZ', '2022-06-02'): 0.9673134451901566},
        )
        self.assertGreater(nominal['max_diff_bp'], 5.0)
        self.assertLessEqual(fixed['max_diff_bp'], 5.0)

    def test_checkpoint_moves_only_fully_closed_symbols(self):
        self.assertEqual(
            closure.updated_checkpoint(9),
            {'PASS': 766, 'EXACT_TERM_REVIEW': 78, 'MISSING_EVENT_REVIEW': 0, 'NOT_APPLICABLE': 3},
        )


if __name__ == '__main__':
    unittest.main()
