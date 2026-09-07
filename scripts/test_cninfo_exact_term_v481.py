import unittest

from cninfo_exact_term_v481 import (
    choose_implementation_announcement,
    query_window,
    choose_orgid_record,
    stock_query_param,
    column_for_code,
)
from collect_cninfo_exact_term_indices_v481 import (
    select_standard_exact_symbols,
    match_announcements_to_events,
)


class CninfoExactTermResolverTests(unittest.TestCase):
    def test_query_window_centers_notice_date(self):
        self.assertEqual(query_window('2023-05-09', 10), ('2023-04-29','2023-05-19'))

    def test_prefers_equity_distribution_implementation_announcement(self):
        items=[
            {'announcementTitle':'2022年年度股东大会决议公告','announcementTime':1683504000000,'adjunctUrl':'a.pdf'},
            {'announcementTitle':'2022年年度权益分派实施公告','announcementTime':1683676800000,'adjunctUrl':'b.pdf'},
            {'announcementTitle':'关于回购股份的进展公告','announcementTime':1683763200000,'adjunctUrl':'c.pdf'},
        ]
        x=choose_implementation_announcement(items,'2023-05-09')
        self.assertEqual(x['adjunctUrl'],'b.pdf')

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

    def test_event_without_prior_implementation_announcement_stays_unmatched(self):
        out=match_announcements_to_events(['2023-05-17'],[],max_prior_days=30)
        self.assertIsNone(out['2023-05-17'])


if __name__=='__main__':
    unittest.main()
