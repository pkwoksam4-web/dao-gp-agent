import unittest

from global_qfq_nominal_v481 import classify_nominal_symbol


class NominalClassificationTests(unittest.TestCase):
    def test_nominal_factor_pass_requires_explicit_event_source_success(self):
        r = classify_nominal_symbol(
            formal_row_n=100,
            event_count=2,
            factor_compare_status='PASS',
            sharebonus_coverage='EXPLICIT_SUCCESS',
            rights_coverage='EXPLICIT_SUCCESS',
            sina_formal_event_n=2,
        )
        self.assertEqual(r, 'PASS_NOMINAL_EVENT_FACTOR')

    def test_mismatch_routes_to_exact_corporate_action_review(self):
        r = classify_nominal_symbol(
            formal_row_n=100,
            event_count=1,
            factor_compare_status='FAIL',
            sharebonus_coverage='EXPLICIT_SUCCESS',
            rights_coverage='EXPLICIT_SUCCESS',
            sina_formal_event_n=1,
        )
        self.assertEqual(r, 'REVIEW_REQUIRED_EXACT_CORPORATE_ACTION_TERMS')

    def test_empty_9201_is_not_negative_event_coverage(self):
        r = classify_nominal_symbol(
            formal_row_n=100,
            event_count=0,
            factor_compare_status='PASS',
            sharebonus_coverage='EMPTY_UNPROVEN',
            rights_coverage='EMPTY_UNPROVEN',
            sina_formal_event_n=0,
        )
        self.assertEqual(r, 'UNKNOWN_NEGATIVE_EVENT_COVERAGE')

    def test_explicit_full_history_with_no_events_can_prove_negative_coverage(self):
        r = classify_nominal_symbol(
            formal_row_n=100,
            event_count=0,
            factor_compare_status='PASS',
            sharebonus_coverage='EXPLICIT_SUCCESS',
            rights_coverage='EXPLICIT_SUCCESS',
            sina_formal_event_n=0,
        )
        self.assertEqual(r, 'PASS_PROVEN_NO_FORMAL_ACTIONS')

    def test_sina_event_without_nominal_event_is_missing_event_source_match(self):
        r = classify_nominal_symbol(
            formal_row_n=100,
            event_count=0,
            factor_compare_status=None,
            sharebonus_coverage='EXPLICIT_SUCCESS',
            rights_coverage='EXPLICIT_SUCCESS',
            sina_formal_event_n=1,
        )
        self.assertEqual(r, 'REVIEW_MISSING_EVENT_SOURCE_MATCH')

    def test_no_formal_rows_is_not_factor_failure(self):
        r = classify_nominal_symbol(
            formal_row_n=0,
            event_count=0,
            factor_compare_status=None,
            sharebonus_coverage='EMPTY_UNPROVEN',
            rights_coverage='EMPTY_UNPROVEN',
            sina_formal_event_n=0,
        )
        self.assertEqual(r, 'NOT_APPLICABLE_NO_FORMAL_ROWS')

    def test_any_fetch_failure_blocks_symbol(self):
        r = classify_nominal_symbol(
            formal_row_n=100,
            event_count=1,
            factor_compare_status='PASS',
            sharebonus_coverage='FAILED',
            rights_coverage='EXPLICIT_SUCCESS',
            sina_formal_event_n=1,
        )
        self.assertEqual(r, 'BLOCKED_EVENT_SOURCE')


if __name__ == '__main__':
    unittest.main()
