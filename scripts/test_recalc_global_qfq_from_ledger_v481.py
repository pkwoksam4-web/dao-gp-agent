import unittest

from recalc_global_qfq_from_ledger_v481 import classify_result, rows_by_security_code


class LedgerRecalcClassificationTests(unittest.TestCase):
    def test_pass_with_actions(self):
        self.assertEqual(
            classify_result(100, 2, 'PASS', ['2024-01-02','2025-01-03'], ['2024-01-02','2025-01-03']),
            'PASS_GLOBAL_LEDGER_NOMINAL_FACTOR',
        )

    def test_pass_with_proven_zero_actions(self):
        self.assertEqual(
            classify_result(100, 0, 'PASS', [], []),
            'PASS_GLOBAL_LEDGER_PROVEN_NO_ACTION',
        )

    def test_fail_with_missing_sina_event_routes_to_missing_event_review(self):
        self.assertEqual(
            classify_result(100, 1, 'FAIL', ['2024-01-02','2025-01-03'], ['2024-01-02']),
            'REVIEW_GLOBAL_LEDGER_MISSING_EVENT_MATCH',
        )

    def test_fail_with_same_event_dates_routes_to_exact_terms(self):
        self.assertEqual(
            classify_result(100, 2, 'FAIL', ['2024-01-02','2025-01-03'], ['2024-01-02','2025-01-03']),
            'REVIEW_GLOBAL_LEDGER_EXACT_TERMS',
        )

    def test_no_formal_rows_is_not_failure(self):
        self.assertEqual(
            classify_result(0, 0, None, [], []),
            'NOT_APPLICABLE_NO_FORMAL_ROWS',
        )

    def test_missing_comparison_fails_closed(self):
        self.assertEqual(
            classify_result(100, 1, None, ['2024-01-02'], ['2024-01-02']),
            'REVIEW_GLOBAL_LEDGER_FACTOR_COMPARISON',
        )


class LedgerGroupingTests(unittest.TestCase):
    def test_duplicate_same_date_rows_are_preserved_for_merge_actions(self):
        rows=[
            {'SECURITY_CODE':'600720','EX_DIVIDEND_DATE':'2024-06-13','PRETAX_BONUS_RMB':2.57},
            {'SECURITY_CODE':'600720','EX_DIVIDEND_DATE':'2024-06-13','PRETAX_BONUS_RMB':1.104},
            {'SECURITY_CODE':'000001','EX_DIVIDEND_DATE':'2024-06-14','PRETAX_BONUS_RMB':1.0},
        ]
        out=rows_by_security_code(rows)
        self.assertEqual(len(out['600720']),2)
        self.assertEqual(len(out['000001']),1)


if __name__=='__main__':
    unittest.main()
