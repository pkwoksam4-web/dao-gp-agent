from __future__ import annotations

import importlib
import unittest

import pandas as pd


def _subject():
    try:
        return importlib.import_module('baostock_turnover_full_v482')
    except ModuleNotFoundError as exc:
        raise AssertionError('baostock_turnover_full_v482 production module is missing') from exc


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
    def __init__(self, rows, error_code='0', error_msg='success'):
        self.rows = list(rows)
        self.error_code = error_code
        self.error_msg = error_msg
        self.calls = []

    def query_history_k_data_plus(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return FakeResult(
            ['date','code','turn','tradestatus','isST'],
            self.rows,
            self.error_code,
            self.error_msg,
        )


class BaoStockTurnoverFullV482Contracts(unittest.TestCase):
    def test_shard_selection_is_deterministic_and_complete(self):
        m = _subject()
        symbols = [f'{i:06d}.SZ' for i in range(19)]
        shards = [m.select_shard(symbols, i, 4) for i in range(4)]
        flat = [s for shard in shards for s in shard]
        self.assertEqual(sorted(flat), sorted(symbols))
        self.assertEqual(len(flat), len(set(flat)))
        self.assertEqual(shards[0], symbols[0::4])

    def test_expected_trade_dates_apply_only_frozen_false_zero_correction(self):
        m = _subject()
        pitst = pd.DataFrame([
            {'symbol':'002087.SZ','date':'2024-06-12','tradestatus':0},
            {'symbol':'002087.SZ','date':'2024-06-13','tradestatus':0},
            {'symbol':'002087.SZ','date':'2024-06-14','tradestatus':0},
            {'symbol':'000001.SZ','date':'2024-06-13','tradestatus':1},
        ])
        self.assertEqual(m.expected_trade_dates(pitst, '002087.SZ'), ['2024-06-13'])
        self.assertEqual(m.expected_trade_dates(pitst, '000001.SZ'), ['2024-06-13'])
        self.assertEqual(pitst.loc[pitst.symbol=='002087.SZ','tradestatus'].tolist(), [0,0,0])

    def test_exact_date_audit_passes_only_once_per_expected_trade_date(self):
        m = _subject()
        expected = ['2024-01-02','2024-01-03']
        rows = [
            {'symbol':'000001.SZ','date':'2024-01-02','turnover_ratio':0.01},
            {'symbol':'000001.SZ','date':'2024-01-03','turnover_ratio':0.02},
        ]
        ok = m.audit_exact_dates('000001.SZ', expected, rows)
        self.assertEqual(ok['status'], 'PASS_EXACT_TURNOVER_DATES')
        self.assertEqual(ok['missing_dates_n'], 0)
        self.assertEqual(ok['extra_dates_n'], 0)
        self.assertEqual(ok['duplicate_dates_n'], 0)
        self.assertEqual(ok['bad_turnover_n'], 0)

        missing = m.audit_exact_dates('000001.SZ', expected, rows[:1])
        self.assertEqual(missing['status'], 'REVIEW_TURNOVER_DATES')
        self.assertEqual(missing['missing_dates'], ['2024-01-03'])

        duplicate = m.audit_exact_dates('000001.SZ', expected, rows + [dict(rows[1])])
        self.assertEqual(duplicate['status'], 'REVIEW_TURNOVER_DATES')
        self.assertEqual(duplicate['duplicate_dates_n'], 1)

    def test_exact_date_audit_rejects_wrong_symbol_or_bad_turnover(self):
        m = _subject()
        wrong = [{'symbol':'000002.SZ','date':'2024-01-02','turnover_ratio':0.01}]
        out = m.audit_exact_dates('000001.SZ', ['2024-01-02'], wrong)
        self.assertEqual(out['status'], 'REVIEW_BAD_TURNOVER')
        self.assertEqual(out['bad_turnover_n'], 1)

        bad = [{'symbol':'000001.SZ','date':'2024-01-02','turnover_ratio':float('nan')}]
        out = m.audit_exact_dates('000001.SZ', ['2024-01-02'], bad)
        self.assertEqual(out['status'], 'REVIEW_BAD_TURNOVER')
        self.assertEqual(out['bad_turnover_n'], 1)

    def test_collect_symbol_passes_normal_trade_rows_against_pitst_dates(self):
        m = _subject()
        pitst = pd.DataFrame([
            {'symbol':'000001.SZ','date':'2020-06-01','tradestatus':1},
            {'symbol':'000001.SZ','date':'2020-06-02','tradestatus':1},
        ])
        fake = FakeBaoStock([
            ['2020-06-01','sz.000001','1.250000','1','0'],
            ['2020-06-02','sz.000001','1.500000','1','0'],
        ])
        rows, audit = m.collect_symbol(fake, pitst, '000001.SZ')
        self.assertEqual(audit['status'], 'PASS_EXACT_TURNOVER_DATES')
        self.assertEqual(audit['applied_trade_status_corrections'], [])
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[0]['turnover_ratio'], 0.0125, places=12)

    def test_collect_symbol_applies_only_exact_false_zero_correction_before_extract(self):
        m = _subject()
        pitst = pd.DataFrame([
            {'symbol':'002087.SZ','date':'2024-06-12','tradestatus':0},
            {'symbol':'002087.SZ','date':'2024-06-13','tradestatus':0},
            {'symbol':'002087.SZ','date':'2024-06-14','tradestatus':0},
        ])
        fake = FakeBaoStock([
            ['2024-06-12','sz.002087','1.000000','0','0'],
            ['2024-06-13','sz.002087','1.100000','0','0'],
            ['2024-06-14','sz.002087','1.200000','0','0'],
        ])
        rows, audit = m.collect_symbol(fake, pitst, '002087.SZ')
        self.assertEqual(audit['status'], 'PASS_EXACT_TURNOVER_DATES')
        self.assertEqual(audit['applied_trade_status_corrections'], [['002087.SZ','2024-06-13']])
        self.assertEqual([r['date'] for r in rows], ['2024-06-13'])

    def test_collect_symbol_zero_trade_symbol_passes_only_when_expected_and_actual_empty(self):
        m = _subject()
        pitst = pd.DataFrame([
            {'symbol':'600074.SH','date':'2020-06-01','tradestatus':0},
        ])
        fake = FakeBaoStock([
            ['2020-06-01','sh.600074','','0','0'],
        ])
        rows, audit = m.collect_symbol(fake, pitst, '600074.SH')
        self.assertEqual(rows, [])
        self.assertEqual(audit['status'], 'PASS_ZERO_TRADE_SYMBOL')
        self.assertEqual(audit['expected_trade_rows'], 0)

    def test_collect_symbol_correction_with_blank_turn_fails_closed(self):
        m = _subject()
        pitst = pd.DataFrame([
            {'symbol':'002087.SZ','date':'2024-06-13','tradestatus':0},
        ])
        fake = FakeBaoStock([
            ['2024-06-13','sz.002087','','0','0'],
        ])
        rows, audit = m.collect_symbol(fake, pitst, '002087.SZ')
        self.assertEqual(rows, [])
        self.assertEqual(audit['status'], 'REVIEW_BAD_TURNOVER')
        self.assertEqual(audit['bad_turnover_n'], 1)

    def test_collect_symbol_query_failure_is_unresolved_not_empty(self):
        m = _subject()
        pitst = pd.DataFrame([
            {'symbol':'000001.SZ','date':'2020-06-01','tradestatus':1},
        ])
        fake = FakeBaoStock([], error_code='1001', error_msg='network')
        rows, audit = m.collect_symbol(fake, pitst, '000001.SZ')
        self.assertEqual(rows, [])
        self.assertEqual(audit['status'], 'FAILED_QUERY')
        self.assertEqual(audit['unresolved_symbol'], True)

    def test_zero_trade_symbols_are_exact(self):
        m = _subject()
        self.assertEqual(
            set(m.ZERO_TRADE_SYMBOLS),
            {'600074.SH','600485.SH','600677.SH'},
        )

    def test_full_gate_requires_frozen_global_counts_and_zero_errors(self):
        m = _subject()
        self.assertTrue(m.full_global_gate(
            scope_n=847,
            turnover_symbol_n=844,
            turnover_rows=1_011_607,
            missing_n=0,
            extra_n=0,
            duplicate_n=0,
            bad_turnover_n=0,
            unresolved_symbol_n=0,
            zero_trade_symbols={'600074.SH','600485.SH','600677.SH'},
        ))
        self.assertFalse(m.full_global_gate(
            scope_n=847,
            turnover_symbol_n=844,
            turnover_rows=1_011_606,
            missing_n=1,
            extra_n=0,
            duplicate_n=0,
            bad_turnover_n=0,
            unresolved_symbol_n=0,
            zero_trade_symbols={'600074.SH','600485.SH','600677.SH'},
        ))
        self.assertFalse(m.full_global_gate(
            scope_n=847,
            turnover_symbol_n=844,
            turnover_rows=1_011_607,
            missing_n=0,
            extra_n=0,
            duplicate_n=0,
            bad_turnover_n=0,
            unresolved_symbol_n=0,
            zero_trade_symbols={'600074.SH'},
        ))


if __name__ == '__main__':
    unittest.main()
