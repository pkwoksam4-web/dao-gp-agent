import unittest

import final_four_closure_v482 as mod


class FinalFourClosureV482Tests(unittest.TestCase):
    def test_merge_840_checkpoint_overrides_builds_265_base(self):
        base = {(f'B{i:03d}', '2024-01-01'): 1.0 for i in range(262)}
        rows = [
            {'symbol': f'F{i:03d}', 'ex_date': '2024-02-01', 'corrected_event_ratio': 0.99}
            for i in range(3)
        ]
        out = mod.merge_final_six_overrides(base, rows)
        self.assertEqual(len(out), 265)

    def test_merge_840_checkpoint_overrides_rejects_overlap(self):
        base = {('000001.SZ', '2024-01-01'): 1.0}
        rows = [{'symbol': '000001.SZ', 'ex_date': '2024-01-01', 'corrected_event_ratio': 0.99}]
        with self.assertRaises(ValueError):
            mod.merge_final_six_overrides(base, rows)

    def test_updated_checkpoint_can_close_all_four_without_promoting_formal(self):
        self.assertEqual(
            mod.updated_checkpoint({'PASS': 840, 'EXACT_TERM_REVIEW': 4, 'MISSING_EVENT_REVIEW': 0, 'NOT_APPLICABLE': 3}, 4),
            {'PASS': 844, 'EXACT_TERM_REVIEW': 0, 'MISSING_EVENT_REVIEW': 0, 'NOT_APPLICABLE': 3},
        )

    def test_remaining_scope_is_exactly_four(self):
        rows = [
            {'symbol': '000550.SZ'},
            {'symbol': '000672.SZ'},
            {'symbol': '000989.SZ'},
            {'symbol': '001230.SZ'},
            {'symbol': '001323.SZ'},
        ]
        active, ignored = mod.partition_evidence_scope(
            rows, {'000550.SZ','000672.SZ','000989.SZ','001230.SZ'}
        )
        self.assertEqual({r['symbol'] for r in active}, {'000550.SZ','000672.SZ','000989.SZ','001230.SZ'})
        self.assertEqual([r['symbol'] for r in ignored], ['001323.SZ'])


if __name__ == '__main__':
    unittest.main()
