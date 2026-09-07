import unittest

from cninfo_exact_term_v481 import (
    choose_implementation_announcement,
    query_window,
    choose_orgid_record,
    stock_query_param,
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


if __name__=='__main__':
    unittest.main()
