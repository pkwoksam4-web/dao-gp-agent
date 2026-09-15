from __future__ import annotations

import importlib
import unittest


def _subject():
    try:
        return importlib.import_module('gp12_pit_adjusted_close_v482')
    except ModuleNotFoundError as exc:
        raise AssertionError('gp12_pit_adjusted_close_v482 production module is missing') from exc


class PitAdjustedCloseAvailabilityTests(unittest.TestCase):
    def test_rejects_event_when_final_terms_arrive_after_ex_date(self):
        m = _subject()
        event = {
            'symbol': '600197.SH',
            'ex_date': '2020-07-02',
            'availability_date': '2020-07-03',
            'event_ratio': 0.96,
        }
        with self.assertRaisesRegex(ValueError, 'EVENT_NOT_PIT_AVAILABLE'):
            m.validate_event_availability(event)

    def test_final_override_availability_supersedes_same_day_nominal_source(self):
        m = _subject()
        resolve = getattr(m, 'resolve_final_event_availability', None)
        self.assertTrue(callable(resolve), 'resolve_final_event_availability is not implemented')
        # 000697: the generic F10 row is dated on ex-date, while the final
        # restructuring implementation terms were already disclosed 3 days earlier.
        resolved = resolve(
            ex_date='2025-11-28',
            nominal_availability_date='2025-11-28',
            final_override_availability_date='2025-11-25',
        )
        self.assertEqual(resolved, '2025-11-25')

    def test_forward_path_applies_event_from_ex_date_only(self):
        m = _subject()
        raw_rows = [
            {'date': '2020-06-30', 'close': 100.0},
            {'date': '2020-07-02', 'close': 90.0},
            {'date': '2020-07-03', 'close': 99.0},
        ]
        events = [{
            'symbol': 'TEST.SZ',
            'ex_date': '2020-07-02',
            'availability_date': '2020-07-01',
            'event_ratio': 0.9,
        }]
        path = m.build_forward_pit_adjusted_path(raw_rows, events)
        self.assertEqual([row['date'] for row in path], ['2020-06-30', '2020-07-02', '2020-07-03'])
        self.assertEqual([round(row['adjusted_close'], 10) for row in path], [100.0, 100.0, 110.0])

    def test_qfq_path_uses_factor_known_for_each_trade_date(self):
        m = _subject()
        build = getattr(m, 'build_qfq_adjusted_path', None)
        self.assertTrue(callable(build), 'build_qfq_adjusted_path is not implemented')
        raw_rows = [
            {'date': '2020-06-30', 'close': 100.0},
            {'date': '2020-07-02', 'close': 90.0},
            {'date': '2020-07-03', 'close': 99.0},
        ]
        factors = [
            {'d': '2020-06-01', 'f': 1.1111111111111112},
            {'d': '2020-07-02', 'f': 1.0},
        ]
        path = build(raw_rows, factors)
        self.assertEqual([round(row['adjusted_close'], 10) for row in path], [90.0, 90.0, 99.0])

    def test_qfq_and_pit_paths_must_be_constant_scale_equivalent(self):
        m = _subject()
        compare = getattr(m, 'compare_constant_scale_paths', None)
        self.assertTrue(callable(compare), 'compare_constant_scale_paths is not implemented')
        pit_rows = [
            {'date': '2020-06-30', 'adjusted_close': 100.0},
            {'date': '2020-07-02', 'adjusted_close': 100.0},
            {'date': '2020-07-03', 'adjusted_close': 110.0},
        ]
        qfq_rows = [
            {'date': '2020-06-30', 'adjusted_close': 90.0},
            {'date': '2020-07-02', 'adjusted_close': 90.0},
            {'date': '2020-07-03', 'adjusted_close': 99.0},
        ]
        report = compare(pit_rows, qfq_rows, threshold_bp=5.0)
        self.assertEqual(report['status'], 'PASS_CONSTANT_SCALE')
        self.assertAlmostEqual(report['scale'], 0.9, places=12)
        self.assertLessEqual(report['max_diff_bp'], 1e-9)


if __name__ == '__main__':
    unittest.main()
