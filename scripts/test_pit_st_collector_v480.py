import unittest

from pit_st_collector_v480 import (
    audit_materialized_rows,
    to_baostock_code,
)


class PitStCollectorV480Tests(unittest.TestCase):
    def test_maps_exchange_qualified_symbol(self):
        self.assertEqual(to_baostock_code('002359.SZ'), 'sz.002359')
        self.assertEqual(to_baostock_code('600634.SH'), 'sh.600634')

    def test_rejects_unknown_exchange(self):
        with self.assertRaises(ValueError):
            to_baostock_code('123456.BJ')

    def test_query_failure_is_fail_closed(self):
        audit = audit_materialized_rows(
            '002359.SZ', [], query_error_code='1001', query_error_msg='network error'
        )
        self.assertEqual(audit['status'], 'FAILED_QUERY')
        self.assertFalse(audit['formal_admission'])
        self.assertEqual(audit['not_st_rows'], 0)

    def test_empty_response_is_unknown_not_not_st(self):
        audit = audit_materialized_rows('600634.SH', [], query_error_code='0', query_error_msg='success')
        self.assertEqual(audit['status'], 'UNKNOWN_EMPTY_RESPONSE')
        self.assertFalse(audit['formal_admission'])
        self.assertEqual(audit['not_st_rows'], 0)

    def test_invalid_isst_is_unknown(self):
        rows = [
            {'date': '2020-06-01', 'code': 'sz.002359', 'tradestatus': '1', 'isST': ''},
        ]
        audit = audit_materialized_rows('002359.SZ', rows, query_error_code='0', query_error_msg='success')
        self.assertEqual(audit['status'], 'UNKNOWN_INVALID_RESPONSE')
        self.assertFalse(audit['formal_admission'])

    def test_valid_rows_preserve_st_state_and_emit_transitions(self):
        rows = [
            {'date': '2020-06-01', 'code': 'sz.002359', 'tradestatus': '1', 'isST': '0'},
            {'date': '2020-06-02', 'code': 'sz.002359', 'tradestatus': '1', 'isST': '1'},
            {'date': '2020-06-03', 'code': 'sz.002359', 'tradestatus': '0', 'isST': '1'},
        ]
        audit = audit_materialized_rows('002359.SZ', rows, query_error_code='0', query_error_msg='success')
        self.assertEqual(audit['status'], 'MATERIALIZED_CANDIDATE_AUDIT_PENDING')
        self.assertEqual(audit['st_rows'], 2)
        self.assertEqual(audit['not_st_rows'], 1)
        self.assertEqual(audit['transition_count'], 1)
        self.assertEqual(audit['transitions'][0]['to_isST'], '1')
        self.assertFalse(audit['formal_admission'])


if __name__ == '__main__':
    unittest.main()
