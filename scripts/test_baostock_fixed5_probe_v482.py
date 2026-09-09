import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name('baostock_fixed5_probe_v482.py')
EXPECTED_SYMBOLS = (
    '000001.SZ',
    '000014.SZ',
    '001201.SZ',
    '002001.SZ',
    '002002.SZ',
)
EXPECTED_FIELDS = (
    'date', 'code', 'open', 'high', 'low', 'close', 'preclose',
    'volume', 'amount', 'adjustflag', 'turn', 'tradestatus', 'pctChg', 'isST',
)


def load_probe_module(testcase: unittest.TestCase):
    testcase.assertTrue(
        MODULE_PATH.exists(),
        'baostock_fixed5_probe_v482.py must exist before the fixed-five contract can pass',
    )
    spec = importlib.util.spec_from_file_location('baostock_fixed5_probe_v482', MODULE_PATH)
    testcase.assertIsNotNone(spec)
    testcase.assertIsNotNone(spec.loader)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BaoStockFixed5ProbeV482Tests(unittest.TestCase):
    def test_fixed_five_are_frozen_from_v373(self):
        mod = load_probe_module(self)
        self.assertEqual(tuple(mod.FIXED5_SYMBOLS), EXPECTED_SYMBOLS)
        self.assertEqual(mod.FORMAL_START, '2020-06-01')
        self.assertEqual(mod.FORMAL_END, '2026-04-17')

    def test_query_contract_is_unadjusted_raw_plus_pit_st_fields(self):
        mod = load_probe_module(self)
        self.assertEqual(tuple(mod.FIELDS), EXPECTED_FIELDS)
        self.assertEqual(mod.ADJUSTFLAG, '3')

    def test_query_failure_fails_closed(self):
        mod = load_probe_module(self)
        got = mod.audit_probe_rows(
            '000001.SZ', [], query_error_code='1001', query_error_msg='network error'
        )
        self.assertEqual(got['status'], 'FAILED_QUERY')
        self.assertFalse(got['formal_admission'])
        self.assertFalse(got['oos_metrics_allowed'])

    def test_empty_response_is_unknown(self):
        mod = load_probe_module(self)
        got = mod.audit_probe_rows('000014.SZ', [], query_error_code='0', query_error_msg='success')
        self.assertEqual(got['status'], 'UNKNOWN_EMPTY_RESPONSE')
        self.assertFalse(got['formal_admission'])

    def test_valid_traded_raw_row_passes_probe_only(self):
        mod = load_probe_module(self)
        rows = [{
            'date': '2026-04-17', 'code': 'sz.001201',
            'open': '10.00', 'high': '10.50', 'low': '9.90', 'close': '10.20',
            'preclose': '9.95', 'volume': '123400', 'amount': '1250000.5',
            'adjustflag': '3', 'turn': '1.20', 'tradestatus': '1',
            'pctChg': '2.5126', 'isST': '0',
        }]
        got = mod.audit_probe_rows('001201.SZ', rows)
        self.assertEqual(got['status'], 'PASS_PROBE_CANDIDATE')
        self.assertEqual(got['raw_traded_rows'], 1)
        self.assertEqual(got['suspended_rows'], 0)
        self.assertEqual(got['first_date'], '2026-04-17')
        self.assertEqual(got['last_date'], '2026-04-17')
        self.assertFalse(got['formal_admission'])
        self.assertFalse(got['oos_metrics_allowed'])

    def test_suspension_row_may_have_empty_price_fields_but_is_not_raw_bar(self):
        mod = load_probe_module(self)
        rows = [{
            'date': '2020-06-01', 'code': 'sz.002001',
            'open': '', 'high': '', 'low': '', 'close': '', 'preclose': '',
            'volume': '', 'amount': '', 'adjustflag': '3', 'turn': '',
            'tradestatus': '0', 'pctChg': '', 'isST': '0',
        }]
        got = mod.audit_probe_rows('002001.SZ', rows)
        self.assertEqual(got['status'], 'PASS_PROBE_CANDIDATE')
        self.assertEqual(got['raw_traded_rows'], 0)
        self.assertEqual(got['suspended_rows'], 1)

    def test_traded_row_missing_amount_is_invalid(self):
        mod = load_probe_module(self)
        rows = [{
            'date': '2020-06-01', 'code': 'sz.002002',
            'open': '1', 'high': '1.1', 'low': '0.9', 'close': '1', 'preclose': '1',
            'volume': '1000', 'amount': '', 'adjustflag': '3', 'turn': '1',
            'tradestatus': '1', 'pctChg': '0', 'isST': '1',
        }]
        got = mod.audit_probe_rows('002002.SZ', rows)
        self.assertEqual(got['status'], 'UNKNOWN_INVALID_RESPONSE')
        self.assertIn('amount', got['validation_error'])
        self.assertFalse(got['formal_admission'])

    def test_duplicate_date_is_invalid(self):
        mod = load_probe_module(self)
        row = {
            'date': '2020-06-01', 'code': 'sz.000001',
            'open': '1', 'high': '1.1', 'low': '0.9', 'close': '1', 'preclose': '1',
            'volume': '1000', 'amount': '1000', 'adjustflag': '3', 'turn': '1',
            'tradestatus': '1', 'pctChg': '0', 'isST': '0',
        }
        got = mod.audit_probe_rows('000001.SZ', [row, dict(row)])
        self.assertEqual(got['status'], 'UNKNOWN_INVALID_RESPONSE')
        self.assertIn('duplicate date', got['validation_error'])


if __name__ == '__main__':
    unittest.main()
