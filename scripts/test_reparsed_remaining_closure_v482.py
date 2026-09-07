from __future__ import annotations

import unittest

import reparsed_remaining_closure_v482 as mod


class ReparsedRemainingClosureV482Tests(unittest.TestCase):
    def test_checkpoint_moves_from_821_23_only_by_newly_closed_symbols(self):
        self.assertEqual(
            mod.updated_checkpoint(
                {'PASS':821,'EXACT_TERM_REVIEW':23,'MISSING_EVENT_REVIEW':0,'NOT_APPLICABLE':3},
                5,
            ),
            {'PASS':826,'EXACT_TERM_REVIEW':18,'MISSING_EVENT_REVIEW':0,'NOT_APPLICABLE':3},
        )

    def test_new_reparsed_term_must_pass_event_level_5bp_gate(self):
        event={
            'prev_actual_close':12.0,
            'cash_per_share_nominal':0.20,
            'stock_ratio':0.0,
            'capitalization_ratio':0.0,
            'rights_ratio':0.0,
            'rights_price':None,
        }
        good=mod.validate_reparsed_term(event,{'cash_per_share':0.245406,'cap_ratio':None},(12.0-0.245406)/12.0)
        self.assertTrue(good['accepted'])
        bad=mod.validate_reparsed_term(event,{'cash_per_share':2.0,'cap_ratio':None},(12.0-0.245406)/12.0)
        self.assertFalse(bad['accepted'])

    def test_duplicate_override_key_is_rejected(self):
        with self.assertRaises(ValueError):
            mod.merge_override_maps(
                {('000739.SZ','2024-05-23'):0.98},
                {('000739.SZ','2024-05-23'):0.97},
            )


if __name__=='__main__':
    unittest.main()
