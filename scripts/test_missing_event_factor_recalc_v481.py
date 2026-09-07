import unittest

from missing_event_factor_recalc_v481 import (
    canonical_supplemental_profile,
    extract_f10_target_profile,
    extract_supplemental_profile,
    extract_targeted_probe_profile,
    resolve_target_profile,
    classify_missing_event_recalc,
)


class SupplementalProfileTests(unittest.TestCase):
    def test_special_and_cash_profiles_are_canonicalized(self):
        expected={
            ('000564.SZ','2021-12-31'): '10转22.035714',
            ('000981.SZ','2022-02-25'): '10转14.82',
            ('002076.SZ','2022-12-21'): '10转4.58796',
            ('300117.SZ','2020-07-20'): '10派0.03元',
            ('300117.SZ','2021-08-20'): '10派0.13元',
            ('300262.SZ','2020-08-11'): '10派0.13元',
            ('600070.SH','2020-07-10'): '10派0.8元',
            ('600070.SH','2021-07-07'): '10派0.49元',
            ('600190.SH','2020-07-02'): '10派0.2元',
            ('600190.SH','2021-06-25'): '10派0.2元',
            ('600190.SH','2022-06-24'): '10派0.2元',
            ('600190.SH','2024-06-26'): '10派0.2元',
        }
        for (symbol,date),profile in expected.items():
            with self.subTest(symbol=symbol,date=date):
                self.assertEqual(canonical_supplemental_profile(symbol,date), profile)

    def test_unknown_supplemental_profile_fails_closed(self):
        with self.assertRaises(KeyError):
            canonical_supplemental_profile('000001.SZ','2020-01-01')

    def test_positive_supplemental_evidence_unlocks_only_exact_symbol_date(self):
        rows=[{
            'symbol':'000564.SZ','target_date':'2021-12-31',
            'status':'SUPPLEMENTAL_POSITIVE_EVENT_EVIDENCE',
            'target_date_found':True,'expected_term_found':True,
        }]
        self.assertEqual(extract_supplemental_profile('000564.SZ','2021-12-31',rows),'10转22.035714')
        with self.assertRaises(ValueError):
            extract_supplemental_profile('000564.SZ','2021-12-30',rows)

    def test_targeted_probe_requires_closed_exact_profile(self):
        probe={
            'artifact':'MISSING_EVENT_300262_PROBE_V481',
            'symbol':'300262.SZ','target_date':'2020-08-11',
            'profile':'10派0.13元','evidence_closed':True,
        }
        self.assertEqual(extract_targeted_probe_profile('300262.SZ','2020-08-11',probe),'10派0.13元')
        bad=dict(probe, evidence_closed=False)
        with self.assertRaises(ValueError):
            extract_targeted_probe_profile('300262.SZ','2020-08-11',bad)


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

    def test_resolution_prefers_pageajax_then_positive_frozen_fallbacks(self):
        direct={'date':'2025-12-29','status':'F10_PAGEAJAX_TARGET_DATE_HIT','hits':[{'row':{
            'EX_DIVIDEND_DATE':'2025-12-29 00:00:00','ASSIGN_PROGRESS':'实施方案','IMPL_PLAN_PROFILE':'10转10'}}]}
        self.assertEqual(resolve_target_profile('000430.SZ',direct,[],{}),('10转10','F10_PAGEAJAX'))

        partial={'date':'2021-12-31','status':'F10_PAGEAJAX_TARGET_DATE_UNRESOLVED_PARTIAL_WINDOW','hits':[]}
        supplements=[{'symbol':'000564.SZ','target_date':'2021-12-31','status':'SUPPLEMENTAL_POSITIVE_EVENT_EVIDENCE','target_date_found':True,'expected_term_found':True}]
        self.assertEqual(resolve_target_profile('000564.SZ',partial,supplements,{}),('10转22.035714','SUPPLEMENTAL_EXACT_SOURCE'))

        failed={'date':'2020-08-11','status':'F10_PAGEAJAX_FETCH_FAILED','hits':[]}
        probes={('300262.SZ','2020-08-11'):{'artifact':'MISSING_EVENT_300262_PROBE_V481','symbol':'300262.SZ','target_date':'2020-08-11','profile':'10派0.13元','evidence_closed':True}}
        self.assertEqual(resolve_target_profile('300262.SZ',failed,[],probes),('10派0.13元','TARGETED_PAGEAJAX_RETRY'))


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
