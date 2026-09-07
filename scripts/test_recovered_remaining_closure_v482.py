from __future__ import annotations

import unittest

import recovered_remaining_closure_v482 as mod


class RecoveredRemainingClosureV482Tests(unittest.TestCase):
    def test_checkpoint_moves_only_by_newly_closed_symbols(self):
        self.assertEqual(
            mod.updated_checkpoint(
                {'PASS':826,'EXACT_TERM_REVIEW':18,'MISSING_EVENT_REVIEW':0,'NOT_APPLICABLE':3},
                6,
            ),
            {'PASS':832,'EXACT_TERM_REVIEW':12,'MISSING_EVENT_REVIEW':0,'NOT_APPLICABLE':3},
        )

    def test_invalid_recovered_term_is_rejected_without_aborting_batch(self):
        event={
            'prev_actual_close':10.0,
            'cash_per_share_nominal':0.10,
            'stock_ratio':0.0,
            'capitalization_ratio':0.0,
            'rights_ratio':0.0,
            'rights_price':None,
        }
        x=mod.validate_recovered_term(event,{'cash_per_share':20.0,'cap_ratio':None},0.99)
        self.assertFalse(x['accepted'])
        self.assertIsNone(x['corrected_event_ratio'])

    def test_merge_refuses_existing_override_collision(self):
        with self.assertRaises(ValueError):
            mod.merge_override_maps(
                {('001230.SZ','2025-06-13'):0.99},
                {('001230.SZ','2025-06-13'):0.98},
            )


if __name__=='__main__':
    unittest.main()
