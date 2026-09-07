import unittest

import final_six_closure_v482 as mod


class FinalSixClosureV482Tests(unittest.TestCase):
    def test_merge_prior_recovered_overrides_builds_262_base(self):
        base = {(f'S{i:03d}', '2024-01-01'): 1.0 for i in range(208)}
        prior_rows = [
            {'symbol': f'R{i:03d}', 'ex_date': '2024-02-01', 'corrected_event_ratio': 0.99}
            for i in range(54)
        ]
        out = mod.merge_prior_recovered_overrides(base, prior_rows)
        self.assertEqual(len(out), 262)

    def test_merge_prior_recovered_overrides_rejects_overlap(self):
        base = {('000001.SZ', '2024-01-01'): 1.0}
        prior_rows = [{'symbol': '000001.SZ', 'ex_date': '2024-01-01', 'corrected_event_ratio': 0.99}]
        with self.assertRaises(ValueError):
            mod.merge_prior_recovered_overrides(base, prior_rows)

    def test_updated_checkpoint_moves_only_exact_review_to_pass(self):
        self.assertEqual(
            mod.updated_checkpoint({'PASS': 838, 'EXACT_TERM_REVIEW': 6, 'MISSING_EVENT_REVIEW': 0, 'NOT_APPLICABLE': 3}, 2),
            {'PASS': 840, 'EXACT_TERM_REVIEW': 4, 'MISSING_EVENT_REVIEW': 0, 'NOT_APPLICABLE': 3},
        )

    def test_classify_evidence_scope_ignores_already_closed_symbol(self):
        remaining = {'000709.SZ', '001323.SZ'}
        rows = [
            {'symbol': '000709.SZ', 'ex_date': '2024-07-11'},
            {'symbol': '002014.SZ', 'ex_date': '2025-09-30'},
        ]
        active, ignored = mod.partition_evidence_scope(rows, remaining)
        self.assertEqual([(r['symbol'], r['ex_date']) for r in active], [('000709.SZ', '2024-07-11')])
        self.assertEqual([(r['symbol'], r['ex_date']) for r in ignored], [('002014.SZ', '2025-09-30')])


if __name__ == '__main__':
    unittest.main()
