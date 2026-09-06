import unittest

from global_event_ledger_v481 import validate_ledger_pages


def page(report, page_number, pages, count, rows, success=True, code=0):
    return {
        'report': report,
        'page_number': page_number,
        'payload': {
            'success': success,
            'code': code,
            'result': {'pages': pages, 'count': count, 'data': rows},
        },
    }


class LedgerValidationTests(unittest.TestCase):
    def test_complete_pages_close_explicit_coverage(self):
        docs = [
            page('RPT_IPO_ALLOTMENT', 1, 2, 3, [
                {'SECURITY_CODE':'000001','EX_DIVIDEND_DATE':'2024-01-02 00:00:00'},
                {'SECURITY_CODE':'000002','EX_DIVIDEND_DATE':'2023-01-03 00:00:00'},
            ]),
            page('RPT_IPO_ALLOTMENT', 2, 2, 3, [
                {'SECURITY_CODE':'000003','EX_DIVIDEND_DATE':'2022-01-04 00:00:00'},
            ]),
        ]
        out = validate_ledger_pages(docs, 'RPT_IPO_ALLOTMENT', '2020-06-01', '2026-04-17')
        self.assertEqual(out['status'], 'GLOBAL_LEDGER_EXPLICIT_SUCCESS')
        self.assertEqual(out['row_count'], 3)
        self.assertEqual(out['page_count'], 2)

    def test_missing_page_fails_closed(self):
        docs = [page('RPT_SHAREBONUS_DET', 1, 2, 1, [{'SECURITY_CODE':'000001','EX_DIVIDEND_DATE':'2024-01-02'}])]
        with self.assertRaises(ValueError):
            validate_ledger_pages(docs, 'RPT_SHAREBONUS_DET', '2020-06-01', '2026-04-17')

    def test_inconsistent_count_fails_closed(self):
        docs = [
            page('RPT_SHAREBONUS_DET', 1, 2, 3, [{'SECURITY_CODE':'000001','EX_DIVIDEND_DATE':'2024-01-02'}]),
            page('RPT_SHAREBONUS_DET', 2, 2, 4, [{'SECURITY_CODE':'000002','EX_DIVIDEND_DATE':'2024-01-03'}]),
        ]
        with self.assertRaises(ValueError):
            validate_ledger_pages(docs, 'RPT_SHAREBONUS_DET', '2020-06-01', '2026-04-17')

    def test_row_count_must_equal_api_count(self):
        docs = [page('RPT_IPO_ALLOTMENT', 1, 1, 2, [{'SECURITY_CODE':'000001','EX_DIVIDEND_DATE':'2024-01-02'}])]
        with self.assertRaises(ValueError):
            validate_ledger_pages(docs, 'RPT_IPO_ALLOTMENT', '2020-06-01', '2026-04-17')

    def test_out_of_window_row_fails_filtered_ledger(self):
        docs = [page('RPT_IPO_ALLOTMENT', 1, 1, 1, [{'SECURITY_CODE':'000001','EX_DIVIDEND_DATE':'2026-04-18'}])]
        with self.assertRaises(ValueError):
            validate_ledger_pages(docs, 'RPT_IPO_ALLOTMENT', '2020-06-01', '2026-04-17')

    def test_non_success_page_fails_closed(self):
        docs = [page('RPT_IPO_ALLOTMENT', 1, 1, 0, [], success=False, code=9201)]
        with self.assertRaises(ValueError):
            validate_ledger_pages(docs, 'RPT_IPO_ALLOTMENT', '2020-06-01', '2026-04-17')


if __name__ == '__main__':
    unittest.main()
