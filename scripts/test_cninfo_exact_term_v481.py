import unittest

from cninfo_exact_term_v481 import (
    choose_implementation_announcement,
    query_window,
    event_query_window,
    choose_orgid_record,
    stock_query_param,
    column_for_code,
    is_distribution_implementation_title,
)
from collect_cninfo_exact_term_indices_v481 import (
    select_standard_exact_symbols,
    match_announcements_to_events,
    shard_standard_scope,
)


class CninfoExactTermResolverTests(unittest.TestCase):
    def test_query_window_centers_notice_date(self):
        self.assertEqual(query_window('2023-05-09', 10), ('2023-04-29','2023-05-19'))

    def test_event_query_window_is_narrow_prior_focused(self):
        self.assertEqual(event_query_window('2024-10-18',45,2),('2024-09-03','2024-10-20'))

    def test_prefers_equity_distribution_implementation_announcement(self):
        items=[
            {'announcementTitle':'2022年年度股东大会决议公告','announcementTime':1683504000000,'adjunctUrl':'a.pdf'},
            {'announcementTitle':'2022年年度权益分派实施公告','announcementTime':1683676800000,'adjunctUrl':'b.pdf'},
            {'announcementTitle':'关于回购股份的进展公告','announcementTime':1683763200000,'adjunctUrl':'c.pdf'},
        ]
        x=choose_implementation_announcement(items,'2023-05-09')
        self.assertEqual(x['adjunctUrl'],'b.pdf')

    def test_accepts_common_distribution_implementation_title_variants(self):
        accepted=[
            '2024年度中期A股分红派息实施公告',
            '2023年年度利润分配实施公告',
            '2022年度利润分配方案实施公告',
            '2021年年度权益分派实施公告',
            '2020年度权益分配实施公告',
            '2024年度资本公积金转增股本实施公告',
            '2025年中期现金分红的实施公告',
        ]
        self.assertTrue(all(is_distribution_implementation_title(x) for x in accepted))

    def test_rejects_implementation_after_adjustment_and_preplan_titles(self):
        rejected=[
            '关于2024年度权益分派实施后调整回购股份价格上限的公告',
            '关于实施2023年度权益分派后调整可转债转股价格的公告',
            '2022年度利润分配预案',
            '关于回购股份的进展公告',
        ]
        self.assertTrue(all(not is_distribution_implementation_title(x) for x in rejected))

    def test_rejects_non_implementation_titles(self):
        items=[{'announcementTitle':'2022年度利润分配预案','announcementTime':1683504000000,'adjunctUrl':'a.pdf'}]
        self.assertIsNone(choose_implementation_announcement(items,'2023-05-09'))

    def test_orgid_record_requires_exact_code(self):
        records=[
            {'code':'001201','orgId':'gfbj0839748','zwjc':'other'},
            {'code':'001202','orgId':'gfbj0839749','zwjc':'炬申股份'},
        ]
        self.assertEqual(choose_orgid_record(records,'001202')['orgId'],'gfbj0839749')

    def test_orgid_record_missing_exact_code_fails_closed(self):
        with self.assertRaises(ValueError):
            choose_orgid_record([{'code':'001201','orgId':'x'}],'001202')

    def test_stock_query_param_uses_code_and_orgid(self):
        self.assertEqual(stock_query_param('001202','gfbj0839749'),'001202,gfbj0839749')

    def test_market_column_routes_shanghai_and_shenzhen(self):
        self.assertEqual(column_for_code('600306'),'sse')
        self.assertEqual(column_for_code('688001'),'sse')
        self.assertEqual(column_for_code('000631'),'szse')
        self.assertEqual(column_for_code('001299'),'szse')
        self.assertEqual(column_for_code('300001'),'szse')


class ExactTermBulkScopeTests(unittest.TestCase):
    def test_selects_standard_exact_and_excludes_special_restructuring(self):
        report={'records':[
            {'symbol':'000631.SZ','status':'REVIEW_GLOBAL_LEDGER_EXACT_TERMS','events':[{'ex_date':'2023-05-17'}]},
            {'symbol':'000525.SZ','status':'REVIEW_EXACT_TERMS_AFTER_MISSING_EVENT','events':[{'ex_date':'2024-11-18'}]},
            {'symbol':'000001.SZ','status':'PASS_GLOBAL_LEDGER_NOMINAL_FACTOR','events':[]},
        ]}
        out=select_standard_exact_symbols(report)
        self.assertEqual(list(out),['000631.SZ'])
        self.assertEqual(out['000631.SZ'],['2023-05-17'])

    def test_matches_nearest_prior_implementation_announcement(self):
        events=['2023-05-17','2024-07-05']
        items=[
            {'announcementTitle':'2022年年度权益分派实施公告','announcementTime':1683561600000,'adjunctUrl':'a.pdf'},
            {'announcementTitle':'2023年年度权益分派实施公告','announcementTime':1719532800000,'adjunctUrl':'b.pdf'},
        ]
        out=match_announcements_to_events(events,items,max_prior_days=30)
        self.assertEqual(out['2023-05-17']['adjunctUrl'],'a.pdf')
        self.assertEqual(out['2024-07-05']['adjunctUrl'],'b.pdf')

    def test_matches_dividend_and_profit_distribution_title_variants(self):
        events=['2024-10-18','2025-06-12']
        items=[
            {'announcementTitle':'2024年度中期A股分红派息实施公告','announcementTime':1728518400000,'adjunctUrl':'a.pdf'},
            {'announcementTitle':'2024年年度利润分配实施公告','announcementTime':1749168000000,'adjunctUrl':'b.pdf'},
        ]
        out=match_announcements_to_events(events,items,max_prior_days=30)
        self.assertEqual(out['2024-10-18']['adjunctUrl'],'a.pdf')
        self.assertEqual(out['2025-06-12']['adjunctUrl'],'b.pdf')

    def test_event_without_prior_implementation_announcement_stays_unmatched(self):
        out=match_announcements_to_events(['2023-05-17'],[],max_prior_days=30)
        self.assertIsNone(out['2023-05-17'])

    def test_deterministic_shards_partition_scope_exactly(self):
        scope={f'{i:06d}.SZ':['2024-01-02'] for i in range(17)}
        shards=[shard_standard_scope(scope,i,4) for i in range(4)]
        union={k for shard in shards for k in shard}
        self.assertEqual(union,set(scope))
        self.assertEqual(sum(len(s) for s in shards),len(scope))
        self.assertTrue(all(set(shards[i]).isdisjoint(set(shards[j])) for i in range(4) for j in range(i+1,4)))
        self.assertEqual(list(shards[0]),['000000.SZ','000004.SZ','000008.SZ','000012.SZ','000016.SZ'])


if __name__=='__main__':
    unittest.main()
