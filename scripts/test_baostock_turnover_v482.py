from __future__ import annotations

import importlib
import unittest


def _subject():
    try:
        return importlib.import_module('baostock_turnover_v482')
    except ModuleNotFoundError as exc:
        raise AssertionError('baostock_turnover_v482 production module is missing') from exc


class FakeResult:
    def __init__(self, fields, rows, error_code='0', error_msg='success'):
        self.fields = list(fields)
        self._rows = list(rows)
        self._i = -1
        self.error_code = error_code
        self.error_msg = error_msg

    def next(self):
        self._i += 1
        return self._i < len(self._rows)

    def get_row_data(self):
        return self._rows[self._i]


class FakeBaoStock:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def query_history_k_data_plus(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


class BaoStockTurnoverV482Contracts(unittest.TestCase):
    def test_query_uses_same_daily_unadjusted_pit_source_with_turn_added(self):
        m = _subject()
        fields = ['date', 'code', 'turn', 'tradestatus', 'isST']
        fake = FakeBaoStock(FakeResult(fields, [
            ['2020-06-01', 'sz.002359', '3.82', '1', '0'],
        ]))
        rows, ec, em = m.query_rows(fake, '002359.SZ')
        self.assertEqual(ec, '0')
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(fake.calls), 1)
        args, kwargs = fake.calls[0]
        self.assertEqual(args[0], 'sz.002359')
        self.assertEqual(args[1], 'date,code,turn,tradestatus,isST')
        self.assertEqual(kwargs['start_date'], '2020-06-01')
        self.assertEqual(kwargs['end_date'], '2026-04-17')
        self.assertEqual(kwargs['frequency'], 'd')
        self.assertEqual(kwargs['adjustflag'], '3')

    def test_trade_row_turn_percent_converts_to_ratio_and_keeps_provenance(self):
        m = _subject()
        out = m.audit_and_extract('002359.SZ', [
            {'date':'2020-06-12','code':'sz.002359','turn':'3.82','tradestatus':'1','isST':'0'},
        ])
        self.assertEqual(out['status'], 'PASS_TURNOVER_ROWS')
        self.assertEqual(out['trade_rows'], 1)
        self.assertEqual(out['nontrade_rows'], 0)
        self.assertEqual(out['turnover_rows'][0]['date'], '2020-06-12')
        self.assertAlmostEqual(out['turnover_rows'][0]['turnover_ratio'], 0.0382, places=12)
        self.assertEqual(out['turnover_rows'][0]['source'], 'BAOSTOCK_QUERY_HISTORY_K_DATA_PLUS_TURN_V482')

    def test_nontrade_row_may_have_blank_turn_but_is_excluded(self):
        m = _subject()
        out = m.audit_and_extract('002359.SZ', [
            {'date':'2020-06-12','code':'sz.002359','turn':'','tradestatus':'0','isST':'0'},
        ])
        self.assertEqual(out['status'], 'PASS_TURNOVER_ROWS')
        self.assertEqual(out['trade_rows'], 0)
        self.assertEqual(out['nontrade_rows'], 1)
        self.assertEqual(out['turnover_rows'], [])

    def test_trade_row_blank_negative_or_nonfinite_turn_fails_closed(self):
        m = _subject()
        bad_values = ['', '-0.01', 'nan', 'inf']
        for bad in bad_values:
            with self.subTest(turn=bad):
                out = m.audit_and_extract('002359.SZ', [
                    {'date':'2020-06-12','code':'sz.002359','turn':bad,'tradestatus':'1','isST':'0'},
                ])
                self.assertEqual(out['status'], 'REVIEW_BAD_TURNOVER')
                self.assertEqual(out['bad_turnover_n'], 1)
                self.assertEqual(out['turnover_rows'], [])

    def test_query_failure_is_not_interpreted_as_empty_turnover(self):
        m = _subject()
        out = m.audit_and_extract('600634.SH', [], query_error_code='1001', query_error_msg='network')
        self.assertEqual(out['status'], 'FAILED_QUERY')
        self.assertFalse(out['turnover_pit_verified'])

    def test_duplicate_trade_date_or_wrong_code_fails_closed(self):
        m = _subject()
        duplicate = [
            {'date':'2020-06-12','code':'sz.002359','turn':'3.82','tradestatus':'1','isST':'0'},
            {'date':'2020-06-12','code':'sz.002359','turn':'3.82','tradestatus':'1','isST':'0'},
        ]
        self.assertEqual(m.audit_and_extract('002359.SZ', duplicate)['status'], 'REVIEW_DUPLICATE_DATE')
        wrong = [
            {'date':'2020-06-12','code':'sh.600634','turn':'3.82','tradestatus':'1','isST':'0'},
        ]
        self.assertEqual(m.audit_and_extract('002359.SZ', wrong)['status'], 'REVIEW_INVALID_RESPONSE')

    def test_v482_false_zero_corrections_are_exact_and_not_broadened(self):
        m = _subject()
        expected = {
            ('002087.SZ','2024-06-13'),
            ('300356.SZ','2023-06-20'),
            ('600647.SH','2024-06-13'),
            ('600766.SH','2024-06-13'),
            ('603133.SH','2024-06-13'),
        }
        self.assertEqual(set(m.PITST_TRADESTATUS_ONE_CORRECTIONS), expected)
        rows = [
            {'date':'2024-06-12','code':'sz.002087','turn':'1.000000','tradestatus':'0','isST':'0'},
            {'date':'2024-06-13','code':'sz.002087','turn':'1.100000','tradestatus':'0','isST':'0'},
            {'date':'2024-06-14','code':'sz.002087','turn':'1.200000','tradestatus':'0','isST':'0'},
        ]
        corrected, applied = m.apply_trade_status_corrections('002087.SZ', rows)
        self.assertEqual(applied, [('002087.SZ','2024-06-13')])
        self.assertEqual([r['tradestatus'] for r in corrected], ['0','1','0'])
        self.assertEqual([r['tradestatus'] for r in rows], ['0','0','0'])

    def test_exact_global_gate_uses_formal_trade_rows_and_844_symbols(self):
        m = _subject()
        self.assertTrue(m.full_turnover_global_gate(
            scope_n=847,
            turnover_symbol_n=844,
            turnover_rows=1_011_607,
            missing_n=0,
            extra_n=0,
            duplicate_n=0,
            bad_turnover_n=0,
            unresolved_symbol_n=0,
        ))
        self.assertFalse(m.full_turnover_global_gate(
            scope_n=847,
            turnover_symbol_n=844,
            turnover_rows=1_011_606,
            missing_n=1,
            extra_n=0,
            duplicate_n=0,
            bad_turnover_n=0,
            unresolved_symbol_n=0,
        ))


if __name__ == '__main__':
    unittest.main()
