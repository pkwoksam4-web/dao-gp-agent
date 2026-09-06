import pathlib
import tempfile
import unittest

from global_qfq_nominal_v481 import (
    classify_nominal_symbol,
    eastmoney_report_coverage,
    find_sina_raw,
    sina_formal_event_dates,
)


class NominalClassificationTests(unittest.TestCase):
    def test_nominal_factor_pass_requires_explicit_event_source_success(self):
        r = classify_nominal_symbol(formal_row_n=100,event_count=2,factor_compare_status='PASS',sharebonus_coverage='EXPLICIT_SUCCESS',rights_coverage='EXPLICIT_SUCCESS',sina_formal_event_n=2)
        self.assertEqual(r, 'PASS_NOMINAL_EVENT_FACTOR')

    def test_mismatch_routes_to_exact_corporate_action_review(self):
        r = classify_nominal_symbol(formal_row_n=100,event_count=1,factor_compare_status='FAIL',sharebonus_coverage='EXPLICIT_SUCCESS',rights_coverage='EXPLICIT_SUCCESS',sina_formal_event_n=1)
        self.assertEqual(r, 'REVIEW_REQUIRED_EXACT_CORPORATE_ACTION_TERMS')

    def test_empty_9201_is_not_negative_event_coverage(self):
        r = classify_nominal_symbol(formal_row_n=100,event_count=0,factor_compare_status='PASS',sharebonus_coverage='EMPTY_UNPROVEN',rights_coverage='EMPTY_UNPROVEN',sina_formal_event_n=0)
        self.assertEqual(r, 'UNKNOWN_NEGATIVE_EVENT_COVERAGE')

    def test_explicit_full_history_with_no_events_can_prove_negative_coverage(self):
        r = classify_nominal_symbol(formal_row_n=100,event_count=0,factor_compare_status='PASS',sharebonus_coverage='EXPLICIT_SUCCESS',rights_coverage='EXPLICIT_SUCCESS',sina_formal_event_n=0)
        self.assertEqual(r, 'PASS_PROVEN_NO_FORMAL_ACTIONS')

    def test_sina_event_without_nominal_event_is_missing_event_source_match(self):
        r = classify_nominal_symbol(formal_row_n=100,event_count=0,factor_compare_status=None,sharebonus_coverage='EXPLICIT_SUCCESS',rights_coverage='EXPLICIT_SUCCESS',sina_formal_event_n=1)
        self.assertEqual(r, 'REVIEW_MISSING_EVENT_SOURCE_MATCH')

    def test_no_formal_rows_is_not_factor_failure(self):
        r = classify_nominal_symbol(formal_row_n=0,event_count=0,factor_compare_status=None,sharebonus_coverage='EMPTY_UNPROVEN',rights_coverage='EMPTY_UNPROVEN',sina_formal_event_n=0)
        self.assertEqual(r, 'NOT_APPLICABLE_NO_FORMAL_ROWS')

    def test_any_fetch_failure_blocks_symbol(self):
        r = classify_nominal_symbol(formal_row_n=100,event_count=1,factor_compare_status='PASS',sharebonus_coverage='FAILED',rights_coverage='EXPLICIT_SUCCESS',sina_formal_event_n=1)
        self.assertEqual(r, 'BLOCKED_EVENT_SOURCE')


class CoverageParserTests(unittest.TestCase):
    def test_eastmoney_code0_is_explicit_success_even_when_data_empty(self):
        raw = b'{"success":true,"code":0,"result":{"pages":0,"data":[]}}'
        self.assertEqual(eastmoney_report_coverage(raw), 'EXPLICIT_SUCCESS')

    def test_eastmoney_9201_is_empty_unproven(self):
        raw = b'{"success":false,"code":9201,"message":"no data"}'
        self.assertEqual(eastmoney_report_coverage(raw), 'EMPTY_UNPROVEN')

    def test_malformed_eastmoney_payload_is_failed(self):
        self.assertEqual(eastmoney_report_coverage(b'<html>blocked</html>'), 'FAILED')

    def test_sina_formal_event_dates_are_window_bounded(self):
        rows = [
            {'date':'2026-05-01','factor':1.0},
            {'date':'2025-06-01','factor':1.1},
            {'date':'2020-06-01','factor':1.2},
            {'date':'2020-05-01','factor':1.3},
        ]
        self.assertEqual(sina_formal_event_dates(rows, '2020-06-01', '2026-04-17'), ['2025-06-01'])

    def test_find_sina_raw_under_downloads_raw(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            p=root/'downloads'/'raw'/'000001_SZ_sina_qfq.js'
            p.parent.mkdir(parents=True)
            p.write_bytes(b'test')
            self.assertEqual(find_sina_raw(root,'000001.SZ'), p)

    def test_find_sina_raw_missing_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                find_sina_raw(pathlib.Path(td),'000001.SZ')


if __name__ == '__main__':
    unittest.main()
