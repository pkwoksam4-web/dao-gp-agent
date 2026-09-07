from __future__ import annotations

import unittest

import remaining_exact_closure_v482 as mod


class RemainingExactClosureTests(unittest.TestCase):
    def test_accepts_extracted_term_only_when_event_jump_stays_within_5bp(self):
        event={
            'prev_actual_close':10.0,
            'cash_per_share_nominal':0.10,
            'stock_ratio':0.0,
            'capitalization_ratio':0.0,
            'rights_ratio':0.0,
            'rights_price':None,
        }
        good=mod.validate_new_term(event,{'cash_per_share':0.1002,'cap_ratio':None},0.98998,5.0)
        self.assertTrue(good['accepted'])
        bad=mod.validate_new_term(event,{'cash_per_share':5.0,'cap_ratio':None},0.98998,5.0)
        self.assertFalse(bad['accepted'])
        self.assertGreater(bad['corrected_event_diff_bp'],5.0)

    def test_invalid_extracted_term_is_rejected_fail_closed_instead_of_aborting_batch(self):
        event={
            'prev_actual_close':10.0,
            'cash_per_share_nominal':0.10,
            'stock_ratio':0.0,
            'capitalization_ratio':0.0,
            'rights_ratio':0.0,
            'rights_price':None,
        }
        out=mod.validate_new_term(event,{'cash_per_share':37.0,'cap_ratio':None},0.98998,5.0)
        self.assertFalse(out['accepted'])
        self.assertIsNone(out['corrected_event_ratio'])
        self.assertIsNone(out['corrected_event_diff_bp'])
        self.assertIn('INVALID_EFFECTIVE_TERM',out['rejection_reason'])

    def test_checkpoint_moves_only_by_newly_closed_symbols(self):
        self.assertEqual(
            mod.updated_checkpoint_from_current(
                {'PASS':792,'EXACT_TERM_REVIEW':52,'MISSING_EVENT_REVIEW':0,'NOT_APPLICABLE':3},29
            ),
            {'PASS':821,'EXACT_TERM_REVIEW':23,'MISSING_EVENT_REVIEW':0,'NOT_APPLICABLE':3},
        )

    def test_rejects_duplicate_override_key(self):
        with self.assertRaises(ValueError):
            mod.merge_override_maps({('000001.SZ','2022-01-01'):0.99},{('000001.SZ','2022-01-01'):0.98})


if __name__=='__main__':
    unittest.main()
