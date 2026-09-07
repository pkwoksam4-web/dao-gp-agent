import unittest

from missing_event_factor_recalc_v481 import (
    canonical_supplemental_profile,
    extract_f10_target_profile,
    classify_missing_event_recalc,
)


class SupplementalProfileTests(unittest.TestCase):
    def test_special_and_cash_profiles_are_canonicalized(self):
        self.assertEqual(canonical_supplemental_profile('000564.SZ','2021-12-31'), '10转22.035714')
        self.assertEqual(canonical_supplemental_profile('000981.SZ','2022-02-25'), '10转14.82')
        self.assertEqual(canonical_supplemental_profile('002076.SZ','2022-12-21'), '10转4.58796')
        self.assertEqual(canonical_supplemental_profile('300117.SZ','2020-07-20'), '10派0.03元')
        self.assertEqual(canonical_supplemental_profile('300262.SZ','2020-08-11'), '10派0.13元')
        self.assertEqual(canonical_supplemental_profile('600070.SH','2020-07-10'), '10派0.8元')
        self.assertEqual(canonical_supplemental_profile('600190.SH','2020-07-02'), '10派0.2元')

    def test_unknown_supplemental_profile_fails_closed(self):
        with self.assertRaises(KeyError):
            canonical_supplemental_profile('000001.SZ','2020-01-01')


class F10ExtractionTests(unittest.TestCase):
    def test_extracts_exact_target_implemented_profile(self):
        target={
            'date':'2025-12-29',
            'status':'F10_PAGEAJAX_TARGET_DATE_HIT',
            'hits':[{'collection':'fhyx','row':{
                'EX_DIVIDEND_DATE':'2025-12-29 00:00:00',
                'ASSIGN_PROGRESS':'实施方案',
                'IMPL_PLAN_PROFILE':'10转10',
            }}],
        }
        self.assertEqual(extract_f10_target_profile(target),'10转10')

    def test_duplicate_conflicting_profiles_fail_closed(self):
        target={'date':'2024-01-02','status':'F10_PAGEAJAX_TARGET_DATE_HIT','hits':[
            {'collection':'fhyx','row':{'EX_DIVIDEND_DATE':'2024-01-02 00:00:00','ASSIGN_PROGRESS':'实施方案','IMPL_PLAN_PROFILE':'10派1元'}},
            {'collection':'other','row':{'EX_DIVIDEND_DATE':'2024-01-02 00:00:00','ASSIGN_PROGRESS':'实施方案','IMPL_PLAN_PROFILE':'10派2元'}},
        ]}
        with self.assertRaises(ValueError):
            extract_f10_target_profile(target)

    def test_non_implemented_or_wrong_date_fails_closed(self):
        for target in (
            {'date':'2024-01-02','status':'F10_PAGEAJAX_TARGET_DATE_HIT','hits':[{'row':{'EX_DIVIDEND_DATE':'2024-01-02 00:00:00','ASSIGN_PROGRESS':'预案','IMPL_PLAN_PROFILE':'10派1元'}}]},
            {'date':'2024-01-02','status':'F10_PAGEAJAX_TARGET_DATE_HIT','hits':[{'row':{'EX_DIVIDEND_DATE':'2024-01-03 00:00:00','ASSIGN_PROGRESS':'实施方案','IMPL_PLAN_PROFILE':'10派1元'}}]},
        ):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    extract_f10_target_profile(target)


class ClassificationTests(unittest.TestCase):
    def test_pass_and_review_classification(self):
        self.assertEqual(classify_missing_event_recalc(True, 'PASS'), 'PASS_MISSING_EVENT_RESOLVED_NOMINAL_FACTOR')
        self.assertEqual(classify_missing_event_recalc(True, 'FAIL'), 'REVIEW_EXACT_TERMS_AFTER_MISSING_EVENT')

    def test_incomplete_event_coverage_never_passes(self):
        self.assertEqual(classify_missing_event_recalc(False, 'PASS'), 'BLOCKED_MISSING_EVENT_COVERAGE')
        self.assertEqual(classify_missing_event_recalc(False, 'FAIL'), 'BLOCKED_MISSING_EVENT_COVERAGE')

    def test_missing_comparison_fails_closed(self):
        self.assertEqual(classify_missing_event_recalc(True, None), 'BLOCKED_MISSING_EVENT_FACTOR_COMPARISON')


if __name__=='__main__':
    unittest.main()
