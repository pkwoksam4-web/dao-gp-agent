from __future__ import annotations

import unittest

import cninfo_unmatched22_v482 as u


class Unmatched22V482Tests(unittest.TestCase):
    def test_scope_is_exact_frozen_22_events(self):
        self.assertEqual(sum(len(v) for v in u.TARGETS.values()), 22)
        self.assertEqual(len(u.TARGETS), 13)
        self.assertEqual(u.TARGETS['000631.SZ'], ['2023-05-17', '2024-07-05'])
        self.assertEqual(u.TARGETS['000672.SZ'], ['2021-05-31', '2022-05-30', '2024-06-07', '2025-05-27'])

    def test_query_plan_has_targeted_families_and_empty_narrow_fallback_last(self):
        plan = u.query_plan('2024-07-05')
        keys = [p['searchkey'] for p in plan]
        for key in ('权益分派', '权益分配', '分红派息', '利润分配', '资本公积金转增股本', '现金分红', '实施公告'):
            self.assertIn(key, keys)
        self.assertEqual(keys[-1], '')
        self.assertLess(plan[-1]['prior_days'], 45)
        self.assertEqual(len({(p['searchkey'], p['prior_days'], p['forward_days']) for p in plan}), len(plan))

    def test_union_deduplicates_same_announcement_across_queries(self):
        a = {'announcementId': '123', 'announcementTitle': '2023年度权益分派实施公告', 'announcementTime': 1717000000000}
        b = dict(a)
        b['adjunctUrl'] = 'finalpage/2024-05-30/123.PDF'
        c = {'announcementId': '456', 'announcementTitle': '其他公告', 'announcementTime': 1717000000000}
        out = u.union_announcements([[a, c], [b]])
        self.assertEqual(len(out), 2)
        self.assertEqual({x['announcementId'] for x in out}, {'123', '456'})
        merged = next(x for x in out if x['announcementId'] == '123')
        self.assertEqual(merged.get('adjunctUrl'), b['adjunctUrl'])

    def test_selection_still_uses_existing_implementation_title_gate(self):
        event = '2024-06-10'
        def ms(day):
            import datetime as dt
            d = dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc)
            return int(d.timestamp() * 1000)
        items = [
            {'announcementId':'p','announcementTitle':'2023年度利润分配预案','announcementTime':ms('2024-06-08')},
            {'announcementId':'x','announcementTitle':'2023年度权益分派实施公告','announcementTime':ms('2024-06-07')},
            {'announcementId':'y','announcementTitle':'关于权益分派实施后股份变动的公告','announcementTime':ms('2024-06-09')},
        ]
        chosen = u.choose_for_event(event, items)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen['announcementId'], 'x')

    def test_ambiguous_same_day_different_implementation_announcements_fail_closed(self):
        import datetime as dt
        d = int(dt.datetime(2024, 6, 7, tzinfo=dt.timezone.utc).timestamp() * 1000)
        items = [
            {'announcementId':'a','announcementTitle':'权益分派实施公告','announcementTime':d},
            {'announcementId':'b','announcementTitle':'利润分配方案实施公告','announcementTime':d},
        ]
        with self.assertRaises(ValueError):
            u.choose_for_event('2024-06-10', items)


if __name__ == '__main__':
    unittest.main()
