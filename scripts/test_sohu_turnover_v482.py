from __future__ import annotations

import importlib
import json
import unittest


def _subject():
    try:
        return importlib.import_module('sohu_turnover_v482')
    except ModuleNotFoundError as exc:
        raise AssertionError('sohu_turnover_v482 production module is missing') from exc


def _payload(rows):
    return ('historySearchHandler(' + json.dumps([{'status': 0, 'hq': rows}], ensure_ascii=False) + ')').encode('utf-8')


class SohuTurnoverContracts(unittest.TestCase):
    def test_parser_converts_percent_to_ratio_without_touching_price_semantics(self):
        m = _subject()
        rows = m.parse_hishq_turnover_bytes('600634.SH', _payload([
            ['2020-07-20','0.93','0.98','0.03','3.16%','0.92','0.98','44506','422.93','0.77%'],
            ['2020-07-22','0.99','0.99','0.00','0.00%','0.97','0.99','40956','403.24','0.71%'],
            ['2020-09-24','1.08','1.07','-0.01','-0.93%','1.06','1.09','69761','747.24','1.21%'],
        ]))
        self.assertEqual([r['date'] for r in rows], ['2020-07-20','2020-07-22','2020-09-24'])
        self.assertAlmostEqual(rows[0]['turnover_ratio'], 0.0077, places=12)
        self.assertAlmostEqual(rows[1]['turnover_ratio'], 0.0071, places=12)
        self.assertAlmostEqual(rows[2]['turnover_ratio'], 0.0121, places=12)
        self.assertTrue(all(r['source'] == 'SOHU_HISHQ_TURNOVER' for r in rows))

    def test_parser_fails_closed_when_trade_row_has_missing_turnover(self):
        m = _subject()
        with self.assertRaisesRegex(ValueError, 'turnover'):
            m.parse_hishq_turnover_bytes('600634.SH', _payload([
                ['2020-07-22','0.99','0.99','0.00','0.00%','0.97','0.99','40956','403.24','-'],
            ]))

    def test_cross_source_percent_semantics_are_exact_for_archived_fixture(self):
        m = _subject()
        sohu = [
            {'symbol':'600634.SH','date':'2020-07-20','turnover_ratio':0.0077},
            {'symbol':'600634.SH','date':'2020-07-22','turnover_ratio':0.0071},
            {'symbol':'600634.SH','date':'2020-09-24','turnover_ratio':0.0121},
        ]
        eastmoney = [
            {'symbol':'600634.SH','date':'2020-07-20','turnover_pct':0.77},
            {'symbol':'600634.SH','date':'2020-07-22','turnover_pct':0.71},
            {'symbol':'600634.SH','date':'2020-09-24','turnover_pct':1.21},
        ]
        out = m.crosscheck_eastmoney_turnover(sohu, eastmoney, tolerance_bp=0.01)
        self.assertEqual(out['matched_n'], 3)
        self.assertEqual(out['fail_n'], 0)
        self.assertEqual(out['max_diff_bp'], 0.0)

    def test_shard_selection_is_deterministic_and_complete(self):
        m = _subject()
        symbols = [f'{i:06d}.SZ' for i in range(17)]
        shards = [m.select_shard(symbols, i, 4) for i in range(4)]
        flattened = [symbol for shard in shards for symbol in shard]
        self.assertEqual(sorted(flattened), sorted(symbols))
        self.assertEqual(len(flattened), len(set(flattened)))
        self.assertEqual(shards[0], symbols[0::4])

    def test_trade_date_audit_requires_exact_dates_once(self):
        m = _subject()
        rows = [
            {'symbol':'000001.SZ','date':'2024-01-02','turnover_ratio':0.01},
            {'symbol':'000001.SZ','date':'2024-01-03','turnover_ratio':0.02},
        ]
        ok = m.audit_trade_dates('000001.SZ', ['2024-01-02','2024-01-03'], rows)
        self.assertEqual(ok['status'], 'PASS_EXACT_TURNOVER_DATES')
        self.assertEqual(ok['missing_dates_n'], 0)
        self.assertEqual(ok['extra_dates_n'], 0)
        self.assertEqual(ok['duplicate_dates_n'], 0)

        missing = m.audit_trade_dates('000001.SZ', ['2024-01-02','2024-01-03'], rows[:1])
        self.assertEqual(missing['status'], 'REVIEW_TURNOVER_DATES')
        self.assertEqual(missing['missing_dates'], ['2024-01-03'])

        duplicate = m.audit_trade_dates('000001.SZ', ['2024-01-02','2024-01-03'], rows + [dict(rows[1])])
        self.assertEqual(duplicate['status'], 'REVIEW_TURNOVER_DATES')
        self.assertEqual(duplicate['duplicate_dates_n'], 1)

    def test_trade_date_audit_rejects_negative_or_nonfinite_turnover(self):
        m = _subject()
        rows = [
            {'symbol':'000001.SZ','date':'2024-01-02','turnover_ratio':-0.01},
            {'symbol':'000001.SZ','date':'2024-01-03','turnover_ratio':float('nan')},
        ]
        out = m.audit_trade_dates('000001.SZ', ['2024-01-02','2024-01-03'], rows)
        self.assertEqual(out['status'], 'REVIEW_BAD_TURNOVER')
        self.assertEqual(out['bad_turnover_n'], 2)

    def test_request_params_are_raw_daily_ascending_and_exact(self):
        m = _subject()
        params = m.build_request_params('600634.SH', '2020-06-01', '2020-08-29')
        self.assertEqual(params, {
            'code':'cn_600634',
            'start':'20200601',
            'end':'20200829',
            'stat':'1',
            'order':'A',
            'period':'d',
            'callback':'historySearchHandler',
            'rt':'jsonp',
        })

    def test_calendar_chunk_plan_is_gapless_and_bounded(self):
        m = _subject()
        chunks = m.plan_chunks('2020-06-01', '2020-12-31', max_calendar_days=90)
        self.assertEqual(chunks[0], ('2020-06-01','2020-08-29'))
        self.assertEqual(chunks[-1][1], '2020-12-31')
        self.assertTrue(all((__import__('datetime').date.fromisoformat(b) - __import__('datetime').date.fromisoformat(a)).days + 1 <= 90 for a,b in chunks))
        for (_, left_end), (right_start, _) in zip(chunks, chunks[1:]):
            self.assertEqual((__import__('datetime').date.fromisoformat(right_start) - __import__('datetime').date.fromisoformat(left_end)).days, 1)

    def test_merge_turnover_rows_rejects_conflicting_duplicate(self):
        m = _subject()
        a = [{'symbol':'600634.SH','date':'2020-07-22','turnover_ratio':0.0071,'source':'SOHU_HISHQ_TURNOVER'}]
        self.assertEqual(m.merge_turnover_rows_unique('600634.SH', a, list(a)), a)
        b = [{'symbol':'600634.SH','date':'2020-07-22','turnover_ratio':0.0072,'source':'SOHU_HISHQ_TURNOVER'}]
        with self.assertRaisesRegex(ValueError, 'conflicting duplicate'):
            m.merge_turnover_rows_unique('600634.SH', a, b)

    def test_global_gate_requires_exact_formal_trade_date_coverage(self):
        m = _subject()
        self.assertTrue(m.full_turnover_global_gate(
            unique_symbol_n=844,
            symbol_list_n=847,
            turnover_rows=1_011_607,
            duplicate_rows=0,
            missing_n=0,
            extra_n=0,
            bad_turnover_n=0,
            shard_error=0,
        ))
        self.assertFalse(m.full_turnover_global_gate(
            unique_symbol_n=844,
            symbol_list_n=847,
            turnover_rows=1_011_606,
            duplicate_rows=0,
            missing_n=1,
            extra_n=0,
            bad_turnover_n=0,
            shard_error=0,
        ))


if __name__ == '__main__':
    unittest.main()
