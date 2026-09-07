import unittest

from cninfo_exact_term_v481 import choose_implementation_announcement, query_window


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


if __name__=='__main__':
    unittest.main()
